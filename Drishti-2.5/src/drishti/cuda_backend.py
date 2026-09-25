"""Optional CUDA execution for the current single-frame map contracts.

The CPU path remains the reference. CuPy is imported only when CUDA is selected so the
headless package continues to run on machines without an NVIDIA device.
"""

import importlib
from typing import Any

import numpy as np

from drishti.arrays import ByteArray, FloatArray, IntArray, PointArray, immutable
from drishti.config import MappingConfig
from drishti.contracts import Mode, PoseSource
from drishti.ground import GroundClass
from drishti.mapping import MapSnapshot, aggregate_cells
from drishti.projection import RangeImage
from drishti.semantics import CLASS_NAMES, Motion


class CudaFramePath:
    """Run range projection and cell reductions on a CUDA device.

    Accepted-point filtering and Patchwork++ stay on the host. CPU ``MapSnapshot`` and
    ``RangeImage`` remain the public result types, so transfers are included in stage time.
    """

    def __init__(self) -> None:
        try:
            self.cp = importlib.import_module("cupy")
            if self.cp.cuda.runtime.getDeviceCount() < 1:
                raise RuntimeError("no NVIDIA CUDA device is available")
            # An import and device count do not prove kernels can launch.
            if int((self.cp.arange(4, dtype=self.cp.int32) * 2).sum()) != 12:
                raise RuntimeError("CUDA kernel launch returned an unexpected result")
        except (ImportError, OSError, RuntimeError) as exc:
            raise RuntimeError(
                "CUDA requires a working NVIDIA device and a matching CuPy installation"
            ) from exc

    @staticmethod
    def available() -> bool:
        try:
            cp = importlib.import_module("cupy")
            return bool(cp.cuda.runtime.getDeviceCount() > 0)
        except (ImportError, OSError, RuntimeError):
            return False

    def _host(self, values: Any) -> np.ndarray[Any, Any]:
        return np.asarray(self.cp.asnumpy(values))

    def _cell_keys(
        self, xyz_map_m: FloatArray, sensor_xy_m: FloatArray, config: MappingConfig
    ) -> Any:
        xy_map_m = xyz_map_m[:, :2]
        if xy_map_m.ndim != 2 or xy_map_m.shape[1] != 2 or sensor_xy_m.shape != (2,):
            raise ValueError("ownership requires (N, 2) map points and a (2,) sensor position")
        if not np.isfinite(xy_map_m).all() or not np.isfinite(sensor_xy_m).all():
            raise ValueError("ownership coordinates must be finite")
        if np.any(np.abs(xy_map_m) > config.max_abs_coordinate_m):
            raise ValueError("ownership coordinates exceed the configured lattice bound")

        cp = self.cp
        xy = cp.asarray(xy_map_m)
        sensor = cp.asarray(sensor_xy_m)
        base = cp.floor(xy / 0.05).astype(cp.int64)
        level = cp.full(len(base), len(config.ratios) - 1, dtype=cp.int64)
        for current in range(len(config.ratios) - 1, 0, -1):
            width_m = config.cell_sizes_cm[current] / 100
            lower_m = (base // config.ratios[current]) * width_m
            dx_m = cp.maximum(
                cp.maximum(lower_m[:, 0] - sensor[0], sensor[0] - (lower_m[:, 0] + width_m)),
                0,
            )
            dy_m = cp.maximum(
                cp.maximum(lower_m[:, 1] - sensor[1], sensor[1] - (lower_m[:, 1] + width_m)),
                0,
            )
            closest_m = (
                cp.sqrt(dx_m * dx_m + dy_m * dy_m)
                if config.footprint == "radial"
                else cp.maximum(dx_m, dy_m)
            )
            promote = (level == current) & (closest_m < config.radii_m[current - 1])
            level[promote] -= 1
        ratios = cp.asarray(config.ratios, dtype=cp.int64)[level]
        return cp.column_stack((level, base // ratios[:, None]))

    def project(self, points: PointArray, point_ids: IntArray, config: MappingConfig) -> RangeImage:
        if points.ndim != 2 or points.shape[1] != 4 or point_ids.shape != (len(points),):
            raise ValueError("projection requires (N, 4) points and aligned original point IDs")
        if len(points) > config.max_points:
            raise ValueError("projection point count exceeds configured capacity")
        if not np.isfinite(points[:, :3]).all():
            raise ValueError("projection requires finite geometry")
        cp = self.cp
        xyz = cp.asarray(points[:, :3], dtype=cp.float64)
        ids = cp.asarray(point_ids)
        ranges = cp.sqrt(xyz[:, 0] ** 2 + xyz[:, 1] ** 2 + xyz[:, 2] ** 2)
        elevation = cp.arctan2(xyz[:, 2], cp.hypot(xyz[:, 0], xyz[:, 1]))
        lower, upper = np.deg2rad([config.fov_down_deg, config.fov_up_deg])
        eligible = (ranges > 0) & (elevation >= lower) & (elevation <= upper)
        indices = cp.flatnonzero(eligible)
        rows = cp.floor((upper - elevation[indices]) / (upper - lower) * config.projection_rows)
        rows = cp.clip(rows.astype(cp.int64), 0, config.projection_rows - 1)
        azimuth = cp.arctan2(xyz[indices, 1], xyz[indices, 0])
        columns = cp.floor((azimuth + np.pi) / (2 * np.pi) * config.projection_columns)
        columns = columns.astype(cp.int64) % config.projection_columns
        pixels = rows * config.projection_columns + columns
        shape = (config.projection_rows, config.projection_columns)
        image = cp.full(shape, cp.inf, dtype=cp.float64)
        cp.minimum.at(image.ravel(), pixels, ranges[indices])
        nearest = ranges[indices] == image.ravel()[pixels]
        owners = cp.full(shape, np.iinfo(np.int64).max, dtype=cp.int64)
        cp.minimum.at(owners.ravel(), pixels[nearest], ids[indices][nearest])
        valid = cp.isfinite(image)
        image[~valid] = cp.nan
        owners[~valid] = -1
        valid_count = int(cp.count_nonzero(valid))
        eligible_count = int(indices.size)
        return RangeImage(
            immutable(self._host(image)),
            immutable(self._host(owners)),
            eligible_count - valid_count,
            len(points) - eligible_count,
        )

    def aggregate_cells(
        self,
        xyz_map_m: FloatArray,
        sensor_xy_m: FloatArray,
        ground: ByteArray,
        semantic: ByteArray,
        motion: ByteArray,
        intensity: FloatArray,
        *,
        config: MappingConfig,
        sequence: str,
        frame_id: int,
        timestamp_s: float,
        mode: Mode,
        pose_source: PoseSource,
        ground_method: str,
    ) -> tuple[MapSnapshot, IntArray]:
        if not len(xyz_map_m):
            return aggregate_cells(
                xyz_map_m,
                sensor_xy_m,
                ground,
                semantic,
                motion,
                intensity,
                config=config,
                sequence=sequence,
                frame_id=frame_id,
                timestamp_s=timestamp_s,
                mode=mode,
                pose_source=pose_source,
                ground_method=ground_method,
            )

        cp = self.cp
        keys = self._cell_keys(xyz_map_m, sensor_xy_m, config)
        order = cp.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
        ordered = keys[order]
        starts = cp.empty(len(keys), dtype=cp.bool_)
        starts[0] = True
        starts[1:] = cp.any(ordered[1:] != ordered[:-1], axis=1)
        unique = self._host(ordered[starts]).astype(np.int64)
        n = len(unique)
        inverse_device = cp.empty(len(keys), dtype=cp.int64)
        inverse_device[order] = cp.cumsum(starts, dtype=cp.int64) - 1
        count_device = cp.bincount(inverse_device, minlength=n)
        inverse = self._host(inverse_device).astype(np.int64)

        # Fixed-point heights are quantized on the reference host before transfer.
        height_cm = cp.asarray(np.rint(xyz_map_m[:, 2] * 100).astype(np.int64))
        ground_device = cp.asarray(ground)
        semantic_device = cp.asarray(semantic)
        motion_device = cp.asarray(motion)
        is_ground = ground_device == GroundClass.GROUND
        is_obstacle = ground_device == GroundClass.NONGROUND

        def counts(mask: Any) -> Any:
            return cp.bincount(inverse_device[mask], minlength=n)

        def bounds(mask: Any) -> tuple[Any, Any]:
            low = cp.full(n, np.iinfo(np.int64).max, dtype=cp.int64)
            high = cp.full(n, np.iinfo(np.int64).min, dtype=cp.int64)
            cp.minimum.at(low, inverse_device[mask], height_cm[mask])
            cp.maximum.at(high, inverse_device[mask], height_cm[mask])
            valid = counts(mask) > 0
            return cp.where(valid, low, 0), cp.where(valid, high, 0)

        ground_count_device = counts(is_ground)
        unknown_ground_count_device = counts(ground_device == GroundClass.UNKNOWN)
        obstacle_count_device = counts(is_obstacle)
        ground_low_device, ground_high_device = bounds(is_ground)
        observed_low_device, observed_high_device = bounds(cp.ones(len(keys), dtype=cp.bool_))
        obstacle_low_device, obstacle_high_device = bounds(is_obstacle)
        sums = cp.zeros(n, dtype=cp.int64)
        squares = cp.zeros(n, dtype=cp.int64)
        cp.add.at(sums, inverse_device[is_ground], height_cm[is_ground])
        cp.add.at(squares, inverse_device[is_ground], height_cm[is_ground] ** 2)
        (
            count,
            ground_count,
            unknown_ground_count,
            obstacle_count,
            ground_low,
            ground_high,
            observed_low,
            observed_high,
            obstacle_low,
            obstacle_high,
            ground_sums,
            ground_squares,
        ) = self._host(
            cp.stack(
                (
                    count_device,
                    ground_count_device,
                    unknown_ground_count_device,
                    obstacle_count_device,
                    ground_low_device,
                    ground_high_device,
                    observed_low_device,
                    observed_high_device,
                    obstacle_low_device,
                    obstacle_high_device,
                    sums,
                    squares,
                )
            )
        ).astype(np.int64)
        span_cm = ground_high - ground_low
        ambiguous = (ground_count > 0) & (span_cm > config.ambiguous_ground_span_m * 100)
        ground_valid = (ground_count > 0) & ~ambiguous
        denominator = np.maximum(ground_count, 1)
        mean_cm = ground_sums / denominator
        ground_height = np.where(ground_valid, np.rint(mean_cm), 0).astype(np.int32)
        spread_m2 = np.maximum(ground_squares / denominator - mean_cm**2, 0) / 10000
        class_count = len(CLASS_NAMES)
        if not np.any(semantic) and not np.any(motion):
            evidence = np.zeros((n, class_count), dtype=np.int64)
            evidence[:, 0] = count
            dominant = np.zeros(n, dtype=np.uint8)
            conflict = np.zeros(n, dtype=np.bool_)
            cell_motion = np.full(n, Motion.UNKNOWN, dtype=np.uint8)
        else:
            packed = inverse_device * class_count + semantic_device
            evidence = (
                self._host(cp.bincount(packed, minlength=n * class_count))
                .reshape(n, class_count)
                .astype(np.int64)
            )
            dominant = np.argmax(evidence, axis=1).astype(np.uint8)
            conflict = np.count_nonzero(evidence[:, 1:], axis=1) > 1
            tied = np.count_nonzero(evidence == np.max(evidence, axis=1, keepdims=True), axis=1) > 1
            dominant[tied] = 0
            cell_motion = np.full(n, Motion.UNKNOWN, dtype=np.uint8)
            stationary_count, moving_count = self._host(
                cp.stack(
                    (
                        counts(motion_device == Motion.STATIONARY),
                        counts(motion_device == Motion.MOVING),
                    )
                )
            ).astype(np.int64)
            cell_motion[stationary_count == count] = Motion.STATIONARY
            cell_motion[moving_count > 0] = Motion.MOVING
        finite_intensity = np.isfinite(intensity)
        intensity_count = np.bincount(inverse[finite_intensity], minlength=n).astype(np.int64)
        intensity_sum = np.bincount(
            inverse[finite_intensity], weights=intensity[finite_intensity], minlength=n
        )
        size_m = np.asarray(config.cell_sizes_cm, dtype=np.float64)[unique[:, 0]] / 100
        snapshot = MapSnapshot(
            sequence=sequence,
            frame_id=frame_id,
            timestamp_s=timestamp_s,
            mode=mode,
            pose_source=pose_source,
            config_digest=config.digest,
            ground_method=ground_method,
            level=unique[:, 0],
            indices=unique[:, 1:],
            centers_xy_m=(unique[:, 1:] + 0.5) * size_m[:, None],
            size_m=size_m,
            point_count=count,
            ground_count=ground_count,
            unknown_ground_count=unknown_ground_count,
            ground_height_cm=ground_height,
            ground_valid=ground_valid,
            ground_span_cm=span_cm,
            ground_spread_m2=spread_m2,
            ambiguous=ambiguous,
            observed_min_cm=observed_low.astype(np.int32),
            observed_max_cm=observed_high.astype(np.int32),
            obstacle_min_cm=obstacle_low.astype(np.int32),
            obstacle_max_cm=obstacle_high.astype(np.int32),
            obstacle_valid=obstacle_count > 0,
            semantic=dominant,
            semantic_evidence=evidence,
            semantic_conflict=conflict,
            motion=cell_motion,
            intensity_mean=intensity_sum / np.maximum(intensity_count, 1),
            intensity_valid=intensity_count > 0,
        )
        return snapshot, immutable(inverse)
