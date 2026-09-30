"""Single-scan obstacle candidates from observed point support."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

import numpy as np

from drishti.arrays import IntArray
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
    """Group local returns without claiming filled occupancy or calibrated error.

    The CPU union-find is the reference. ``device="cuda"`` computes the same 26-connected
    voxel components with sparse min-label propagation and returns identical evidence.
    """

    def __init__(self, *, device: Literal["cpu", "cuda"] = "cpu") -> None:
        if device not in ("cpu", "cuda"):
            raise ValueError("detector device must be cpu or cuda")
        self.device = device
        self._xp: Any = None
        if device == "cuda":
            from drishti.cuda_backend import CudaFramePath

            self._xp = CudaFramePath().cp

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
        if self._xp is not None:
            return self._build(
                device_components(self._xp, indices, groups, voxels),
                observations,
                timestamp_ns,
            )
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
        return self._build(
            [np.array(members, dtype=np.int64) for members in components.values()],
            observations,
            timestamp_ns,
        )

    @staticmethod
    def _build(
        components: list[IntArray], observations: "PointObservations", timestamp_ns: int
    ) -> tuple[InstanceEvidence, ...]:
        """Shared evidence construction; member order sets the first label and mean score."""
        points = observations.points_map_m
        ids = observations.point_ids
        labels = observations.semantic
        scores = observations.semantic_confidence
        if len(components) > MAX_CANDIDATES:
            raise ValueError("detector candidate capacity exceeded")
        ordered = sorted(components, key=lambda members: int(np.min(ids[members])))
        result: list[InstanceEvidence] = []
        for instance_id, positions in enumerate(ordered):
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


def device_components(
    xp: Any, indices: IntArray, groups: IntArray, voxels: IntArray
) -> list[IntArray]:
    """26-connected same-group voxel components on an array module (NumPy or CuPy).

    Members are returned in the CPU reference order: by the lowest point index of their
    voxel, then by point index, so first labels and mean scores match exactly.
    """
    to_host: Any = np.asarray if xp is np else xp.asnumpy
    group = xp.asarray(groups.astype(np.int64))
    voxel = xp.asarray(voxels)
    # One empty padding slot on each side keeps neighbour offsets from wrapping axes.
    coords = voxel - voxel.min(axis=0) + 1
    size_x, size_y, size_z = (int(value) + 2 for value in to_host(coords.max(axis=0)))
    if (int(groups.max()) + 1) * size_x * size_y * size_z >= 2**62:
        raise ValueError("detector voxel span exceeds device key packing")
    keys = ((group * size_x + coords[:, 0]) * size_y + coords[:, 1]) * size_z + coords[:, 2]
    unique, inverse = xp.unique(keys, return_inverse=True)
    inverse = inverse.reshape(-1)
    count = len(unique)
    sources, targets = [], []
    for dx, dy, dz in _NEIGHBORS:
        wanted = unique + (dx * size_y + dy) * size_z + dz
        found = xp.minimum(xp.searchsorted(unique, wanted), count - 1)
        hit = unique[found] == wanted
        sources.append(xp.flatnonzero(hit))
        targets.append(found[hit])
    source, target = xp.concatenate(sources), xp.concatenate(targets)
    label = xp.arange(count, dtype=xp.int64)
    for _ in range(count + 1):
        update = label.copy()
        xp.minimum.at(update, source, label[target])
        xp.minimum.at(update, target, label[source])
        update = update[update]
        if bool((update == label).all()):
            break
        label = update
    else:
        raise RuntimeError("device connected components did not converge")
    voxel_of = np.asarray(to_host(inverse), dtype=np.int64)
    component = np.asarray(to_host(label), dtype=np.int64)[voxel_of]
    first_index = np.full(count, np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(first_index, voxel_of, indices)
    order = np.lexsort((indices, first_index[voxel_of], component))
    boundaries = np.flatnonzero(np.diff(component[order])) + 1
    return [np.asarray(part, dtype=np.int64) for part in np.split(indices[order], boundaries)]


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
