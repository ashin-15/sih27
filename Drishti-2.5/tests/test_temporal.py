from collections.abc import Sequence
from dataclasses import fields
from typing import Any, Literal

import numpy as np
import pytest

from drishti.config import MappingConfig
from drishti.contracts import make_frame
from drishti.cuda_backend import CudaFramePath
from drishti.ground import GroundClass
from drishti.mapping import resolve_owners
from drishti.pipeline import MappingEngine
from drishti.temporal import (
    FusedMapView,
    FusedOccupancy,
    TemporalMap,
    TemporalSettings,
    TerrainFlag,
    TerrainState,
)

ROAD = 9
SIDEWALK = 11
CAR = 1
SECOND = 1_000_000_000
G = GroundClass.GROUND
N = GroundClass.NONGROUND


@pytest.mark.cuda
def test_cuda_temporal_preserves_full_views_across_motion_and_expiry() -> None:
    if not CudaFramePath.available():
        pytest.skip("CUDA unavailable")
    cpu = TemporalMap(MappingConfig())
    gpu = TemporalMap(MappingConfig(), device="cuda")
    allocated = gpu.device_workspace_bytes
    rng = np.random.default_rng(51)
    for step, sensor_x in enumerate((0.0, 0.0, 31.0, -31.0, 0.0)):
        points = np.column_stack(
            [rng.uniform(-60, 60, (12000, 2)), rng.choice([0.0, 0.15, 1.0, 3.0], 12000)]
        )
        kwargs: dict[str, Any] = dict(
            points_map_m=points,
            ground=rng.choice([G, N], len(points)).astype(np.uint8),
            semantic=rng.choice([0, ROAD, SIDEWALK, CAR], len(points)).astype(np.uint8),
            sensor_xy_m=np.array([sensor_x, 0.0]),
            timestamp_ns=(step + 1) * 3 * SECOND,
            free_level=np.array([0, 0], dtype=np.int64),
            free_indices=np.array([[100, 100], [-100, -100]], dtype=np.int64),
        )
        expected, actual = cpu.update(**kwargs), gpu.update(**kwargs)
        for field in fields(expected):
            left, right = getattr(expected, field.name), getattr(actual, field.name)
            if isinstance(left, np.ndarray):
                assert left.tobytes() == right.tobytes(), field.name
                assert not right.flags.writeable
            else:
                assert left == right
        assert gpu.device_workspace_bytes == allocated
    assert allocated == 48 * max(window.size**2 for window in gpu._windows)


@pytest.mark.cuda
def test_cuda_steps_wrap_variance_and_reused_workspace() -> None:
    if not CudaFramePath.available():
        pytest.skip("CUDA unavailable")
    cpu = TemporalMap(MappingConfig())
    gpu = TemporalMap(MappingConfig(), device="cuda")
    rng = np.random.default_rng(52)
    for window in cpu._windows:
        axis = np.arange(-window.half, window.half + 1, dtype=np.int64)
        keys = np.stack(np.meshgrid(axis, axis, indexing="ij"), axis=-1).reshape(-1, 2)
        slots = window.claim(keys)
        window.height[:] = rng.normal(size=len(slots)).astype(np.float32)
        window.variance[:] = rng.choice([0, np.inf, np.nan, 0.01], len(slots))
        for selected in (slots[::3], slots[-20:], slots[:0]):
            expected = cpu._steps(window, selected)
            actual = gpu._steps(window, selected)
            for left, right in zip(expected, actual, strict=True):
                assert left.tobytes() == right.tobytes()
        window.claim(np.array([[window.size * 3, 0]], dtype=np.int64))
        for left, right in zip(cpu._steps(window, slots), gpu._steps(window, slots), strict=True):
            assert left.tobytes() == right.tobytes()


def _cloud(x: float, y: float, z: float, count: int = 10, spread: float = 0.0) -> np.ndarray:
    offsets = np.linspace(0.005, 0.04, count)
    heights = z + spread * np.linspace(-1, 1, count)
    return np.column_stack([x + offsets, np.full(count, y + 0.02), heights])


def _fuse(
    fused: TemporalMap,
    parts: Sequence[tuple[np.ndarray, int, int]],
    time_ns: int,
    sensor: tuple[float, float] = (0.0, 0.0),
    free: list[tuple[int, int, int]] | None = None,
) -> FusedMapView:
    points = np.vstack([cloud for cloud, _, _ in parts]) if parts else np.empty((0, 3))
    ground = (
        np.concatenate([np.full(len(cloud), cls, dtype=np.uint8) for cloud, cls, _ in parts])
        if parts
        else np.empty(0, dtype=np.uint8)
    )
    semantic = (
        np.concatenate([np.full(len(cloud), sem, dtype=np.uint8) for cloud, _, sem in parts])
        if parts
        else np.empty(0, dtype=np.uint8)
    )
    free_level = free_indices = None
    if free is not None:
        free_level = np.array([item[0] for item in free], dtype=np.int64)
        free_indices = np.array([item[1:] for item in free], dtype=np.int64).reshape(-1, 2)
    return fused.update(
        points_map_m=points,
        ground=ground,
        semantic=semantic,
        sensor_xy_m=np.array(sensor, dtype=np.float64),
        timestamp_ns=time_ns,
        free_level=free_level,
        free_indices=free_indices,
    )


def _cell(view: FusedMapView, level: int, kx: int, ky: int) -> int:
    hits = np.flatnonzero(
        (view.level == level) & (view.indices[:, 0] == kx) & (view.indices[:, 1] == ky)
    )
    assert len(hits) == 1, f"cell {(level, kx, ky)} published {len(hits)} times"
    return int(hits[0])


def test_kalman_elevation_converges_and_resets_on_a_jump() -> None:
    fused = TemporalMap(MappingConfig())
    sigmas = []
    rng = np.random.default_rng(3)
    for step in range(8):
        cloud = _cloud(5.0, 5.0, 0.3 + rng.normal(0, 0.02), spread=0.02)
        view = _fuse(fused, [(cloud, G, ROAD)], (step + 1) * SECOND // 10)
        index = _cell(view, 0, 100, 100)
        sigmas.append(view.ground_sigma_m[index])
        assert view.ground_valid[index]
    # Process noise bounds certainty: sigma falls, then holds at the steady-state value.
    assert all(later <= earlier for earlier, later in zip(sigmas, sigmas[1:], strict=False))
    assert sigmas[-1] < sigmas[0] and sigmas[-1] == pytest.approx(sigmas[-2], rel=1e-6)
    assert abs(view.ground_height_m[index] - 0.3) < 0.05
    jumped = _fuse(fused, [(_cloud(5.0, 5.0, 1.2, spread=0.02), G, ROAD)], SECOND)
    index = _cell(jumped, 0, 100, 100)
    assert jumped.ground_height_m[index] == pytest.approx(1.2, abs=1e-6)
    assert jumped.ground_sigma_m[index] > sigmas[-1]


def test_unobserved_cells_become_stale() -> None:
    fused = TemporalMap(MappingConfig())
    _fuse(fused, [(_cloud(5.0, 5.0, 0.0), G, ROAD)], SECOND)
    fresh = _fuse(fused, [(_cloud(6.0, 5.0, 0.0), G, ROAD)], 2 * SECOND)
    assert fresh.terrain[_cell(fresh, 0, 100, 100)] == TerrainState.DRIVABLE
    later = _fuse(fused, [(_cloud(6.0, 5.0, 0.0), G, ROAD)], 3 * SECOND + 1)
    index = _cell(later, 0, 100, 100)
    assert later.terrain[index] == TerrainState.STALE
    assert later.occupancy[index] == FusedOccupancy.STALE
    assert later.terrain[_cell(later, 0, 120, 100)] == TerrainState.DRIVABLE


def test_window_eviction_and_slot_reuse_forget_old_cells() -> None:
    config = MappingConfig()
    fused = TemporalMap(config)
    allocated = fused.allocated_bytes
    _fuse(fused, [(_cloud(5.0, 5.0, 0.0), G, ROAD)], SECOND)
    window = fused._windows[0]
    # Moving the sensor by a whole window puts the key 100 + size in the same slot.
    shift_m = window.size * 0.05
    moved = _fuse(
        fused, [(_cloud(5.0 + shift_m, 5.0, 0.4), N, CAR)], 2 * SECOND, sensor=(shift_m, 0.0)
    )
    index = _cell(moved, 0, 100 + window.size, 100)
    assert moved.observations[index] == 1
    assert not moved.ground_valid[index]
    assert not np.any((moved.level == 0) & (moved.indices[:, 0] == 100))
    back = _fuse(fused, [(_cloud(9.0, 5.0, 0.0), G, ROAD)], 3 * SECOND)
    assert not np.any((back.level == 0) & (back.indices[:, 0] == 100))
    assert fused.allocated_bytes == allocated


def test_ground_only_scans_clear_ghosts_without_claiming_free_space() -> None:
    fused = TemporalMap(MappingConfig())
    car = [(_cloud(5.0, 5.0, 0.0), G, ROAD), (_cloud(5.0, 5.0, 1.0), N, CAR)]
    for step in range(2):
        view = _fuse(fused, car, (step + 1) * SECOND // 10)
    assert view.terrain[_cell(view, 0, 100, 100)] == TerrainState.OBSTACLE
    states = []
    for step in range(2, 8):
        view = _fuse(fused, [(_cloud(5.0, 5.0, 0.0), G, ROAD)], (step + 1) * SECOND // 10)
        states.append(int(view.occupancy[_cell(view, 0, 100, 100)]))
    assert states[:4] == [FusedOccupancy.OCCUPIED] * 4
    assert states[4:] == [FusedOccupancy.UNKNOWN] * 2
    assert view.terrain[_cell(view, 0, 100, 100)] == TerrainState.DRIVABLE


def test_free_beams_mark_free_and_a_current_return_wins() -> None:
    fused = TemporalMap(MappingConfig())
    free = [(0, 100, 100)]
    _fuse(fused, [], SECOND // 10, free=free)
    view = _fuse(fused, [], 2 * SECOND // 10, free=free)
    assert view.occupancy[_cell(view, 0, 100, 100)] == FusedOccupancy.FREE
    for step in range(3, 8):
        _fuse(fused, [], step * SECOND // 10, free=free)
    hit = _fuse(fused, [(_cloud(5.0, 5.0, 0.5), N, CAR)], SECOND)
    index = _cell(hit, 0, 100, 100)
    assert hit.occupancy[index] == FusedOccupancy.OCCUPIED
    assert hit.terrain[index] == TerrainState.OBSTACLE


def test_older_free_evidence_cannot_reappear_after_a_newer_hit() -> None:
    fused = TemporalMap(MappingConfig())
    free = [(0, 100, 100)]
    for step in range(1, 6):
        view = _fuse(fused, [], step * SECOND // 10, free=free)
    index = _cell(view, 0, 100, 100)
    assert view.occupancy[index] == FusedOccupancy.FREE

    hit = _fuse(fused, [(_cloud(5.0, 5.0, 0.5), N, CAR)], 6 * SECOND // 10)
    assert hit.occupancy[_cell(hit, 0, 100, 100)] == FusedOccupancy.OCCUPIED
    unobserved = _fuse(fused, [], 7 * SECOND // 10)
    assert unobserved.occupancy[_cell(unobserved, 0, 100, 100)] != FusedOccupancy.FREE


def test_published_cells_never_overlap_after_motion() -> None:
    config = MappingConfig()
    fused = TemporalMap(config)
    rng = np.random.default_rng(7)
    view = None
    for step, sensor_x in enumerate((0.0, 7.0, 31.0)):
        xy = rng.uniform(-60, 60, (4000, 2)) + [sensor_x, 0]
        points = np.column_stack([xy, np.zeros(len(xy))])
        view = fused.update(
            points_map_m=points,
            ground=np.full(len(xy), G, dtype=np.uint8),
            semantic=np.full(len(xy), ROAD, dtype=np.uint8),
            sensor_xy_m=np.array([sensor_x, 0.0]),
            timestamp_ns=(step + 1) * SECOND // 10,
        )
    assert view is not None
    published = {
        (int(level), int(kx), int(ky))
        for level, (kx, ky) in zip(view.level, view.indices, strict=True)
    }
    assert len(published) == len(view.level)
    probes = rng.uniform(-60, 90, (20000, 2))
    base = np.floor(probes / 0.05).astype(np.int64)
    covering = np.zeros(len(probes), dtype=np.int64)
    for level, ratio in enumerate(config.ratios):
        keys = base // ratio
        covering += [(level, int(x), int(y)) in published for x, y in keys]
    assert covering.max() == 1


def test_terrain_states_and_flags() -> None:
    fused = TemporalMap(MappingConfig())
    parts = [
        (_cloud(2.0, 0.0, 0.0), G, ROAD),  # drivable
        (_cloud(2.0, 1.0, 0.02), G, SIDEWALK),  # non-drivable terrain
        (_cloud(2.0, 2.0, 0.0), G, 0),  # unknown semantics: never drivable
        (_cloud(2.0, 3.0, 0.0), G, ROAD),  # obstacle on road
        (_cloud(2.0, 3.0, 1.0), N, CAR),
        (_cloud(2.0, 4.0, 0.0), G, ROAD),  # overhang: high return above road
        (_cloud(2.0, 4.0, 3.0), N, 15),
        (_cloud(4.0, 0.0, 0.0), G, ROAD),  # curb: lower cell beside a 15 cm step
        (_cloud(4.05, 0.0, 0.15), G, ROAD),  # drop: upper cell beside the step
    ]
    view = _fuse(fused, parts, SECOND)
    road = _cell(view, 0, 40, 0)
    assert view.terrain[road] == TerrainState.DRIVABLE and view.flags[road] == 0
    assert view.terrain[_cell(view, 0, 40, 20)] == TerrainState.NON_DRIVABLE
    assert view.terrain[_cell(view, 0, 40, 40)] == TerrainState.UNKNOWN
    obstacle = _cell(view, 0, 40, 60)
    assert view.terrain[obstacle] == TerrainState.OBSTACLE
    assert view.obstacle_low_m[obstacle] == pytest.approx(1.0)
    overhang = _cell(view, 0, 40, 80)
    assert view.terrain[overhang] == TerrainState.DRIVABLE
    assert view.flags[overhang] == TerrainFlag.OVERHANG
    lower, upper = _cell(view, 0, 80, 0), _cell(view, 0, 81, 0)
    assert view.flags[lower] == TerrainFlag.CURB
    assert view.flags[upper] == TerrainFlag.DROP
    assert view.terrain[lower] == view.terrain[upper] == TerrainState.NON_DRIVABLE
    summary = view.summary
    assert summary.published_cells == len(view.level)
    assert summary.curb_cells == summary.drop_cells == summary.overhang_cells == 1
    assert sum(summary.terrain_counts) == len(view.level)
    with pytest.raises(ValueError):
        view.terrain[0] = 0


def test_step_neighbours_cross_toroidal_slot_boundary_without_aliasing() -> None:
    fused = TemporalMap(MappingConfig())
    window = fused._windows[0]
    size = window.size
    lower_key = np.array([[size - 1, 1]], dtype=np.int64)
    upper_key = np.array([[size, 1]], dtype=np.int64)
    lower = window.claim(lower_key)
    upper = window.claim(upper_key)
    window.height[lower] = 0.0
    window.height[upper] = 0.15
    window.variance[np.r_[lower, upper]] = 0.0
    rise, drop = fused._steps(window, np.r_[lower, upper])
    expected_step = float(np.float32(0.15))
    np.testing.assert_array_equal(rise, [expected_step, 0.0])
    np.testing.assert_array_equal(drop, [0.0, expected_step])

    # Reusing the wrapped slot for an unrelated key must not create a neighbour.
    window.claim(np.array([[-1, 1]], dtype=np.int64))
    rise, drop = fused._steps(window, upper)
    np.testing.assert_array_equal(rise, [0.0])
    np.testing.assert_array_equal(drop, [0.0])


def test_invalid_inputs_and_settings_are_rejected() -> None:
    fused = TemporalMap(MappingConfig())
    _fuse(fused, [(_cloud(2.0, 0.0, 0.0), G, ROAD)], SECOND)
    with pytest.raises(ValueError, match="increasing"):
        _fuse(fused, [(_cloud(2.0, 0.0, 0.0), G, ROAD)], SECOND)
    with pytest.raises(ValueError, match="learning IDs"):
        _fuse(fused, [(_cloud(2.0, 0.0, 0.0), G, 20)], 2 * SECOND)
    with pytest.raises(ValueError, match="drivable"):
        TemporalSettings(drivable_classes=(0,))
    with pytest.raises(ValueError, match="ordered"):
        TemporalSettings(free_at=0.5)
    with pytest.raises(ValueError, match="config"):
        MappingEngine(
            MappingConfig(), temporal=TemporalMap(MappingConfig(radii_m=(5.0, 25.0, 100.0)))
        )


def test_engine_publishes_the_fused_layer_on_the_shared_path() -> None:
    engine = MappingEngine(MappingConfig(), temporal=TemporalMap(MappingConfig()))
    points = np.array([[5, 0, -1.73, 0.5], [30, 0, 1, 0.8]], dtype=np.float32)
    first = engine.process(make_frame(points))
    second = engine.process(make_frame(points, frame_id=1, timestamp_s=0.1))
    assert first.fused is not None and second.fused is not None
    assert second.timings.temporal_ms is not None
    assert second.fused.observations.max() == 2
    plain = MappingEngine(MappingConfig()).process(make_frame(points))
    assert plain.fused is None and plain.timings.temporal_ms is None


@pytest.mark.parametrize("footprint", ["radial", "square"])
@pytest.mark.parametrize("device", ["cpu", pytest.param("cuda", marks=pytest.mark.cuda)])
def test_ownership_matches_the_snapshot_rule(
    footprint: Literal["radial", "square"], device: Literal["cpu", "cuda"]
) -> None:
    if device == "cuda" and not CudaFramePath.available():
        pytest.skip("working CUDA required")
    config = MappingConfig(footprint=footprint)
    fused = TemporalMap(config, device=device)
    rng = np.random.default_rng(11)
    sensor = np.array([3.37, -1.81])
    xy = rng.uniform(-110, 110, (50000, 2)) + sensor
    expected = resolve_owners(xy, sensor, config)
    base = np.floor(xy / 0.05).astype(np.int64)
    for level, ratio in enumerate(config.ratios):
        owned = fused._owned(level, base // ratio, sensor)
        np.testing.assert_array_equal(owned, expected.level == level)
