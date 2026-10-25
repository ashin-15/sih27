"""Sequence-owned fused 2.5D map (decision 0011).

Fixed-memory rolling windows per resolution level hold, per cell: a 1D Kalman filter on
ground height, log-odds occupancy with staleness and ghost clearing, decayed semantic
evidence and a drivability verdict. Every accepted point updates its cell at every level,
so each level keeps exact statistics; the published view takes each cell only from the
level that owns it under the current sensor position, so published cells never overlap.
The fused map is evidence, not a navigation guarantee.
"""

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Literal

import numpy as np

from drishti.arrays import BoolArray, ByteArray, FloatArray, IntArray, immutable
from drishti.config import MappingConfig
from drishti.foveation import MAX_STRETCH, FoveationState, forward_block_distance
from drishti.ground import GroundClass
from drishti.semantics import CLASS_NAMES
from drishti.temporal_cuda import CudaTemporalSteps

CLASS_COUNT = len(CLASS_NAMES)
TEMPORAL_METHOD = "rolling-kalman-logodds-v1"
_NO_KEY = np.iinfo(np.int64).min
# Semantic evidence is stored as uint8: per-scan class fractions scaled by this factor and
# decayed each observation, so the steady state scale / (1 - decay) stays within 255.
_SEMANTIC_SCALE = 50


class FusedOccupancy(IntEnum):
    UNKNOWN = 0
    OCCUPIED = 1
    FREE = 2
    STALE = 3


class TerrainState(IntEnum):
    UNKNOWN = 0
    DRIVABLE = 1
    NON_DRIVABLE = 2
    OBSTACLE = 3
    STALE = 4


class TerrainFlag(IntEnum):
    CURB = 1
    DROP = 2
    OVERHANG = 4


@dataclass(frozen=True)
class TemporalSettings:
    stale_after_s: float = 2.0
    log_odds_hit: float = 0.85
    log_odds_miss: float = 0.4
    log_odds_ground_clear: float = 0.2
    log_odds_min: float = -2.0
    log_odds_max: float = 3.5
    occupied_at: float = 0.85
    free_at: float = -0.8
    height_noise_m: float = 0.03
    process_noise_m2_per_s: float = 0.0025
    reset_jump_m: float = 0.5
    valid_sigma_m: float = 0.10
    semantic_decay: float = 0.8
    drivable_classes: tuple[int, ...] = (9, 10)
    step_limit_m: float = 0.10
    clearance_m: float = 2.0

    def __post_init__(self) -> None:
        positive = (
            "stale_after_s",
            "log_odds_hit",
            "log_odds_miss",
            "log_odds_ground_clear",
            "log_odds_max",
            "occupied_at",
            "height_noise_m",
            "process_noise_m2_per_s",
            "reset_jump_m",
            "valid_sigma_m",
            "step_limit_m",
            "clearance_m",
        )
        for name in positive:
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not self.log_odds_min < self.free_at < 0 < self.occupied_at <= self.log_odds_max:
            raise ValueError("log-odds bounds and thresholds must be ordered")
        if not 0 < self.semantic_decay <= 0.8:
            raise ValueError("semantic_decay must lie in (0, 0.8] for uint8 evidence")
        if not self.drivable_classes or any(
            type(value) is not int or not 1 <= value < CLASS_COUNT
            for value in self.drivable_classes
        ):
            raise ValueError("drivable classes must be known learning IDs")


@dataclass(frozen=True)
class FusedMapSummary:
    method: str
    published_cells: int
    terrain_counts: tuple[int, ...]
    occupancy_counts: tuple[int, ...]
    curb_cells: int
    drop_cells: int
    overhang_cells: int
    allocated_bytes: int


@dataclass(frozen=True)
class FusedMapView:
    """Published fused cells for one frame; arrays are aligned and immutable."""

    level: IntArray
    indices: IntArray
    centers_xy_m: FloatArray
    size_m: FloatArray
    ground_height_m: FloatArray
    ground_sigma_m: FloatArray
    ground_valid: BoolArray
    occupancy: ByteArray
    terrain: ByteArray
    flags: ByteArray
    semantic: ByteArray
    obstacle_low_m: FloatArray
    obstacle_high_m: FloatArray
    last_seen_ns: IntArray
    observations: IntArray
    summary: FusedMapSummary


class _Window:
    """One level's toroidal window; a slot holds the cell whose key mod size equals it."""

    def __init__(self, ratio: int, width_m: float, radius_m: float) -> None:
        self.ratio = ratio
        self.width_m = width_m
        self.half = int(math.ceil(radius_m / width_m)) + 1
        self.size = 2 * self.half + 1
        slots = self.size * self.size
        self.key = np.full((slots, 2), _NO_KEY, dtype=np.int64)
        self.last_seen = np.full(slots, -1, dtype=np.int64)
        self.last_hit = np.full(slots, -1, dtype=np.int64)
        self.last_free = np.full(slots, -1, dtype=np.int64)
        self.observations = np.zeros(slots, dtype=np.int32)
        self.log_odds = np.zeros(slots, dtype=np.float32)
        self.height = np.zeros(slots, dtype=np.float32)
        self.variance = np.full(slots, np.inf, dtype=np.float32)
        self.height_ns = np.full(slots, -1, dtype=np.int64)
        self.obstacle_low = np.zeros(slots, dtype=np.float32)
        self.obstacle_high = np.zeros(slots, dtype=np.float32)
        self.semantic = np.zeros((slots, CLASS_COUNT), dtype=np.uint8)
        self.dominant = np.zeros(slots, dtype=np.uint8)
        self.center: tuple[int, int] | None = None

    @property
    def nbytes(self) -> int:
        return sum(value.nbytes for value in vars(self).values() if isinstance(value, np.ndarray))

    def reset(self, slots: IntArray) -> None:
        self.key[slots] = _NO_KEY
        self.last_seen[slots] = -1
        self.last_hit[slots] = -1
        self.last_free[slots] = -1
        self.observations[slots] = 0
        self.log_odds[slots] = 0
        self.height[slots] = 0
        self.variance[slots] = np.inf
        self.height_ns[slots] = -1
        self.obstacle_low[slots] = 0
        self.obstacle_high[slots] = 0
        self.semantic[slots] = 0
        self.dominant[slots] = 0

    def slots(self, keys: IntArray) -> IntArray:
        return np.asarray((keys[:, 0] % self.size) * self.size + keys[:, 1] % self.size)

    def claim(self, keys: IntArray) -> IntArray:
        """Slots for in-window keys, resetting slots that held a different cell."""
        slots = self.slots(keys)
        stored = self.key[slots]
        replaced = (stored[:, 0] != keys[:, 0]) | (stored[:, 1] != keys[:, 1])
        self.reset(slots[replaced])
        self.key[slots] = keys
        return slots

    def evict(self, center: IntArray) -> None:
        position = (int(center[0]), int(center[1]))
        if position == self.center:
            return
        self.center = position
        held = self.key[:, 0] != _NO_KEY
        outside = held & ~self.inside(self.key, center)
        self.reset(np.flatnonzero(outside))

    def inside(self, keys: IntArray, center: IntArray) -> BoolArray:
        return np.asarray(
            (np.abs(keys[:, 0] - center[0]) <= self.half)
            & (np.abs(keys[:, 1] - center[1]) <= self.half),
            dtype=np.bool_,
        )


class TemporalMap:
    """Fused map for one ordered sequence; create a new one for every sequence."""

    def __init__(
        self,
        config: MappingConfig,
        settings: TemporalSettings | None = None,
        *,
        device: Literal["cpu", "cuda"] = "cpu",
    ) -> None:
        if device not in ("cpu", "cuda"):
            raise ValueError("temporal device must be cpu or cuda")
        self.device = device
        self.config = config
        self.foveation: FoveationState | None = None
        self.settings = TemporalSettings() if settings is None else settings
        self._windows = [
            _Window(
                ratio,
                size_cm / 100,
                radius
                * (MAX_STRETCH if config.foveation_enabled and radius < config.radii_m[-1] else 1),
            )
            for ratio, size_cm, radius in zip(
                config.ratios, config.cell_sizes_cm, config.radii_m, strict=True
            )
        ]
        self._last_ns = -1
        self._cuda_steps = (
            CudaTemporalSteps(max(window.size**2 for window in self._windows))
            if device == "cuda"
            else None
        )

    @property
    def allocated_bytes(self) -> int:
        return sum(window.nbytes for window in self._windows)

    @property
    def device_workspace_bytes(self) -> int:
        return self._cuda_steps.allocated_bytes if self._cuda_steps is not None else 0

    def update(
        self,
        *,
        points_map_m: FloatArray,
        ground: ByteArray,
        semantic: ByteArray,
        sensor_xy_m: FloatArray,
        timestamp_ns: int,
        free_level: IntArray | None = None,
        free_indices: IntArray | None = None,
    ) -> FusedMapView:
        """Fuse one scan's accepted points and free cells, then publish the owned view."""
        n = len(points_map_m)
        if (
            points_map_m.shape != (n, 3)
            or ground.shape != (n,)
            or semantic.shape != (n,)
            or not np.isfinite(points_map_m).all()
            or sensor_xy_m.shape != (2,)
            or not np.isfinite(sensor_xy_m).all()
        ):
            raise ValueError("invalid temporal map input")
        if type(timestamp_ns) is not int or timestamp_ns <= self._last_ns:
            raise ValueError("temporal map requires strictly increasing timestamps")
        if np.any(semantic >= CLASS_COUNT):
            raise ValueError("semantic IDs must be learning IDs 0..19")
        settings = self.settings
        base = np.floor(points_map_m[:, :2] / 0.05).astype(np.int64)
        sensor_base = np.floor(sensor_xy_m / 0.05).astype(np.int64)
        for level, window in enumerate(self._windows):
            center = sensor_base // window.ratio
            window.evict(center)
            keys = base // window.ratio
            inside = window.inside(keys, center)
            if np.any(inside):
                self._fuse_points(
                    window,
                    keys[inside],
                    center,
                    ground[inside],
                    points_map_m[inside, 2],
                    semantic[inside],
                    timestamp_ns,
                )
            if free_level is not None and free_indices is not None:
                free = free_indices[free_level == level]
                free = free[window.inside(free, center)] if len(free) else free
                if len(free):
                    slots = window.claim(free.astype(np.int64))
                    window.log_odds[slots] -= settings.log_odds_miss
                    window.last_free[slots] = timestamp_ns
                    window.last_seen[slots] = timestamp_ns
            np.clip(
                window.log_odds,
                settings.log_odds_min,
                settings.log_odds_max,
                out=window.log_odds,
            )
        self._last_ns = timestamp_ns
        return self._view(sensor_xy_m, timestamp_ns)

    def _fuse_points(
        self,
        window: _Window,
        keys: IntArray,
        center: IntArray,
        ground: ByteArray,
        height_m: FloatArray,
        semantic: ByteArray,
        timestamp_ns: int,
    ) -> None:
        settings = self.settings
        span = 2 * window.half + 1
        local = keys - center + window.half
        packed = local[:, 0] * span + local[:, 1]
        # Window-local cell IDs are bounded, so grouping is a counting pass, not a sort.
        occupied = np.bincount(packed, minlength=span * span)
        unique = np.flatnonzero(occupied)
        cells = len(unique)
        counts = occupied[unique]
        lookup = np.empty(span * span, dtype=np.int64)
        lookup[unique] = np.arange(cells)
        inverse = lookup[packed]
        cell_keys = np.column_stack((unique // span, unique % span)) - window.half + center
        slots = window.claim(cell_keys)
        is_ground = ground == GroundClass.GROUND
        ground_height = np.where(is_ground, height_m, 0.0)
        ground_count = np.bincount(inverse, weights=is_ground, minlength=cells)
        ground_sum = np.bincount(inverse, weights=ground_height, minlength=cells)
        ground_square = np.bincount(inverse, weights=ground_height**2, minlength=cells)
        is_obstacle = ground == GroundClass.NONGROUND
        obstacle_count = np.bincount(inverse, weights=is_obstacle, minlength=cells)
        low = np.full(cells, np.inf)
        high = np.full(cells, -np.inf)
        np.minimum.at(low, inverse[is_obstacle], height_m[is_obstacle])
        np.maximum.at(high, inverse[is_obstacle], height_m[is_obstacle])
        classes = np.bincount(
            inverse * CLASS_COUNT + semantic.astype(np.int64), minlength=cells * CLASS_COUNT
        ).reshape(cells, CLASS_COUNT)

        # Ground elevation: scalar Kalman filter per cell, measurement = this scan's mean.
        has_ground = ground_count > 0
        rows = slots[has_ground]
        count = ground_count[has_ground]
        mean = ground_sum[has_ground] / count
        spread = np.maximum(ground_square[has_ground] / count - mean**2, 0.0)
        noise = np.maximum(spread, settings.height_noise_m**2) / count
        previous_ns = window.height_ns[rows]
        elapsed_s = np.where(previous_ns >= 0, (timestamp_ns - previous_ns) / 1e9, 0.0)
        prior = (
            window.variance[rows].astype(np.float64) + settings.process_noise_m2_per_s * elapsed_s
        )
        estimate = window.height[rows].astype(np.float64)
        restart = ~np.isfinite(prior) | (np.abs(mean - estimate) > settings.reset_jump_m)
        safe_prior = np.where(restart, 0.0, prior)
        gain = safe_prior / (safe_prior + noise)
        window.height[rows] = np.where(restart, mean, estimate + gain * (mean - estimate))
        window.variance[rows] = np.where(restart, noise, (1 - gain) * safe_prior)
        window.height_ns[rows] = timestamp_ns

        # Occupancy log-odds: obstacle returns are hits; ground-only scans clear departed
        # objects without claiming free space.
        hit = obstacle_count > 0
        window.log_odds[slots[hit]] += settings.log_odds_hit
        window.last_hit[slots[hit]] = timestamp_ns
        window.obstacle_low[slots[hit]] = low[hit]
        window.obstacle_high[slots[hit]] = high[hit]
        cleared = has_ground & ~hit
        window.log_odds[slots[cleared]] -= settings.log_odds_ground_clear

        evidence = window.semantic[slots].astype(np.float32)
        evidence *= np.float32(settings.semantic_decay)
        fraction = classes.astype(np.float32)
        fraction *= (np.float32(_SEMANTIC_SCALE) / counts.astype(np.float32))[:, None]
        evidence += fraction
        np.rint(evidence, out=evidence)
        np.minimum(evidence, 255, out=evidence)
        window.semantic[slots] = evidence
        known = window.semantic[slots, 1:]
        window.dominant[slots] = np.where(known.max(axis=1) > 0, known.argmax(axis=1) + 1, 0)
        window.last_seen[slots] = timestamp_ns
        window.observations[slots] += 1

    def _steps(self, window: _Window, slots: IntArray) -> tuple[FloatArray, FloatArray]:
        """Largest rise and drop to same-level 4-neighbours with valid ground, per slot."""
        limit = np.float32(self.settings.valid_sigma_m**2)
        if self._cuda_steps is not None:
            return self._cuda_steps.compute(
                window.key, window.height, window.variance, slots, window.size, limit
            )
        size = window.size
        keys = window.key[slots]
        height = window.height[slots].astype(np.float64)
        row, column = np.divmod(slots, size)
        rise = np.zeros(len(slots))
        drop = np.zeros(len(slots))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if dx == 1:
                neighbour = slots + size
                neighbour[row == size - 1] -= size * size
            elif dx == -1:
                neighbour = slots - size
                neighbour[row == 0] += size * size
            elif dy == 1:
                neighbour = slots + 1
                neighbour[column == size - 1] -= size
            else:
                neighbour = slots - 1
                neighbour[column == 0] += size
            target = keys + (dx, dy)
            stored = window.key[neighbour]
            usable = (
                (stored[:, 0] == target[:, 0])
                & (stored[:, 1] == target[:, 1])
                & (window.variance[neighbour] <= limit)
            )
            difference = np.where(usable, window.height[neighbour] - height, 0.0)
            np.maximum(rise, difference, out=rise)
            np.maximum(drop, -difference, out=drop)
        return rise, drop

    def _owned(self, level: int, keys: IntArray, sensor_xy_m: FloatArray) -> BoolArray:
        """Whether ``mapping.resolve_owners`` assigns these level cells to ``level``.

        A cell is owned at its level when every coarser ancestor block was promoted (its
        footprint is nearer than the next finer radius) and the cell itself was not.
        """
        adaptive = self.foveation is not None and self.foveation.stretch > 1
        if self._cuda_steps is not None and not adaptive:
            return self._cuda_steps.owned(level, keys, sensor_xy_m, self.config)
        xp: Any = self._cuda_steps.cp if self._cuda_steps is not None else np
        keys = xp.asarray(keys)
        sensor_xy_m = xp.asarray(sensor_xy_m)
        config = self.config
        ratios = config.ratios
        owned = xp.ones(len(keys), dtype=np.bool_)
        for current in range(level, len(ratios)):
            if current == 0:
                continue
            width_m = config.cell_sizes_cm[current] / 100
            lower_m = ((keys * ratios[level]) // ratios[current]) * width_m
            dx_m = xp.maximum(
                xp.maximum(
                    lower_m[:, 0] - sensor_xy_m[0], sensor_xy_m[0] - (lower_m[:, 0] + width_m)
                ),
                0,
            )
            dy_m = xp.maximum(
                xp.maximum(
                    lower_m[:, 1] - sensor_xy_m[1], sensor_xy_m[1] - (lower_m[:, 1] + width_m)
                ),
                0,
            )
            closest_m = (
                xp.sqrt(dx_m * dx_m + dy_m * dy_m)
                if config.footprint == "radial"
                else xp.maximum(dx_m, dy_m)
            )
            promoted = closest_m < config.radii_m[current - 1]
            if adaptive:
                assert self.foveation is not None
                promoted |= (
                    forward_block_distance(xp, lower_m, width_m, sensor_xy_m, self.foveation)
                    < config.radii_m[current - 1]
                )
            owned &= ~promoted if current == level else promoted
        return np.asarray(xp.asnumpy(owned) if xp is not np else owned, dtype=np.bool_)

    def _view(self, sensor_xy_m: FloatArray, timestamp_ns: int) -> FusedMapView:
        settings = self.settings
        stale_ns = round(settings.stale_after_s * 1e9)
        parts: dict[str, list[Any]] = {}
        for level, window in enumerate(self._windows):
            observed = np.flatnonzero((window.key[:, 0] != _NO_KEY) & (window.last_seen >= 0))
            if not len(observed):
                continue
            slots = observed[self._owned(level, window.key[observed], sensor_xy_m)]
            if not len(slots):
                continue
            rise, drop = self._steps(window, slots)
            sigma = np.sqrt(window.variance[slots].astype(np.float64))
            ground_valid = sigma <= settings.valid_sigma_m
            stale = timestamp_ns - window.last_seen[slots] > stale_ns
            hit_now = window.last_hit[slots] == timestamp_ns
            log_odds = window.log_odds[slots]
            occupied = hit_now | (log_odds >= settings.occupied_at)
            recently_free = (
                (window.last_free[slots] >= 0)
                & (timestamp_ns - window.last_free[slots] <= stale_ns)
                & (window.last_free[slots] > window.last_hit[slots])
            )
            occupancy = np.full(len(slots), FusedOccupancy.UNKNOWN, dtype=np.uint8)
            occupancy[recently_free & (log_odds <= settings.free_at)] = FusedOccupancy.FREE
            occupancy[occupied] = FusedOccupancy.OCCUPIED
            occupancy[stale] = FusedOccupancy.STALE
            semantic = window.dominant[slots]
            height = window.height[slots].astype(np.float64)
            clearance = window.obstacle_low[slots] - height
            blocking = occupied & (~ground_valid | (clearance < settings.clearance_m))
            overhang = occupied & ground_valid & (clearance >= settings.clearance_m)
            curb = ground_valid & (rise > settings.step_limit_m)
            fall = ground_valid & (drop > settings.step_limit_m)
            drivable_class = np.isin(semantic, settings.drivable_classes)
            terrain = np.full(len(slots), TerrainState.UNKNOWN, dtype=np.uint8)
            terrain[ground_valid & (semantic != 0) & ~drivable_class] = TerrainState.NON_DRIVABLE
            terrain[ground_valid & (curb | fall)] = TerrainState.NON_DRIVABLE
            terrain[ground_valid & drivable_class & ~curb & ~fall & ~blocking] = (
                TerrainState.DRIVABLE
            )
            terrain[blocking] = TerrainState.OBSTACLE
            terrain[stale] = TerrainState.STALE
            flags = (
                curb * TerrainFlag.CURB + fall * TerrainFlag.DROP + overhang * TerrainFlag.OVERHANG
            ).astype(np.uint8)
            columns = {
                "level": np.full(len(slots), level, dtype=np.int64),
                "indices": window.key[slots],
                "size_m": np.full(len(slots), window.width_m),
                "ground_height_m": np.where(ground_valid, height, 0.0),
                "ground_sigma_m": np.where(np.isfinite(sigma), sigma, -1.0),
                "ground_valid": ground_valid,
                "occupancy": occupancy,
                "terrain": terrain,
                "flags": flags,
                "semantic": semantic,
                "obstacle_low_m": window.obstacle_low[slots].astype(np.float64),
                "obstacle_high_m": window.obstacle_high[slots].astype(np.float64),
                "last_seen_ns": window.last_seen[slots],
                "observations": window.observations[slots].astype(np.int64),
            }
            for name, values in columns.items():
                parts.setdefault(name, []).append(values)
        empty = {
            "level": np.empty(0, dtype=np.int64),
            "indices": np.empty((0, 2), dtype=np.int64),
            "size_m": np.empty(0),
            "ground_height_m": np.empty(0),
            "ground_sigma_m": np.empty(0),
            "ground_valid": np.empty(0, dtype=np.bool_),
            "occupancy": np.empty(0, dtype=np.uint8),
            "terrain": np.empty(0, dtype=np.uint8),
            "flags": np.empty(0, dtype=np.uint8),
            "semantic": np.empty(0, dtype=np.uint8),
            "obstacle_low_m": np.empty(0),
            "obstacle_high_m": np.empty(0),
            "last_seen_ns": np.empty(0, dtype=np.int64),
            "observations": np.empty(0, dtype=np.int64),
        }
        data: dict[str, Any] = {
            name: np.concatenate(parts[name]) if name in parts else value
            for name, value in empty.items()
        }
        centers = (data["indices"] + 0.5) * data["size_m"][:, None]
        summary = FusedMapSummary(
            TEMPORAL_METHOD,
            len(data["level"]),
            tuple(int(v) for v in np.bincount(data["terrain"], minlength=len(TerrainState))),
            tuple(int(v) for v in np.bincount(data["occupancy"], minlength=len(FusedOccupancy))),
            int(np.count_nonzero(data["flags"] & TerrainFlag.CURB)),
            int(np.count_nonzero(data["flags"] & TerrainFlag.DROP)),
            int(np.count_nonzero(data["flags"] & TerrainFlag.OVERHANG)),
            self.allocated_bytes,
        )
        return FusedMapView(
            level=immutable(data["level"]),
            indices=immutable(np.ascontiguousarray(data["indices"])),
            centers_xy_m=immutable(np.ascontiguousarray(centers)),
            size_m=immutable(data["size_m"]),
            ground_height_m=immutable(data["ground_height_m"]),
            ground_sigma_m=immutable(data["ground_sigma_m"]),
            ground_valid=immutable(data["ground_valid"]),
            occupancy=immutable(data["occupancy"]),
            terrain=immutable(data["terrain"]),
            flags=immutable(data["flags"]),
            semantic=immutable(data["semantic"]),
            obstacle_low_m=immutable(data["obstacle_low_m"]),
            obstacle_high_m=immutable(data["obstacle_high_m"]),
            last_seen_ns=immutable(data["last_seen_ns"]),
            observations=immutable(data["observations"]),
            summary=summary,
        )
