"""Single-scan obstacle candidates from observed point support."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

import numpy as np

from drishti.ground import GroundClass
from drishti.semantics import LEARNING_TO_RAW

if TYPE_CHECKING:
    from drishti.pipeline import PointObservations

VOXEL_WIDTH_M = 0.45
MAX_CANDIDATES = 8192
_OBJECT_CLASSES = frozenset((*range(1, 9), 18, 19))
_NEIGHBORS = tuple(
    (dx, dy, dz)
    for dx in (-1, 0, 1)
    for dy in (-1, 0, 1)
    for dz in (-1, 0, 1)
    if (dx, dy, dz) > (0, 0, 0)
)


def _triple(values: np.ndarray) -> tuple[float, float, float]:
    return float(values[0]), float(values[1]), float(values[2])


@dataclass(frozen=True)
class InstanceEvidence:
    instance_id: int
    semantic_id: int
    semantic_confidence: float
    center_m: tuple[float, float, float]
    bounds_min_m: tuple[float, float, float]
    bounds_max_m: tuple[float, float, float]
    point_ids: tuple[int, ...]
    observed_ns: int
    uncertainty_m: float | None
    status: Literal["observed", "ambiguous"]


class ObstacleDetector(Protocol):
    def detect(
        self, observations: "PointObservations", timestamp_ns: int
    ) -> tuple[InstanceEvidence, ...]: ...


class ConnectedComponentDetector:
    """Group local returns without claiming filled occupancy or calibrated error."""

    def detect(
        self, observations: "PointObservations", timestamp_ns: int
    ) -> tuple[InstanceEvidence, ...]:
        points = observations.points_map_m
        ids = observations.point_ids
        labels = observations.semantic
        ground = observations.ground
        scores = observations.semantic_confidence
        n = len(ids)
        if (
            points.shape != (n, 3)
            or labels.shape != (n,)
            or ground.shape != (n,)
            or scores.shape != (n,)
            or len(set(ids.tolist())) != n
            or np.any(ids < 0)
            or not np.isfinite(points).all()
            or np.any(labels > 19)
            or np.any(ground > GroundClass.NONGROUND)
            or not np.isfinite(scores).all()
            or np.any((scores < 0) | (scores > 1))
        ):
            raise ValueError("invalid detector observations")
        if timestamp_ns < 0:
            raise ValueError("invalid detector timestamp")
        candidate = (ground != GroundClass.GROUND) | np.isin(labels, tuple(_OBJECT_CLASSES))
        indices = np.flatnonzero(candidate)
        if not len(indices):
            return ()
        voxels = np.floor(points[indices] / VOXEL_WIDTH_M).astype(np.int64)
        groups = np.where(np.isin(labels[indices], tuple(_OBJECT_CLASSES)), labels[indices], 0)
        voxel_members: dict[tuple[int, int, int, int], list[int]] = {}
        for index, group, voxel in zip(indices, groups, voxels, strict=True):
            key = (int(group), int(voxel[0]), int(voxel[1]), int(voxel[2]))
            voxel_members.setdefault(key, []).append(int(index))
        parent = {key: key for key in voxel_members}

        def root(key: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
            while parent[key] != key:
                parent[key] = parent[parent[key]]
                key = parent[key]
            return key

        for key in sorted(voxel_members):
            group, x, y, z = key
            for dx, dy, dz in _NEIGHBORS:
                neighbor = (group, x + dx, y + dy, z + dz)
                if neighbor in parent:
                    first, second = root(key), root(neighbor)
                    if first != second:
                        parent[max(first, second)] = min(first, second)
        components: dict[tuple[int, int, int, int], list[int]] = {}
        for key, members in voxel_members.items():
            components.setdefault(root(key), []).extend(members)
        if len(components) > MAX_CANDIDATES:
            raise ValueError("detector candidate capacity exceeded")
        ordered = sorted(components.values(), key=lambda members: int(np.min(ids[members])))
        result: list[InstanceEvidence] = []
        for instance_id, members in enumerate(ordered):
            positions = np.array(members, dtype=np.int64)
            support = tuple(sorted(int(value) for value in ids[positions]))
            bounds_min = points[positions].min(axis=0)
            bounds_max = points[positions].max(axis=0)
            first_label = int(labels[positions[0]])
            label = first_label if first_label in _OBJECT_CLASSES else 0
            ambiguous = label == 0 or len(positions) < 3
            result.append(
                InstanceEvidence(
                    instance_id=instance_id,
                    semantic_id=label,
                    semantic_confidence=float(np.mean(scores[positions])) if label else 0.0,
                    center_m=_triple((bounds_min + bounds_max) / 2),
                    bounds_min_m=_triple(bounds_min),
                    bounds_max_m=_triple(bounds_max),
                    point_ids=support,
                    observed_ns=timestamp_ns,
                    uncertainty_m=None,
                    status="ambiguous" if ambiguous else "observed",
                )
            )
        return tuple(result)


def panoptic_raw_labels(
    input_point_ids: np.ndarray,
    accepted_point_ids: np.ndarray,
    semantic_id: np.ndarray,
    instances: tuple[InstanceEvidence, ...],
) -> np.ndarray:
    """Scatter candidate thing IDs and semantic IDs into original scan order."""
    if len(accepted_point_ids) != len(semantic_id):
        raise ValueError("panoptic point alignment")
    positions = {int(point_id): index for index, point_id in enumerate(input_point_ids)}
    raw = np.zeros(len(input_point_ids), dtype=np.uint32)
    for point_id, label in zip(accepted_point_ids, semantic_id, strict=True):
        if int(point_id) not in positions or not 0 <= int(label) <= 19:
            raise ValueError("invalid panoptic point")
        raw[positions[int(point_id)]] = LEARNING_TO_RAW[int(label)]
    for item in instances:
        if 1 <= item.semantic_id <= 8:
            if item.instance_id >= 65535:
                raise ValueError("panoptic instance ID overflow")
            for point_id in item.point_ids:
                if point_id not in positions:
                    raise ValueError("invalid panoptic support")
                raw[positions[point_id]] |= np.uint32((item.instance_id + 1) << 16)
    return raw
