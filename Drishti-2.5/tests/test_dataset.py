from pathlib import Path

import numpy as np
import pytest

from drishti.contracts import Mode, PoseSource
from drishti.dataset import DatasetSource


def test_replay_preserves_timing_point_order_labels_and_pose(dataset_root: Path) -> None:
    source = DatasetSource(dataset_root, "08", mode=Mode.ORACLE, pose_source=PoseSource.SLAM)
    frames = list(source.frames())
    assert [frame.frame_id for frame in frames] == [0, 1, 2]
    assert [frame.timestamp_s for frame in frames] == [0.0, 0.1, 0.21]
    np.testing.assert_allclose(frames[1].map_from_sensor[:3, 3], [0.5, 0, 0], atol=1e-12)
    assert frames[0].annotations is not None
    assert frames[0].annotations.semantic.tolist() == [9, 1]
    assert frames[0].annotations.instance.tolist() == [0, 42]
    assert frames[0].point_ids.tolist() == [0, 1]
    with pytest.raises(ValueError):
        frames[0].points_sensor.setflags(write=True)


def test_geometric_mode_ignores_corrupt_annotation_files(dataset_root: Path) -> None:
    (dataset_root / "sequences/08/labels/000000.label").write_bytes(b"not labels")
    frames = list(DatasetSource(dataset_root, "08", mode=Mode.GEOMETRIC).frames())
    assert len(frames) == 3
    assert all(frame.annotations is None for frame in frames)


def test_oracle_rejects_point_label_count_mismatch(dataset_root: Path) -> None:
    (dataset_root / "sequences/08/labels/000000.label").write_bytes(b"\0" * 4)
    with pytest.raises(ValueError, match="label.*count"):
        list(DatasetSource(dataset_root, "08", mode=Mode.ORACLE).frames())


def test_dataset_never_silently_falls_back_to_another_pose_source(dataset_root: Path) -> None:
    (dataset_root / "sequences/08/poses.txt").unlink()
    with pytest.raises(FileNotFoundError, match="poses.txt"):
        DatasetSource(dataset_root, "08")


def test_nonmonotonic_timestamps_are_rejected(dataset_root: Path) -> None:
    np.savetxt(dataset_root / "sequences/08/times.txt", [0.0, 0.1, 0.1])
    with pytest.raises(ValueError, match="strictly increasing"):
        DatasetSource(dataset_root, "08")


def test_malformed_scan_cannot_be_reshaped_silently(dataset_root: Path) -> None:
    (dataset_root / "sequences/08/velodyne/000000.bin").write_bytes(b"\0" * 17)
    with pytest.raises(ValueError, match="scan byte"):
        list(DatasetSource(dataset_root, "08").frames())


def test_sequence_identifier_cannot_escape_dataset(dataset_root: Path) -> None:
    with pytest.raises(ValueError, match="sequence"):
        DatasetSource(dataset_root, "../../08")
