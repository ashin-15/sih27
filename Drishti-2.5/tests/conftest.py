from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def dataset_root(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    sequence = root / "sequences" / "08"
    (sequence / "velodyne").mkdir(parents=True)
    (sequence / "labels").mkdir()
    (root / "poses").mkdir()
    calibration = np.array([[0, -1, 0, 0.2], [0, 0, -1, -0.1], [1, 0, 0, 0.3]], float)
    sequence.joinpath("calib.txt").write_text(
        "Tr: " + " ".join(str(value) for value in calibration.ravel()) + "\n", encoding="utf-8"
    )
    poses = np.repeat(np.eye(4)[None], 3, axis=0)
    poses[:, 2, 3] = [0, 0.5, 1.0]
    np.savetxt(sequence / "poses.txt", poses[:, :3].reshape(3, 12))
    np.savetxt(root / "poses" / "08.txt", poses[:, :3].reshape(3, 12))
    np.savetxt(sequence / "times.txt", [0.0, 0.1, 0.21])
    points = np.array([[5.01, 0.01, -1.73, 0.2], [5.02, 0.02, 0.27, 0.8]], dtype="<f4")
    for frame in range(3):
        points.tofile(sequence / "velodyne" / f"{frame:06d}.bin")
        np.array([40, (42 << 16) | 252], dtype="<u4").tofile(
            sequence / "labels" / f"{frame:06d}.label"
        )
    return root
