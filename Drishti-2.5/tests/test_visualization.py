import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from drishti.arrays import ByteArray, IntArray, PointArray
from drishti.config import MappingConfig
from drishti.contracts import Mode, make_frame
from drishti.ground import GroundClass
from drishti.learned import SemanticPrediction
from drishti.pipeline import FrameResult, MappingEngine
from drishti.semantics import Annotations

pytest.importorskip("rerun")

from drishti.visualization import (
    RerunView,
    cell_geometry,
    semantic_legend_markdown,
    semantic_summary_markdown,
)


@pytest.mark.viewer
def test_recording_contains_actual_cell_sizes_and_a_loadable_blueprint(tmp_path: Path) -> None:
    points = np.array([[5, 0, -1.73, 0.5], [30, 0, 1, 0.8]], dtype=np.float32)
    result = MappingEngine(MappingConfig()).process(make_frame(points))
    geometry = cell_geometry(result.snapshot)
    np.testing.assert_array_equal(geometry.sizes_m[:, :2], [[0.05, 0.05], [0.5, 0.5]])
    np.testing.assert_array_equal(geometry.centers_m[:, :2], result.snapshot.centers_xy_m)
    path = tmp_path / "map.rrd"
    view = RerunView(recording_path=path)
    view.publish(result)
    view.close()
    assert path.stat().st_size > 1000
    verified = subprocess.run(
        ["rerun", "rrd", "verify", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "RUST_LOG": "error"},
    )
    assert verified.returncode == 0, verified.stderr


@pytest.mark.viewer
def test_empty_frame_clears_cell_geometry_without_stale_values(tmp_path: Path) -> None:
    engine = MappingEngine(MappingConfig())
    first = engine.process(make_frame(np.array([[5, 0, -1.73, 0.5]], dtype=np.float32)))
    empty = engine.process(
        make_frame(np.empty((0, 4), dtype=np.float32), frame_id=1, timestamp_s=0.1)
    )
    view = RerunView(recording_path=tmp_path / "empty.rrd")
    view.publish(first)
    view.publish(empty)
    view.close()
    assert cell_geometry(empty.snapshot).sizes_m.shape == (0, 3)


class FlatGround:
    method = "flat-test-fixture"

    def segment(self, points: PointArray) -> ByteArray:
        return np.full(len(points), GroundClass.NONGROUND, dtype=np.uint8)


class SemanticFixturePredictor:
    checkpoint_sha256 = "a" * 64
    weights_sha256 = "b" * 64

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction:
        assert points.shape == (6, 4)
        assert point_ids.tolist() == list(range(6))
        semantic = np.array([1, 2, 1, 1, 2, 0], dtype=np.uint8)
        return SemanticPrediction(
            semantic,
            np.full(len(points), 0.75, dtype=np.float64),
            np.where(semantic == 0, 2, 0).astype(np.uint8),
        )

    def close(self) -> None:
        pass


def _semantic_fixture_result(mode: Mode) -> FrameResult:
    points = np.array(
        [
            [5.01, 0.0, 0.0, 0.5],
            [5.02, 0.0, 0.0, 0.5],
            [5.11, 0.0, 0.0, 0.5],
            [5.12, 0.0, 0.0, 0.5],
            [5.13, 0.0, 0.0, 0.5],
            [5.21, 0.0, 0.0, 0.5],
        ],
        dtype=np.float32,
    )
    annotations = Annotations(
        semantic=np.array([1, 2, 1, 1, 2, 0], dtype=np.uint8),
        motion=np.zeros(len(points), dtype=np.uint8),
        instance=np.zeros(len(points), dtype=np.uint16),
    )
    if mode == Mode.LEARNED:
        engine = MappingEngine(
            MappingConfig(),
            mode=mode,
            predictor=SemanticFixturePredictor(),
            ground=FlatGround(),
        )
        return engine.process(make_frame(points))
    return MappingEngine(MappingConfig(), mode=mode, ground=FlatGround()).process(
        make_frame(points, annotations=annotations if mode == Mode.ORACLE else None)
    )


def test_semantic_dashboard_reports_canonical_classes_and_aggregation_limits() -> None:
    learned = semantic_summary_markdown(_semantic_fixture_result(Mode.LEARNED))
    assert "| 0 | unknown | 1 | 2 |" in learned
    assert "| 1 | car | 3 | 1 |" in learned
    assert "| 2 | bicycle | 2 | 0 |" in learned
    assert "Known-class conflicts: 2 cells." in learned
    assert "Tied class evidence rendered as unknown: 1 cells." in learned

    geometric = semantic_summary_markdown(_semantic_fixture_result(Mode.GEOMETRIC))
    assert "| 0 | unknown | 6 | 3 |" in geometric
    assert "| 1 | car |" not in geometric

    oracle = semantic_summary_markdown(_semantic_fixture_result(Mode.ORACLE))
    assert oracle == learned

    legend = semantic_legend_markdown()
    assert "| 0 | unknown | 145, 151, 160 |" in legend
    assert "| 1 | car | 100, 160, 245 |" in legend
    assert "| 19 | traffic-sign | 235, 195, 70 |" in legend
