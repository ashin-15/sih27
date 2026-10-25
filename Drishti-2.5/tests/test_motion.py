from dataclasses import replace

import numpy as np
import pytest

from drishti.motion import MotionEstimator, MotionSettings, MotionView
from drishti.obstacles import InstanceEvidence
from drishti.semantics import Motion
from drishti.tracking import CandidateTracker


def _step(
    estimator: MotionEstimator,
    tracker: CandidateTracker,
    frame: int,
    x: float,
    *,
    observed: bool = True,
    pose_valid: bool = True,
) -> MotionView:
    stamp = frame * 100_000_000
    item = InstanceEvidence(
        0,
        1,
        0.9,
        (x, 0.0, 0.0),
        (x - 0.1, -0.1, -0.1),
        (x + 0.1, 0.1, 0.1),
        (0, 1, 2),
        stamp,
        None,
        "observed",
    )
    instances = (item,) if observed else ()
    update = tracker.prepare("motion", frame, stamp, instances)
    view = estimator.update(
        "motion",
        frame,
        stamp,
        np.array([2, 0, 1, 9], dtype=np.int64),
        instances,
        update.tracks,
        pose_valid=pose_valid,
    )
    tracker.commit(update)
    return view


@pytest.mark.parametrize(
    "speed,expected", [(0.0, Motion.STATIONARY), (0.5, Motion.UNKNOWN), (2.0, Motion.MOVING)]
)
def test_motion_needs_history_and_preserves_point_order(speed: float, expected: Motion) -> None:
    estimator, tracker = MotionEstimator(), CandidateTracker()
    for frame in range(5):
        view = _step(estimator, tracker, frame, 10 + speed * frame / 10)
        assert view.point_state[-1] == Motion.UNKNOWN
        assert not view.point_state.flags.writeable and not view.point_ids.flags.writeable
        if frame < 2:
            assert not view.point_state.any()
            assert view.estimates[0].velocity_map_mps is None
        else:
            np.testing.assert_array_equal(view.point_state[:3], [expected] * 3)
            assert view.estimates[0].velocity_map_mps == pytest.approx((speed, 0.0, 0.0))
        assert all(len(history) <= 3 for history in estimator._history.values())


def test_gap_pose_failure_and_reassociation_clear_motion_history() -> None:
    estimator, tracker = MotionEstimator(), CandidateTracker()
    for frame in range(3):
        _step(estimator, tracker, frame, 10.0)
    missing = _step(estimator, tracker, 3, 10.0, observed=False)
    assert not missing.point_state.any()
    restored = _step(estimator, tracker, 4, 10.0)
    assert restored.estimates[0].observations == 1
    invalid_pose = _step(estimator, tracker, 5, 10.0, pose_valid=False)
    assert invalid_pose.estimates[0].reason == "pose-unverified"
    assert not estimator._history
    jumped = _step(estimator, tracker, 9, 10.0)
    assert not jumped.point_state.any()


def test_motion_rejects_bad_contracts_without_advancing_state() -> None:
    estimator, tracker = MotionEstimator(), CandidateTracker()
    _step(estimator, tracker, 0, 10.0)
    with pytest.raises(ValueError, match="sequence"):
        estimator.update("other", 1, 1, np.empty(0, np.int64), (), ())
    with pytest.raises(ValueError, match="increasing"):
        estimator.update("motion", 0, 0, np.empty(0, np.int64), (), ())
    with pytest.raises(ValueError, match="point IDs"):
        estimator.update("motion", 1, 1, np.array([1, 1], np.int64), (), ())
    with pytest.raises(ValueError, match="thresholds"):
        MotionSettings(moving_min_mps=0.1)
    assert estimator._frame_id == 0
    track = replace(tracker._states[0].evidence, last_observed_ns=100_000_000)
    item = replace(tracker._states[0].observation, point_ids=(100,), observed_ns=100_000_000)
    with pytest.raises(ValueError, match="support"):
        estimator.update("motion", 1, 100_000_000, np.array([0], np.int64), (item,), (track,))
    assert estimator._frame_id == 0
