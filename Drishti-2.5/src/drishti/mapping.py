import hashlib
import json
from dataclasses import dataclass, fields

import numpy as np
from numpy.typing import NDArray

from drishti.arrays import BoolArray, ByteArray, FloatArray, IntArray, immutable
from drishti.config import MappingConfig
from drishti.contracts import Mode, PoseSource
from drishti.ground import GroundClass
from drishti.semantics import CLASS_NAMES, Motion


@dataclass(frozen=True)
class CellOwners:
    level: IntArray
    indices: IntArray


def resolve_owners(
    xy_map_m: FloatArray, sensor_xy_m: FloatArray, config: MappingConfig
) -> CellOwners:
    if xy_map_m.ndim != 2 or xy_map_m.shape[1] != 2 or sensor_xy_m.shape != (2,):
        raise ValueError("ownership requires (N, 2) map points and a (2,) sensor position")
    if not np.isfinite(xy_map_m).all() or not np.isfinite(sensor_xy_m).all():
        raise ValueError("ownership coordinates must be finite")
    if np.any(np.abs(xy_map_m) > config.max_abs_coordinate_m):
        raise ValueError("ownership coordinates exceed the configured lattice bound")
    base = np.floor(xy_map_m / 0.05).astype(np.int64)
    level = np.full(len(base), len(config.ratios) - 1, dtype=np.int64)
    for current in range(len(config.ratios) - 1, 0, -1):
        width_m = config.cell_sizes_cm[current] / 100
        lower_m = (base // config.ratios[current]) * width_m
        distance_m = np.maximum(
            np.maximum(lower_m - sensor_xy_m, sensor_xy_m - (lower_m + width_m)), 0
        )
        closest_m = (
            np.linalg.norm(distance_m, axis=1)
            if config.footprint == "radial"
            else np.max(distance_m, axis=1)
        )
        promote = (level == current) & (closest_m < config.radii_m[current - 1])
        level[promote] -= 1
    ratios = np.asarray(config.ratios, dtype=np.int64)[level]
    return CellOwners(immutable(level), immutable(base // ratios[:, None]))


@dataclass(frozen=True)
class MapSnapshot:
    sequence: str
    frame_id: int
    timestamp_s: float
    mode: Mode
    pose_source: PoseSource
    config_digest: str
    ground_method: str
    level: IntArray
    indices: IntArray
    centers_xy_m: FloatArray
    size_m: FloatArray
    point_count: IntArray
    ground_count: IntArray
    unknown_ground_count: IntArray
    ground_height_cm: NDArray[np.int32]
    ground_valid: BoolArray
    ground_span_cm: IntArray
    ground_spread_m2: FloatArray
    ambiguous: BoolArray
    observed_min_cm: NDArray[np.int32]
    observed_max_cm: NDArray[np.int32]
    obstacle_min_cm: NDArray[np.int32]
    obstacle_max_cm: NDArray[np.int32]
    obstacle_valid: BoolArray
    semantic: ByteArray
    semantic_evidence: IntArray
    semantic_conflict: BoolArray
    motion: ByteArray
    intensity_mean: FloatArray
    intensity_valid: BoolArray
    scope: str = "single-frame"
    coordinate_frame: str = "map-x-forward-y-left-z-up"
    vertical_datum: str = "initial-sensor-origin"

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, np.ndarray):
                object.__setattr__(self, field.name, immutable(value))

    @property
    def array_bytes(self) -> int:
        return sum(
            value.nbytes
            for field in fields(self)
            if isinstance(value := getattr(self, field.name), np.ndarray)
        )

    @property
    def digest(self) -> str:
        digest = hashlib.sha256()
        for field in fields(self):
            value = getattr(self, field.name)
            digest.update(field.name.encode())
            if isinstance(value, np.ndarray):
                digest.update(str(value.dtype).encode())
                digest.update(str(value.shape).encode())
                digest.update(value.tobytes())
            else:
                digest.update(json.dumps(value, allow_nan=False).encode())
        return digest.hexdigest()


def aggregate_cells(
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
    owners = resolve_owners(xyz_map_m[:, :2], sensor_xy_m, config)
    keys = np.column_stack((owners.level, owners.indices))
    unique, inverse, count = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    inverse = inverse.astype(np.int64)
    n = len(unique)
    height_cm = np.rint(xyz_map_m[:, 2] * 100).astype(np.int64)
    is_ground = ground == GroundClass.GROUND
    is_obstacle = ground == GroundClass.NONGROUND

    def counts(mask: BoolArray) -> IntArray:
        return np.bincount(inverse[mask], minlength=n).astype(np.int64)

    def bounds(mask: BoolArray) -> tuple[IntArray, IntArray]:
        low = np.full(n, np.iinfo(np.int64).max, dtype=np.int64)
        high = np.full(n, np.iinfo(np.int64).min, dtype=np.int64)
        np.minimum.at(low, inverse[mask], height_cm[mask])
        np.maximum.at(high, inverse[mask], height_cm[mask])
        valid = counts(mask) > 0
        return np.where(valid, low, 0), np.where(valid, high, 0)

    ground_count = counts(is_ground)
    ground_low, ground_high = bounds(is_ground)
    span_cm = ground_high - ground_low
    ambiguous = (ground_count > 0) & (span_cm > config.ambiguous_ground_span_m * 100)
    ground_valid = (ground_count > 0) & ~ambiguous
    sums = np.zeros(n, dtype=np.int64)
    squares = np.zeros(n, dtype=np.int64)
    np.add.at(sums, inverse[is_ground], height_cm[is_ground])
    np.add.at(squares, inverse[is_ground], height_cm[is_ground] ** 2)
    denominator = np.maximum(ground_count, 1)
    mean_cm = sums / denominator
    ground_height = np.where(ground_valid, np.rint(mean_cm), 0).astype(np.int32)
    spread_m2 = np.maximum(squares / denominator - mean_cm**2, 0) / 10000
    observed_low, observed_high = bounds(np.ones(len(inverse), dtype=np.bool_))
    obstacle_low, obstacle_high = bounds(is_obstacle)
    evidence = np.zeros((n, len(CLASS_NAMES)), dtype=np.int64)
    np.add.at(evidence, (inverse, semantic), 1)
    dominant = np.argmax(evidence, axis=1).astype(np.uint8)
    conflict = np.count_nonzero(evidence[:, 1:], axis=1) > 1
    tied = np.count_nonzero(evidence == np.max(evidence, axis=1, keepdims=True), axis=1) > 1
    dominant[tied] = 0
    cell_motion = np.full(n, Motion.UNKNOWN, dtype=np.uint8)
    cell_motion[counts(motion == Motion.STATIONARY) == count] = Motion.STATIONARY
    cell_motion[counts(motion == Motion.MOVING) > 0] = Motion.MOVING
    finite_intensity = np.isfinite(intensity)
    intensity_count = counts(finite_intensity)
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
        unknown_ground_count=counts(ground == GroundClass.UNKNOWN),
        ground_height_cm=ground_height,
        ground_valid=ground_valid,
        ground_span_cm=span_cm,
        ground_spread_m2=spread_m2,
        ambiguous=ambiguous,
        observed_min_cm=observed_low.astype(np.int32),
        observed_max_cm=observed_high.astype(np.int32),
        obstacle_min_cm=obstacle_low.astype(np.int32),
        obstacle_max_cm=obstacle_high.astype(np.int32),
        obstacle_valid=counts(is_obstacle) > 0,
        semantic=dominant,
        semantic_evidence=evidence,
        semantic_conflict=conflict,
        motion=cell_motion,
        intensity_mean=intensity_sum / np.maximum(intensity_count, 1),
        intensity_valid=intensity_count > 0,
    )
    return snapshot, immutable(inverse)
