from dataclasses import dataclass

import numpy as np

from drishti.arrays import BoolArray, FloatArray, IntArray, PointArray, immutable
from drishti.config import MappingConfig


@dataclass(frozen=True)
class RangeImage:
    ranges_m: FloatArray
    point_ids: IntArray
    collisions: int
    outside_fov: int

    @property
    def valid(self) -> BoolArray:
        return np.asarray(self.point_ids >= 0, dtype=np.bool_)

    @property
    def array_bytes(self) -> int:
        return self.ranges_m.nbytes + self.point_ids.nbytes


def project(points: PointArray, point_ids: IntArray, config: MappingConfig) -> RangeImage:
    if points.ndim != 2 or points.shape[1] != 4 or point_ids.shape != (len(points),):
        raise ValueError("projection requires (N, 4) points and aligned original point IDs")
    if len(points) > config.max_points:
        raise ValueError("projection point count exceeds configured capacity")
    if not np.isfinite(points[:, :3]).all():
        raise ValueError("projection requires finite geometry")
    xyz = points[:, :3].astype(np.float64)
    ranges = np.sqrt(xyz[:, 0] ** 2 + xyz[:, 1] ** 2 + xyz[:, 2] ** 2)
    elevation = np.arctan2(xyz[:, 2], np.hypot(xyz[:, 0], xyz[:, 1]))
    lower, upper = np.deg2rad([config.fov_down_deg, config.fov_up_deg])
    eligible = (ranges > 0) & (elevation >= lower) & (elevation <= upper)
    indices = np.flatnonzero(eligible)
    rows = np.floor((upper - elevation[indices]) / (upper - lower) * config.projection_rows)
    rows = np.clip(rows.astype(np.int64), 0, config.projection_rows - 1)
    azimuth = np.arctan2(xyz[indices, 1], xyz[indices, 0])
    columns = np.floor((azimuth + np.pi) / (2 * np.pi) * config.projection_columns)
    columns = columns.astype(np.int64) % config.projection_columns
    pixels = rows * config.projection_columns + columns
    shape = (config.projection_rows, config.projection_columns)
    image = np.full(shape, np.inf, dtype=np.float64)
    np.minimum.at(image.ravel(), pixels, ranges[indices])
    nearest = ranges[indices] == image.ravel()[pixels]
    inverse = np.full(shape, np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(inverse.ravel(), pixels[nearest], point_ids[indices][nearest])
    valid = np.isfinite(image)
    image[~valid] = np.nan
    inverse[~valid] = -1
    return RangeImage(
        immutable(image),
        immutable(inverse),
        len(indices) - int(np.count_nonzero(valid)),
        len(points) - len(indices),
    )
