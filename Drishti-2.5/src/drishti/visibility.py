"""Current-scan occupied, observed-free and unknown cell evidence from single returns.

Observed-free is evidence that a ground-terminated beam crossed a cell at low height with no
nearby conflicting return. It is not clearance, drivability or navigation proof.
"""

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from drishti.arrays import BoolArray, ByteArray, FloatArray, IntArray, immutable
from drishti.config import MappingConfig
from drishti.cuda_backend import CudaFramePath, owner_keys
from drishti.ground import GroundClass
from drishti.mapping import MapSnapshot, resolve_owners
from drishti.obstacles import InstanceEvidence

if TYPE_CHECKING:
    from drishti.pipeline import PointObservations

VISIBILITY_METHOD = "current-scan-ground-corridor-v1"
GROUND_SEMANTIC_IDS = (9, 10, 11, 12, 17)
MAX_FREE_CELLS = 262_144  # owner-raised 2026-09-30; real scans need about 131k-146k
SAMPLE_STEP_M = 0.025
INTERIOR_EPSILON_M = 1e-6
_BEAM_CHUNK = 4096
_INDEX_OFFSET = 1 << 25


class Occupancy(IntEnum):
    UNKNOWN = 0
    OCCUPIED = 1
    OBSERVED_FREE = 2
    STALE = 3
    AMBIGUOUS = 4


@dataclass(frozen=True)
class VisibilitySettings:
    tau_free_m: float = 0.10
    corridor_max_m: float = 5.0
    conflict_margin_m: float = 0.30
    max_free_cells: int = MAX_FREE_CELLS

    def __post_init__(self) -> None:
        for name in ("tau_free_m", "corridor_max_m", "conflict_margin_m"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if type(self.max_free_cells) is not int or not 1 <= self.max_free_cells <= MAX_FREE_CELLS:
            raise ValueError(f"max_free_cells must be between 1 and {MAX_FREE_CELLS}")


@dataclass(frozen=True)
class VisibilitySummary:
    method: str
    tau_free_m: float
    corridor_max_m: float
    conflict_margin_m: float
    max_free_cells: int
    qualifying_beams: int
    free_cells: int
    occupied_cells: int
    ambiguous_cells: int
    unknown_cells: int
    rejected_free_cells: int
    deskew_status: str


@dataclass(frozen=True)
class VisibilityEvidence:
    """Occupancy for snapshot cells in snapshot order, plus separately listed free cells."""

    occupancy: ByteArray
    obstacle_support: IntArray
    free_level: IntArray
    free_indices: IntArray
    free_ray_support: IntArray
    free_beam_point_id: IntArray
    summary: VisibilitySummary


def corridor_start_fraction(
    origin_m: FloatArray, return_m: FloatArray, settings: VisibilitySettings
) -> FloatArray:
    """Return per-beam corridor start fractions; NaN marks a nonqualifying beam."""
    delta = return_m[:, :2] - origin_m[:2]
    distance = np.hypot(delta[:, 0], delta[:, 1])
    drop = origin_m[2] - return_m[:, 2]
    valid = (distance > 0) & (drop > 0)
    safe_drop = np.where(valid, drop, 1.0)
    length = np.minimum(settings.corridor_max_m, settings.tau_free_m * distance / safe_drop)
    safe_distance = np.where(valid, distance, 1.0)
    fraction = np.maximum(0.0, 1.0 - length / safe_distance)
    return np.where(valid, fraction, np.nan)


def pack_cells(level: IntArray, indices: IntArray) -> IntArray:
    """Pack (level, x, y) into one int64; indices fit the configured lattice bound."""
    shifted = indices + _INDEX_OFFSET
    # Operators only, so the same packing runs on NumPy or CuPy arrays.
    return (((shifted[:, 0] << 26) | shifted[:, 1]) << 3 | level).astype(np.int64)


def unpack_cells(packed: IntArray) -> IntArray:
    """Inverse of ``pack_cells``: (level, x, y) rows."""
    mask = (1 << 26) - 1
    return np.column_stack(
        (packed & 7, (packed >> 29) - _INDEX_OFFSET, ((packed >> 3) & mask) - _INDEX_OFFSET)
    ).astype(np.int64)


def _near(cells: IntArray, conflicts: IntArray, steps: int) -> BoolArray:
    """Mark cells within `steps` Chebyshev index steps of any conflict cell."""
    if not len(cells) or not len(conflicts):
        return np.zeros(len(cells), dtype=np.bool_)
    span = np.arange(-steps, steps + 1, dtype=np.int64)
    offsets = np.stack(np.meshgrid(span, span, indexing="ij"), axis=-1).reshape(-1, 2)
    zero = np.zeros(1, dtype=np.int64)
    if len(cells) <= len(conflicts):
        expanded = (cells[:, None, :] + offsets[None]).reshape(-1, 2)
        hits = np.isin(
            pack_cells(np.zeros(len(expanded), dtype=np.int64), expanded),
            pack_cells(np.repeat(zero, len(conflicts)), conflicts),
        )
        return np.asarray(hits.reshape(len(cells), -1).any(axis=1), dtype=np.bool_)
    blocked = (conflicts[:, None, :] + offsets[None]).reshape(-1, 2)
    return np.asarray(
        np.isin(
            pack_cells(np.repeat(zero, len(cells)), cells),
            pack_cells(np.zeros(len(blocked), dtype=np.int64), blocked),
        ),
        dtype=np.bool_,
    )


_WINDOW_GRID_LIMIT = 1 << 24


def _near_window(cells: IntArray, conflicts: IntArray, steps: int) -> BoolArray:
    """Exact ``_near`` via a summed-area table over the cells' bounding window."""
    if not len(cells) or not len(conflicts):
        return np.zeros(len(cells), dtype=np.bool_)
    low = cells.min(axis=0) - steps
    high = cells.max(axis=0) + steps
    width, height = (int(value) for value in high - low + 1)
    if width * height > _WINDOW_GRID_LIMIT:
        return _near(cells, np.unique(conflicts, axis=0), steps)
    inside = np.all((conflicts >= low) & (conflicts <= high), axis=1)
    local = conflicts[inside] - low
    counts = np.bincount(local[:, 0] * height + local[:, 1], minlength=width * height)
    table = np.zeros((width + 1, height + 1), dtype=np.int64)
    table[1:, 1:] = counts.reshape(width, height).cumsum(axis=0).cumsum(axis=1)
    x0, y0 = (cells - steps - low).T
    x1, y1 = (cells + steps - low + 1).T
    window = table[x1, y1] - table[x0, y1] - table[x1, y0] + table[x0, y0]
    return np.asarray(window > 0, dtype=np.bool_)


class CurrentScanVisibility:
    """Stateless per-frame visibility; the engine owns sequencing and publication."""

    def __init__(
        self,
        settings: VisibilitySettings | None = None,
        *,
        device: Literal["cpu", "cuda"] = "cpu",
    ) -> None:
        if device not in ("cpu", "cuda"):
            raise ValueError("visibility device must be cpu or cuda")
        self.settings = VisibilitySettings() if settings is None else settings
        self.device = device
        # CPU is the reference; CUDA only moves corridor sampling and ownership to the device.
        self._xp: Any = CudaFramePath().cp if device == "cuda" else np

    def _corridor_pairs(
        self,
        points_xy: FloatArray,
        point_ids: IntArray,
        start_fraction: FloatArray,
        origin_xy: FloatArray,
        config: MappingConfig,
    ) -> IntArray:
        """Sample one beam chunk; return unique (packed cell key, point ID) rows on the host."""
        xp = self._xp
        origin = xp.asarray(origin_xy)
        delta = xp.asarray(points_xy) - origin
        distance = xp.hypot(delta[:, 0], delta[:, 1])
        fraction = xp.asarray(start_fraction)
        samples = xp.ceil(distance * (1.0 - fraction) / SAMPLE_STEP_M).astype(xp.int64)
        total = int(samples.sum())
        if not total:
            return np.empty((0, 2), dtype=np.int64)
        ends = xp.cumsum(samples)
        position = xp.arange(total, dtype=xp.int64)
        owner = xp.searchsorted(ends, position, side="right")
        step = position - (ends - samples)[owner]
        u = fraction[owner] + step * SAMPLE_STEP_M / distance[owner]
        keep = u < 1.0
        owner, u = owner[keep], u[keep]
        xy = origin + u[:, None] * delta[owner]
        if xp is np:
            owners = resolve_owners(xy, origin_xy, config)
            keys = np.column_stack((owners.level, owners.indices))
        else:
            keys = owner_keys(xp, xy, origin, config)
        width = xp.asarray(config.cell_sizes_cm, dtype=xp.float64)[keys[:, 0]] / 100
        low = keys[:, 1:3] * width[:, None]
        high = low + width[:, None]
        epsilon = INTERIOR_EPSILON_M
        inside = xp.all((xy - low > epsilon) & (high - xy > epsilon), axis=1)
        packed = pack_cells(keys[inside, 0], keys[inside, 1:3])
        ids = xp.asarray(point_ids)[owner[inside]]
        if not len(packed):
            return np.empty((0, 3), dtype=np.int64)
        # Reduce on the device: distinct beams per cell and the lowest supporting point ID.
        order = xp.lexsort(xp.stack((ids, packed)))
        packed, ids = packed[order], ids[order]
        distinct = xp.ones(len(packed), dtype=xp.bool_)
        distinct[1:] = (packed[1:] != packed[:-1]) | (ids[1:] != ids[:-1])
        packed, ids = packed[distinct], ids[distinct]
        new_cell = xp.ones(len(packed), dtype=xp.bool_)
        new_cell[1:] = packed[1:] != packed[:-1]
        starts = xp.flatnonzero(new_cell)
        counts = xp.diff(xp.concatenate((starts, xp.asarray([len(packed)]))))
        cells = xp.stack((packed[starts], counts, ids[starts]), axis=1)
        return np.asarray(cells if xp is np else xp.asnumpy(cells), dtype=np.int64)

    def compute(
        self,
        observations: "PointObservations",
        snapshot: MapSnapshot,
        instances: tuple[InstanceEvidence, ...],
        map_from_sensor: FloatArray,
        config: MappingConfig,
        deskew_status: str,
    ) -> VisibilityEvidence:
        settings = self.settings
        ids = observations.point_ids
        points = observations.points_map_m
        ground = observations.ground
        semantic = observations.semantic
        inverse = observations.cell_indices
        cell_count = len(snapshot.level)
        n = len(ids)
        if (
            points.shape != (n, 3)
            or ground.shape != (n,)
            or semantic.shape != (n,)
            or inverse.shape != (n,)
            or not np.isfinite(points).all()
            or (n and (inverse.min() < 0 or inverse.max() >= cell_count))
        ):
            raise ValueError("invalid visibility observations")
        support = np.fromiter(
            (point_id for item in instances for point_id in item.point_ids), dtype=np.int64
        )
        obstacle = (ground == GroundClass.NONGROUND) | np.isin(ids, support)
        clean = (ground == GroundClass.GROUND) & np.isin(semantic, GROUND_SEMANTIC_IDS)
        doubtful = ~obstacle & ~clean
        obstacle_support = np.bincount(inverse[obstacle], minlength=cell_count).astype(np.int64)
        doubtful_count = np.bincount(inverse[doubtful], minlength=cell_count)
        occupancy = np.full(cell_count, Occupancy.UNKNOWN, dtype=np.uint8)
        occupancy[obstacle_support > 0] = Occupancy.OCCUPIED
        ambiguous = snapshot.ambiguous | ((obstacle_support == 0) & (doubtful_count > 0))
        occupancy[ambiguous] = Occupancy.AMBIGUOUS

        origin = np.asarray(map_from_sensor[:3, 3], dtype=np.float64)
        sensor_range = np.linalg.norm(observations.points_sensor[:, :3].astype(np.float64), axis=1)
        candidates = np.flatnonzero(clean & (sensor_range >= config.ground_min_range_m))
        fraction = corridor_start_fraction(origin, points[candidates], settings)
        beams = candidates[np.isfinite(fraction)]
        fraction = fraction[np.isfinite(fraction)]
        sizes_m = np.asarray(config.cell_sizes_cm, dtype=np.float64) / 100
        found: list[IntArray] = []
        for start in range(0, len(beams), _BEAM_CHUNK):
            chunk = beams[start : start + _BEAM_CHUNK]
            reduced = self._corridor_pairs(
                points[chunk, :2],
                ids[chunk],
                fraction[start : start + _BEAM_CHUNK],
                origin[:2],
                config,
            )
            if len(reduced):
                found.append(reduced)
        # Each beam belongs to one chunk, so per-cell beam counts add and the minimum ID wins.
        merged = np.concatenate(found) if found else np.empty((0, 3), dtype=np.int64)
        starts = np.empty(0, dtype=np.int64)
        counts = np.empty(0, dtype=np.int64)
        if len(merged):
            merged = merged[np.lexsort((merged[:, 2], merged[:, 0]))]
            starts = np.flatnonzero(np.r_[True, merged[1:, 0] != merged[:-1, 0]])
            counts = np.add.reduceat(merged[:, 1], starts)
        packed, beam_ids = merged[starts, 0], merged[starts, 2]
        cells = unpack_cells(packed)

        # Exclude cells holding a return under both the mapping and the evaluator key rule.
        occupied = [pack_cells(snapshot.level, snapshot.indices)]
        for level, width_m in enumerate(sizes_m):
            keys = np.floor(points[:, :2] / width_m).astype(np.int64)
            occupied.append(pack_cells(np.full(n, level, dtype=np.int64), keys))
        allowed = ~np.isin(packed, np.concatenate(occupied))
        base = np.floor(points[~clean, :2] / 0.05).astype(np.int64)
        for level, width_m in enumerate(sizes_m):
            selected = allowed & (cells[:, 0] == level)
            if not np.any(selected) or not len(base):
                continue
            steps = math.ceil(settings.conflict_margin_m / width_m) + 1
            blocked = _near_window(cells[selected, 1:3], base // config.ratios[level], steps)
            allowed[np.flatnonzero(selected)[blocked]] = False
        cells, counts, beam_ids = cells[allowed], counts[allowed], beam_ids[allowed]
        order = np.lexsort((cells[:, 2], cells[:, 1], cells[:, 0]))
        cells, counts, beam_ids = cells[order], counts[order].astype(np.int64), beam_ids[order]
        rejected = max(0, len(cells) - settings.max_free_cells)
        cells, counts, beam_ids = (
            cells[: settings.max_free_cells],
            counts[: settings.max_free_cells],
            beam_ids[: settings.max_free_cells],
        )
        summary = VisibilitySummary(
            VISIBILITY_METHOD,
            float(settings.tau_free_m),
            float(settings.corridor_max_m),
            float(settings.conflict_margin_m),
            settings.max_free_cells,
            len(beams),
            len(cells),
            int(np.count_nonzero(occupancy == Occupancy.OCCUPIED)),
            int(np.count_nonzero(occupancy == Occupancy.AMBIGUOUS)),
            int(np.count_nonzero(occupancy == Occupancy.UNKNOWN)),
            rejected,
            deskew_status,
        )
        return VisibilityEvidence(
            immutable(occupancy),
            immutable(obstacle_support),
            immutable(np.ascontiguousarray(cells[:, 0], dtype=np.int64)),
            immutable(np.ascontiguousarray(cells[:, 1:3], dtype=np.int64)),
            immutable(counts.astype(np.int64)),
            immutable(beam_ids.astype(np.int64)),
            summary,
        )
