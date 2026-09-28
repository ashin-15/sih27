from pathlib import Path

import numpy as np
import pytest

from drishti.evaluation import evaluate_semantics_by_range


def test_semantic_range_metrics_require_complete_predictions(
    dataset_root: Path, tmp_path: Path
) -> None:
    predictions = tmp_path / "predictions/sequences/08/predictions"
    predictions.mkdir(parents=True)
    np.array([40, 10], dtype="<u4").tofile(predictions / "000000.label")
    with pytest.raises(ValueError, match="one prediction for every"):
        evaluate_semantics_by_range(dataset_root, tmp_path / "predictions", "08")
    report = evaluate_semantics_by_range(
        dataset_root, tmp_path / "predictions", "08", allow_partial=True
    )
    assert report["complete_sequence"] is False
    assert report["scans"] == 1
    all_points = report["all"]
    assert isinstance(all_points, dict)
    assert all_points["miou_19"] == pytest.approx(2 / 19)
    assert all_points["labeled_point_accuracy"] == 1.0
    far = report["by_range"]
    assert isinstance(far, dict)
    assert far["50m+"]["miou_19"] is None


def test_semantic_range_metrics_count_unknown_prediction(
    dataset_root: Path, tmp_path: Path
) -> None:
    predictions = tmp_path / "predictions/sequences/08/predictions"
    predictions.mkdir(parents=True)
    for frame in range(3):
        np.array([40, 0], dtype="<u4").tofile(predictions / f"{frame:06d}.label")
    report = evaluate_semantics_by_range(dataset_root, tmp_path / "predictions", "08")
    assert report["complete_sequence"] is True
    all_points = report["all"]
    assert isinstance(all_points, dict)
    assert all_points["unknown_coverage"] == 0.5
    assert all_points["labeled_point_accuracy"] == 0.5
