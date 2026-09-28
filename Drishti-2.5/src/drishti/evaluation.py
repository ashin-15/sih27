"""Supplemental semantic quality by range; official sequence scoring stays upstream."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from drishti.semantics import CLASS_NAMES, decode_semantickitti

RANGE_EDGES_M = (0.0, 20.0, 50.0, float("inf"))


def _metrics(confusion: NDArray[np.int64], total: int, unknown: int) -> dict[str, object]:
    valid = confusion.copy()
    valid[:, 0] = 0
    true_positive = np.diag(valid)
    union = valid.sum(axis=0) + valid.sum(axis=1) - true_positive
    iou = np.divide(
        true_positive,
        union,
        out=np.zeros(20, dtype=np.float64),
        where=union > 0,
    )
    labeled = int(valid.sum())
    return {
        "points": total,
        "labeled_points": labeled,
        "unknown_predictions": unknown,
        "unknown_coverage": unknown / total if total else None,
        "miou_19": float(np.mean(iou[1:])) if labeled else None,
        "labeled_point_accuracy": float(np.trace(valid) / labeled) if labeled else None,
        "class_iou": {CLASS_NAMES[index]: float(iou[index]) for index in range(1, 20)},
        "class_union": {CLASS_NAMES[index]: int(union[index]) for index in range(1, 20)},
    }


def evaluate_semantics_by_range(
    dataset: Path,
    predictions: Path,
    sequence: str,
    *,
    allow_partial: bool = False,
) -> dict[str, object]:
    """Score matched prediction files; absent classes contribute zero, as upstream does."""
    if len(sequence) != 2 or not sequence.isdigit():
        raise ValueError("sequence must be a two-digit ID")
    source = dataset / "sequences" / sequence
    label_paths = sorted((source / "labels").glob("*.label"))
    prediction_paths = sorted(
        (predictions / "sequences" / sequence / "predictions").glob("*.label")
    )
    if not label_paths or not prediction_paths:
        raise ValueError("matching ground-truth and prediction files are required")
    labels_by_stem = {path.stem: path for path in label_paths}
    if not allow_partial and {path.stem for path in prediction_paths} != set(labels_by_stem):
        raise ValueError("full evaluation requires one prediction for every labeled scan")
    if any(path.stem not in labels_by_stem for path in prediction_paths):
        raise ValueError("prediction has no matching ground-truth scan")
    confusion = [np.zeros((20, 20), dtype=np.int64) for _ in range(4)]
    point_counts = [0, 0, 0, 0]
    unknown_counts = [0, 0, 0, 0]
    for prediction_path in prediction_paths:
        label_path = labels_by_stem[prediction_path.stem]
        scan_path = source / "velodyne" / f"{prediction_path.stem}.bin"
        packed_true = np.fromfile(label_path, dtype="<u4")
        packed_pred = np.fromfile(prediction_path, dtype="<u4")
        points = np.fromfile(scan_path, dtype="<f4")
        if points.size != packed_true.size * 4 or packed_pred.size != packed_true.size:
            raise ValueError(f"scan, label and prediction counts differ for {prediction_path.stem}")
        true = decode_semantickitti(packed_true).semantic.astype(np.int64)
        pred = decode_semantickitti(packed_pred).semantic.astype(np.int64)
        distances = np.linalg.norm(points.reshape(-1, 4)[:, :3], axis=1)
        if not np.isfinite(distances).all():
            raise ValueError("range evaluation requires finite scan geometry")
        groups = np.searchsorted(RANGE_EDGES_M[1:-1], distances, side="right") + 1
        for group in range(4):
            selected = np.ones(len(true), dtype=np.bool_) if group == 0 else groups == group
            targets = true[selected]
            guesses = pred[selected]
            confusion[group] += np.bincount(guesses * 20 + targets, minlength=400).reshape(20, 20)
            point_counts[group] += len(targets)
            unknown_counts[group] += int(np.count_nonzero(guesses == 0))
    return {
        "schema_version": 1,
        "sequence": sequence,
        "scans": len(prediction_paths),
        "complete_sequence": len(prediction_paths) == len(label_paths),
        "range_edges_m": [0, 20, 50, None],
        "all": _metrics(confusion[0], point_counts[0], unknown_counts[0]),
        "by_range": {
            name: _metrics(confusion[index], point_counts[index], unknown_counts[index])
            for index, name in enumerate(("0-20m", "20-50m", "50m+"), start=1)
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Supplemental SemanticKITTI range metrics")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args(argv)
    report = evaluate_semantics_by_range(
        args.dataset, args.predictions, args.sequence, allow_partial=args.allow_partial
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
