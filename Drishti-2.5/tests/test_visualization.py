import os
import subprocess
from pathlib import Path

import numpy as np
import pytest

from drishti.config import MappingConfig
from drishti.contracts import make_frame
from drishti.pipeline import MappingEngine

pytest.importorskip("rerun")

from drishti.visualization import RerunView, cell_geometry


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
