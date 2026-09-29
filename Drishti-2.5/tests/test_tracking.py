from dataclasses import replace

import numpy as np
import pytest

from drishti.arrays import ByteArray, IntArray, PointArray, immutable
from drishti.cli import main
from drishti.config import MappingConfig
from drishti.contracts import Mode, ScanFrame, make_frame
from drishti.ground import GroundClass
from drishti.learned import SemanticPrediction
from drishti.obstacles import ConnectedComponentDetector, InstanceEvidence
from drishti.pipeline import FrameResult, MappingEngine
from drishti.product_result import (
    InProcessProductEvaluator,
    ProductFrameResult,
    ReceiptStatus,
    canonical_result_digest,
    tracking_product_result,
)
from drishti.tracking import CandidateTracker, TrackingUpdate


def _instance(index: int, y: float, timestamp_ns: int, label: int = 1) -> InstanceEvidence:
    return InstanceEvidence(
        index,
        label,
        0.8,
        (10.0, y, 0.5),
        (9.8, y - 0.2, 0.3),
        (10.2, y + 0.2, 0.7),
        (index * 3, index * 3 + 1, index * 3 + 2),
        timestamp_ns,
        None,
        "observed",
    )


def _step(tracker: CandidateTracker, frame: int, ys: tuple[float, ...]) -> TrackingUpdate:
    timestamp = frame * 100_000_000
    update = tracker.prepare(
        "fixture",
        frame,
        timestamp,
        tuple(_instance(i, y, timestamp) for i, y in enumerate(ys)),
    )
    tracker.commit(update)
    return update


def test_crossing_prediction_and_bounded_support_history() -> None:
    tracker = CandidateTracker()
    for frame, ys in enumerate(((-1.0, 1.0), (-0.4, 0.4), (0.2, -0.2), (0.8, -0.8))):
        update = _step(tracker, frame, ys)
        assert [(t.track_id, t.instance_id) for t in update.tracks] == [(1, 0), (2, 1)]
        assert all(
            t.lifecycle == ("tentative" if frame == 0 else "confirmed") for t in update.tracks
        )
        assert all(
            t.velocity_world_mps is None and t.velocity_covariance is None for t in update.tracks
        )
        assert all(len(t.supporting_frame_ids) <= 2 for t in update.tracks)
    for frame in range(4, 100):
        update = _step(tracker, frame, (0.8, -0.8))
    assert len(update._states) == 2
    assert all(t.supporting_frame_ids == (98, 99) for t in update.tracks)


def test_occlusion_expiry_reappearance_and_tentative_miss() -> None:
    tracker = CandidateTracker()
    _step(tracker, 0, (0.0,))
    _step(tracker, 1, (0.0,))
    assert _step(tracker, 2, ()).tracks[0].lifecycle == "occluded"
    assert _step(tracker, 3, ()).tracks[0].lifecycle == "occluded"
    assert _step(tracker, 4, (0.0,)).tracks[0].track_id == 1
    _step(tracker, 5, ())
    _step(tracker, 6, ())
    assert _step(tracker, 7, ()).tracks[0].lifecycle == "expired"
    reborn = _step(tracker, 8, (0.0,))
    assert [t.track_id for t in reborn.tracks] == [2]
    assert _step(tracker, 9, ()).tracks[0].lifecycle == "expired"
    assert _step(tracker, 10, ()).tracks == ()


def test_capacity_ties_unknowns_reset_and_discard() -> None:
    tracker = CandidateTracker(1)
    prepared = tracker.prepare("fixture", 0, 0, (_instance(0, 0, 0), _instance(1, 2, 0)))
    assert prepared.summary.rejected_instance_ids == (1,)
    with pytest.raises(ValueError, match="pending"):
        tracker.prepare("fixture", 1, 100, ())
    tracker.discard(prepared)
    again = tracker.prepare("fixture", 0, 0, (_instance(0, 0, 0),))
    assert again.tracks[0].track_id == 1
    tracker.commit(again)
    tied = _step(tracker, 1, (0.0, 0.0))
    assert tied.tracks[0].instance_id == 0
    assert tied.summary.rejected_instance_ids == (1,)
    with pytest.raises(ValueError, match="increasing"):
        tracker.prepare("fixture", 1, 0, ())
    with pytest.raises(ValueError, match="sequence"):
        tracker.prepare("other", 2, 200_000_000, ())
    other = CandidateTracker()
    update = other.prepare(
        "other",
        0,
        0,
        (
            _instance(0, 0, 0, 0),
            _instance(1, 2, 0, 11),
            replace(_instance(2, 4, 0), status="ambiguous"),
        ),
    )
    assert update.tracks == ()
    other.commit(update)
    born = other.prepare("other", 1, 100_000_000, (_instance(0, 0, 100_000_000),))
    assert born.tracks[0].track_id == 1


class Things:
    checkpoint_sha256 = "a" * 64
    weights_sha256 = "b" * 64

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction:
        return SemanticPrediction(
            immutable(np.ones(len(points), dtype=np.uint8)),
            immutable(np.full(len(points), 0.8)),
            immutable(np.zeros(len(points), dtype=np.uint8)),
        )

    def close(self) -> None:
        pass


class Nonground:
    method = "authored-tracking-fixture"

    def segment(self, points: PointArray) -> ByteArray:
        return immutable(np.full(len(points), GroundClass.NONGROUND, dtype=np.uint8))


def _engine() -> MappingEngine:
    return MappingEngine(
        MappingConfig(),
        mode=Mode.LEARNED,
        predictor=Things(),
        ground=Nonground(),
        detector=ConnectedComponentDetector(),
        tracker=CandidateTracker(),
    )


def _frame(index: int, *, empty: bool = False) -> ScanFrame:
    angle = 0.05 * index
    pose = np.array(
        [
            [np.cos(angle), -np.sin(angle), 0, index * 0.1],
            [np.sin(angle), np.cos(angle), 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float64,
    )
    world = np.array([[9.8, 0, 0.3], [10.0, 0.1, 0.5], [10.2, 0.2, 0.7]])
    sensor = (world - pose[:3, 3]) @ pose[:3, :3]
    points = np.column_stack((sensor, np.full(3, 0.5))).astype(np.float32)
    return make_frame(
        points[:0] if empty else points,
        sequence="fixture",
        frame_id=index,
        timestamp_s=index * 0.1,
        map_from_sensor=pose,
    )


def _product(frame: ScanFrame, result: FrameResult) -> ProductFrameResult:
    return tracking_product_result(
        frame,
        result,
        run_id="test",
        code_revision="c" * 64,
        checkpoint_sha256="a" * 64,
        weights_sha256="b" * 64,
        cell_sizes_cm=MappingConfig().cell_sizes_cm,
    )


def test_shared_path_ego_pose_pending_transaction_and_lifecycle_evaluator() -> None:
    engine, evaluator = _engine(), InProcessProductEvaluator()
    for index in range(7):
        frame = _frame(index, empty=index in (2, 3, 4, 6))
        result = engine.process(frame)
        product = _product(frame, result)
        with pytest.raises(ValueError, match="pending"):
            engine.process(_frame(index + 1))
        assert canonical_result_digest(product) == canonical_result_digest(product)
        if index == 1:
            invalid = replace(product, tracks=(replace(product.tracks[0], lifecycle="tentative"),))
            assert evaluator.receive(frame, invalid).status == ReceiptStatus.REJECTED
            with pytest.raises(ValueError, match="differs"):
                engine.receive_tracking(frame, result, invalid, evaluator)
        receipt = engine.receive_tracking(frame, result, product, evaluator)
        assert receipt.status == ReceiptStatus.ACCEPTED, receipt.error_code
        assert receipt.schema_version == 4
        expected = (
            "tentative",
            "confirmed",
            "occluded",
            "occluded",
            "expired",
            "tentative",
            "expired",
        )
        assert product.tracks[0].lifecycle == expected[index]
        if index >= 5:
            assert product.tracks[0].track_id == 2
    assert len(evaluator._track_births) == 0
    assert len(evaluator._tracking_previous) == 0


def test_rejected_payload_leaves_tracker_uncommitted_and_engine_requires_replay() -> None:
    engine, evaluator = _engine(), InProcessProductEvaluator()
    frame = _frame(0)
    result = engine.process(frame)
    invalid = replace(_product(frame, result), checkpoint_sha256="bad")
    receipt = engine.receive_tracking(frame, result, invalid, evaluator)
    assert receipt.status == ReceiptStatus.REJECTED
    assert engine.tracker is not None
    retry = engine.tracker.prepare("fixture", 0, 0, result.instances)
    assert retry.tracks[0].track_id == 1
    engine.tracker.discard(retry)
    with pytest.raises(ValueError, match="restart sequence"):
        engine.process(_frame(1))
    assert evaluator._last_frame == -1


def test_tracking_cli_guards() -> None:
    assert main(["demo", "--output", "/tmp/unused-tracking-guard", "--track-obstacles"]) == 1
    with pytest.raises(ValueError, match="requires"):
        MappingEngine(MappingConfig(), tracker=CandidateTracker())
    with pytest.raises(ValueError, match="capacity"):
        CandidateTracker(0)


def test_association_diagnostic_perfect_switch_fragment_and_false_track() -> None:
    from drishti.tracking import TrackEvidence
    from drishti.tracking_evaluation import AssociationEvaluation

    def measure(track_ids: tuple[int | None, ...]) -> dict[str, object]:
        evaluator = AssociationEvaluation()
        point_ids = np.arange(100, dtype=np.int64)
        for index, track_id in enumerate(track_ids):
            instance = replace(_instance(0, 0, index), point_ids=tuple(range(100)))
            tracks = (
                ()
                if track_id is None
                else (TrackEvidence(track_id, 0, 0, index, "confirmed", None, None, 0.8, (index,)),)
            )
            evaluator.add_frame(
                index,
                point_ids,
                np.ones(100, dtype=np.uint8),
                np.ones(100, dtype=np.uint16),
                (instance,),
                tracks,
            )
        report = evaluator.report()["overall"]
        assert isinstance(report, dict)
        return report

    perfect = measure((1, 1, 1))
    assert perfect["association_jaccard"] == 1.0
    assert perfect["tp"] == 3 and perfect["id_switches"] == 0
    switched = measure((1, 2))
    assert switched["id_switches"] == 1 and switched["association_jaccard"] == 0.5
    fragmented = measure((1, None, 1))
    assert fragmented["fragmentations"] == 1 and fragmented["fn"] == 1
    assert fragmented["association_jaccard"] == pytest.approx(2 / 3)


def test_tracking_evaluator_rejects_fabricated_history_motion_ids_and_capacity() -> None:
    engine, evaluator = _engine(), InProcessProductEvaluator()
    frame = _frame(0)
    result = engine.process(frame)
    product = _product(frame, result)
    track = product.tracks[0]
    summary = product.tracking_summary
    assert summary is not None
    invalid = (
        replace(product, tracks=(replace(track, track_id=2),)),
        replace(product, tracks=(replace(track, lifecycle="confirmed"),)),
        replace(product, tracks=(replace(track, supporting_frame_ids=(0, 0)),)),
        replace(product, tracks=(replace(track, velocity_world_mps=(1.0, 0.0, 0.0)),)),
        replace(product, tracks=()),
        replace(product, tracking_summary=replace(summary, capacity=0)),
        replace(product, tracking_summary=replace(summary, rejected_instance_ids=(0,))),
        replace(product, tracks=(track, replace(track, track_id=2))),
    )
    for forged in invalid:
        assert evaluator.receive(frame, forged).status == ReceiptStatus.REJECTED
    assert (
        engine.receive_tracking(frame, result, product, evaluator).status == ReceiptStatus.ACCEPTED
    )
    frame = _frame(1)
    result = engine.process(frame)
    product = _product(frame, result)
    assert product.tracks[0].track_id == 1
    wrong_class = replace(
        product,
        semantic_id=immutable(np.full(len(product.point_ids), 2, dtype=np.uint8)),
        instances=tuple(replace(i, semantic_id=2) for i in product.instances),
    )
    assert evaluator.receive(frame, wrong_class).error_code == "tracking-class-or-time-gate"
    assert (
        engine.receive_tracking(frame, result, product, evaluator).status == ReceiptStatus.ACCEPTED
    )


def test_engine_capacity_and_invalid_pose_are_explicit() -> None:
    engine = _engine()
    engine.tracker = CandidateTracker(1)
    base = _frame(0)
    farther = np.array(base.points_sensor, copy=True)
    farther[:, 0] += 3.0
    frame = make_frame(np.vstack((base.points_sensor, farther)), sequence="fixture")
    result = engine.process(frame)
    product = _product(frame, result)
    assert product.tracking_summary is not None
    assert product.tracking_summary.rejected_instance_ids == (1,)
    evaluator = InProcessProductEvaluator()
    assert (
        engine.receive_tracking(frame, result, product, evaluator).status == ReceiptStatus.ACCEPTED
    )
    with pytest.raises(ValueError):
        make_frame(base.points_sensor, map_from_sensor=np.zeros((4, 4)))
    with pytest.raises(ValueError, match="increasing"):
        engine.process(frame)


def test_invalid_candidates_and_long_gaps_do_not_silently_match() -> None:
    tracker = CandidateTracker()
    with pytest.raises(ValueError, match="invalid tracker"):
        tracker.prepare(
            "fixture", 0, 0, (replace(_instance(0, 0, 0), center_m=(float("nan"), 0, 0)),)
        )
    _step(tracker, 0, (0.0, 2.0))
    update = _step(tracker, 1, (0.0, 2.0))
    assert [t.track_id for t in update.tracks] == [1, 2]
    update = _step(tracker, 12, (0.0, 2.0))
    assert update.summary.frame_gap == 10
    assert [t.lifecycle for t in update.tracks] == [
        "occluded",
        "occluded",
        "tentative",
        "tentative",
    ]
