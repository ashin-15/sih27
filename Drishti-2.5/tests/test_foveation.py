from dataclasses import fields

import numpy as np
import pytest

from drishti.config import MappingConfig
from drishti.cuda_backend import owner_keys
from drishti.foveation import FOVEATION_METHOD, FoveationEstimator, FoveationState
from drishti.mapping import resolve_owners
from drishti.temporal import TemporalMap
from drishti.visibility import CurrentScanVisibility


def test_pose_policy_stops_turns_bounds_and_sequence_reset() -> None:
    estimator = FoveationEstimator()
    assert estimator.update("a", 0, np.zeros(2)).stretch == 1
    assert estimator.update("a", 100_000_000, np.array([1.0, 0.0])).stretch == 2
    assert estimator.update("a", 200_000_000, np.array([1.0, 0.0])).stretch == 1
    turning = estimator.update("a", 300_000_000, np.array([1.0, -1.0]))
    assert turning.heading_xy == (0.0, -1.0)
    with pytest.raises(ValueError):
        estimator.update("b", 400_000_000, np.zeros(2))
    with pytest.raises(ValueError):
        FoveationState(FOVEATION_METHOD, 10, (0.0, 0.0), 2, "pose-derived-uncalibrated")


@pytest.mark.parametrize("heading", [(1.0, 0.0), (0.0, -1.0), (0.6, 0.8)])
def test_refinement_ownership_visibility_and_temporal_agree_on_cuda(
    heading: tuple[float, float],
) -> None:
    cp = pytest.importorskip("cupy")
    try:
        cp.cuda.runtime.getDeviceCount()
    except cp.cuda.runtime.CUDARuntimeError:
        pytest.skip("CUDA device unavailable")
    config = MappingConfig(foveation_enabled=True)
    state = FoveationState(FOVEATION_METHOD, 10, heading, 2, "pose-derived-uncalibrated")
    sensor = np.array([-0.013, 0.017])
    xy = np.random.default_rng(42).uniform(-60, 60, (20000, 2))
    base = resolve_owners(xy, sensor, config)
    refined = resolve_owners(xy, sensor, config, state)
    assert np.all(refined.level <= base.level)
    assert np.any(refined.level < base.level)
    # Blocks entirely behind the heading cannot be refined.
    behind = ((xy - sensor) @ np.asarray(heading)) < -2
    np.testing.assert_array_equal(refined.level[behind], base.level[behind])
    keys = np.column_stack((refined.level, refined.indices))
    np.testing.assert_array_equal(
        cp.asnumpy(owner_keys(cp, cp.asarray(xy), cp.asarray(sensor), config, state)), keys
    )
    cpu, gpu = TemporalMap(config), TemporalMap(config, device="cuda")
    for temporal in (cpu, gpu):
        temporal.foveation = state
        for level in range(len(config.ratios)):
            all_keys = np.unique(np.floor(xy / (config.cell_sizes_cm[level] / 100)), axis=0)
            all_keys = all_keys.astype(np.int64)
            centers = (all_keys + 0.5) * (config.cell_sizes_cm[level] / 100)
            expected = resolve_owners(centers, sensor, config, state).level == level
            np.testing.assert_array_equal(temporal._owned(level, all_keys, sensor), expected)
    # Actual rolling views remain identical after a heading change and stale transition.
    for stamp, current in ((0, state), (100_000_000, None), (3_000_000_000, state)):
        views = []
        for temporal in (cpu, gpu):
            temporal.foveation = current
            views.append(
                temporal.update(
                    points_map_m=np.column_stack((xy[:1000], np.zeros(1000))),
                    ground=np.ones(1000, dtype=np.uint8),
                    semantic=np.full(1000, 9, dtype=np.uint8),
                    sensor_xy_m=sensor,
                    timestamp_ns=stamp,
                )
            )
        for field in fields(views[0]):
            left, right = getattr(views[0], field.name), getattr(views[1], field.name)
            if isinstance(left, np.ndarray):
                assert left.tobytes() == right.tobytes(), field.name
            else:
                assert left == right
    visibility_cpu = CurrentScanVisibility()
    visibility_gpu = CurrentScanVisibility(device="cuda")
    visibility_cpu.foveation = visibility_gpu.foveation = state
    args = (xy[:40], np.arange(40, dtype=np.int64), np.zeros(40), sensor, config)
    np.testing.assert_array_equal(
        visibility_cpu._corridor_pairs(*args), visibility_gpu._corridor_pairs(*args)
    )


def test_disabled_policy_preserves_digest_and_enabled_policy_changes_it() -> None:
    assert MappingConfig().digest == MappingConfig(foveation_enabled=False).digest
    assert MappingConfig().digest != MappingConfig(foveation_enabled=True).digest
