import numpy as np
import pytest

from drishti.arrays import ByteArray, PointArray
from drishti.config import MappingConfig
from drishti.contracts import Mode, make_frame
from drishti.ground import GroundClass
from drishti.pipeline import MappingEngine


class AnalyticGround:
    method = "analytic-test-fixture"

    def segment(self, points: PointArray) -> ByteArray:
        return np.where(points[:, 2] < -1, GroundClass.GROUND, GroundClass.NONGROUND).astype(
            np.uint8
        )


def test_scan_reaches_cells_without_losing_projection_collisions_or_intensity() -> None:
    points = np.array(
        [[5.01, 0.01, -1.73, 0.2], [5.02, 0.01, -1.73, 0.8], [30, 0, 0, np.nan]],
        dtype=np.float32,
    )
    engine = MappingEngine(MappingConfig(), mode=Mode.GEOMETRIC, ground=AnalyticGround())
    result = engine.process(make_frame(points))
    assert result.accounting.accepted_points == 3
    assert result.accounting.projection_collisions == 1
    assert result.accounting.invalid_intensity == 1
    np.testing.assert_array_equal(result.observations.points_sensor, points)
    assert result.observations.point_ids.tolist() == [0, 1, 2]
    cells = result.snapshot
    assert cells.point_count.tolist() == [2, 1]
    assert cells.size_m.tolist() == [0.05, 0.5]
    assert cells.ground_valid.tolist() == [True, False]
    assert cells.ground_height_cm.tolist() == [-173, 0]
    assert cells.semantic.tolist() == [0, 0]
    assert cells.motion.tolist() == [0, 0]
    np.testing.assert_allclose(cells.intensity_mean[0], 0.5)
    assert not cells.intensity_valid[1]
    assert cells.scope == "single-frame"


def test_rejections_balance_and_empty_snapshot_is_valid() -> None:
    config = MappingConfig(max_abs_height_m=10)
    points = np.array(
        [[np.nan, 0, 0, 1], [101, 0, 0, 1], [5, 0, 11, 1], [0, 0, 0, 1]], dtype=np.float32
    )
    result = MappingEngine(config, ground=AnalyticGround()).process(make_frame(points))
    counts = result.accounting
    assert (
        counts.input_points,
        counts.invalid_geometry,
        counts.outside_roi,
        counts.outside_height,
        counts.accepted_points,
    ) == (4, 2, 1, 1, 0)
    assert result.snapshot.point_count.size == 0
    assert len(result.snapshot.digest) == 64


def test_oracle_unknown_and_conflicting_surfaces_remain_explicit() -> None:
    from drishti.semantics import decode_semantickitti

    points = np.array([[5.01, 0, -2, 0.1], [5.02, 0, -1.1, 0.9]], dtype=np.float32)
    labels = decode_semantickitti(np.array([0, 0], dtype=np.uint32))
    frame = make_frame(points, annotations=labels)
    result = MappingEngine(MappingConfig(), mode=Mode.ORACLE, ground=AnalyticGround()).process(
        frame
    )
    assert result.snapshot.semantic.tolist() == [0]
    assert result.snapshot.ambiguous.tolist() == [True]
    assert result.snapshot.ground_valid.tolist() == [False]
    assert result.snapshot.ground_span_cm.tolist() == [90]
    assert result.snapshot.ground_spread_m2[0] == pytest.approx(0.2025)


def test_geometric_outputs_do_not_depend_on_annotations() -> None:
    from drishti.semantics import decode_semantickitti

    points = np.array([[5, 0, 0, 1]], dtype=np.float32)
    labels = decode_semantickitti(np.array([252], dtype=np.uint32))
    first = MappingEngine(MappingConfig(), ground=AnalyticGround()).process(make_frame(points))
    second = MappingEngine(MappingConfig(), ground=AnalyticGround()).process(
        make_frame(points, annotations=labels)
    )
    assert first.snapshot.digest == second.snapshot.digest
    oracle = MappingEngine(MappingConfig(), mode=Mode.ORACLE, ground=AnalyticGround()).process(
        make_frame(points, annotations=labels)
    )
    assert oracle.snapshot.semantic.tolist() == [1]
    assert oracle.snapshot.motion.tolist() == [2]


def test_snapshot_survives_next_frame_and_arrays_cannot_be_mutated() -> None:
    engine = MappingEngine(MappingConfig(), ground=AnalyticGround())
    result = engine.process(make_frame(np.array([[5, 0, -1.73, 1]], dtype=np.float32)))
    digest = result.snapshot.digest
    engine.process(
        make_frame(np.array([[6, 0, 1, 1]], dtype=np.float32), frame_id=1, timestamp_s=0.1)
    )
    assert result.snapshot.digest == digest
    with pytest.raises(ValueError):
        result.snapshot.point_count.setflags(write=True)
    with pytest.raises(ValueError):
        result.observations.points_sensor.setflags(write=True)


def test_engine_rejects_capacity_overflow_and_stream_reuse() -> None:
    points = np.array([[5, 0, -1.73, 1], [6, 0, 0, 1]], dtype=np.float32)
    with pytest.raises(ValueError, match="capacity"):
        MappingEngine(MappingConfig(max_points=1), ground=AnalyticGround()).process(
            make_frame(points)
        )
    engine = MappingEngine(MappingConfig(), ground=AnalyticGround())
    engine.process(make_frame(points))
    with pytest.raises(ValueError, match="increasing"):
        engine.process(make_frame(points))
    with pytest.raises(ValueError, match="stream"):
        engine.process(make_frame(points, sequence="another", frame_id=1, timestamp_s=0.1))


def test_uniform_five_cm_fixture_and_adaptive_reduction_agree_on_evidence() -> None:
    points = np.array([[30.01, 0.01, -2.0, 0.2], [30.11, 0.01, -1.6, 0.8]], dtype=np.float32)
    frame = make_frame(points)
    uniform = (
        MappingEngine(MappingConfig(cell_sizes_cm=(5,), radii_m=(100,)), ground=AnalyticGround())
        .process(frame)
        .snapshot
    )
    adaptive = MappingEngine(MappingConfig(), ground=AnalyticGround()).process(frame).snapshot
    assert uniform.point_count.tolist() == [1, 1]
    assert adaptive.point_count.tolist() == [2]
    assert uniform.ground_height_cm.tolist() == [-200, -160]
    assert adaptive.ground_height_cm.tolist() == [-180]
    assert adaptive.ground_spread_m2.tolist() == pytest.approx([0.04])
    assert adaptive.ground_span_cm.tolist() == [40]
    assert int(uniform.ground_count.sum()) == int(adaptive.ground_count.sum())


@pytest.mark.native
def test_native_engine_replay_is_deterministic_across_stream_instances() -> None:
    from drishti.cli import synthetic_frames

    def replay() -> list[str]:
        engine = MappingEngine(MappingConfig())
        return [
            engine.process(frame).snapshot.digest
            for frame in synthetic_frames(3, 26053, Mode.GEOMETRIC)
        ]

    assert replay() == replay()
