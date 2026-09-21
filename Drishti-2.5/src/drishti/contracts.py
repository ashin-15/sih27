import math
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray

from drishti.arrays import FloatArray, IntArray, PointArray, immutable
from drishti.geometry import validate_transform
from drishti.semantics import Annotations


class Mode(StrEnum):
    GEOMETRIC = "geometric"
    ORACLE = "oracle"


class PoseSource(StrEnum):
    SLAM = "slam"
    KITTI_GT = "kitti-gt"
    SYNTHETIC = "synthetic"


@dataclass(frozen=True)
class ScanFrame:
    sequence: str
    frame_id: int
    timestamp_s: float
    points_sensor: PointArray
    point_ids: IntArray
    map_from_sensor: FloatArray
    pose_source: PoseSource
    annotations: Annotations | None = None
    deskew_status: str = "unavailable"

    def __post_init__(self) -> None:
        if self.frame_id < 0 or not math.isfinite(self.timestamp_s) or self.timestamp_s < 0:
            raise ValueError("frame ID and timestamp must be nonnegative and finite")
        if self.points_sensor.ndim != 2 or self.points_sensor.shape[1] != 4:
            raise ValueError("scan points must have shape (N, 4)")
        if self.point_ids.shape != (len(self.points_sensor),) or self.point_ids.dtype != np.int64:
            raise ValueError("point IDs must be aligned int64 original indices")
        if np.any(self.point_ids < 0) or len(np.unique(self.point_ids)) != len(self.point_ids):
            raise ValueError("original point IDs must be unique and nonnegative")
        validate_transform(self.map_from_sensor)
        if self.annotations is not None:
            for array in (
                self.annotations.semantic,
                self.annotations.motion,
                self.annotations.instance,
            ):
                if array.shape != (len(self.points_sensor),):
                    raise ValueError("annotation lengths must match the scan")
        object.__setattr__(self, "points_sensor", immutable(self.points_sensor))
        object.__setattr__(self, "point_ids", immutable(self.point_ids))
        object.__setattr__(self, "map_from_sensor", immutable(self.map_from_sensor))


@dataclass(frozen=True)
class Accounting:
    input_points: int
    invalid_geometry: int
    outside_roi: int
    outside_height: int
    accepted_points: int
    invalid_intensity: int
    projected_points: int
    projection_collisions: int
    outside_projection: int

    def __post_init__(self) -> None:
        terminal = (
            self.invalid_geometry + self.outside_roi + self.outside_height + self.accepted_points
        )
        if terminal != self.input_points:
            raise ValueError("point accounting does not conserve input points")
        if (
            self.projected_points + self.projection_collisions + self.outside_projection
            != self.accepted_points
        ):
            raise ValueError("projection accounting does not conserve accepted points")


def make_frame(
    points: NDArray[np.float32],
    *,
    sequence: str = "synthetic",
    frame_id: int = 0,
    timestamp_s: float = 0.0,
    map_from_sensor: FloatArray | None = None,
    annotations: Annotations | None = None,
) -> ScanFrame:
    return ScanFrame(
        sequence,
        frame_id,
        timestamp_s,
        points,
        np.arange(len(points), dtype=np.int64),
        np.eye(4) if map_from_sensor is None else map_from_sensor,
        PoseSource.SYNTHETIC,
        annotations,
    )
