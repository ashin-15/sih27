"""Offline T-004 screen using pinned saved FRNet classes and the shared engine path.

Scores are synthetic placeholders because the saved files retain classes only.
They do not affect the connected-component grouping. This script makes no
product receipt or calibrated confidence claim.
"""

import argparse
import importlib
import json
import resource
import sys
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import numpy as np

from drishti.arrays import IntArray, PointArray, immutable
from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.learned import SemanticPrediction
from drishti.obstacles import ConnectedComponentDetector, panoptic_raw_labels
from drishti.pipeline import MappingEngine
from drishti.semantics import LEARNING_TO_RAW, decode_semantickitti

RANGE_EDGES_M = (0.0, 20.0, 50.0, float("inf"))
SIZE_EDGES_POINTS = (50, 200, 1000, 2**63)


def _segment_bin(points: np.ndarray, mask: np.ndarray) -> tuple[int, int]:
    distance = float(np.median(np.linalg.norm(points[mask, :2], axis=1)))
    size = int(np.count_nonzero(mask))
    range_bin = int(np.searchsorted(RANGE_EDGES_M[1:-1], distance, side="right"))
    size_bin = int(np.searchsorted(SIZE_EDGES_POINTS[1:-1], size, side="right"))
    return range_bin, size_bin


def _instance_counts(
    points: np.ndarray,
    pred_sem: np.ndarray,
    pred_instance: np.ndarray,
    gt_sem: np.ndarray,
    gt_instance: np.ndarray,
    counts: np.ndarray,
) -> None:
    """Supplemental 0.5 IoU thing matches by observed range and point count.

    Counts are [class 1..8, range bin, size bin, TP/FP/FN] for nonzero
    instance IDs with at least 50 points. These raw masks intentionally do
    not reproduce the official evaluator's ignore/minimum-point policy.
    """
    for class_id in range(1, 9):
        gt = [
            mask
            for item in np.unique(gt_instance[gt_sem == class_id])
            if item != 0
            if np.count_nonzero(mask := (gt_sem == class_id) & (gt_instance == item)) >= 50
        ]
        pred = [
            mask
            for item in np.unique(pred_instance[pred_sem == class_id])
            if item != 0
            if np.count_nonzero(mask := (pred_sem == class_id) & (pred_instance == item)) >= 50
        ]
        pairs = []
        for gi, ground_mask in enumerate(gt):
            for pi, pred_mask in enumerate(pred):
                intersection = int(np.count_nonzero(ground_mask & pred_mask))
                if intersection:
                    union = int(np.count_nonzero(ground_mask | pred_mask))
                    iou = intersection / union
                    if iou > 0.5:
                        pairs.append((iou, gi, pi))
        matched_gt: set[int] = set()
        matched_pred: set[int] = set()
        for _, gi, pi in sorted(pairs, reverse=True):
            if gi not in matched_gt and pi not in matched_pred:
                matched_gt.add(gi)
                matched_pred.add(pi)
        for gi, mask in enumerate(gt):
            range_bin, size_bin = _segment_bin(points, mask)
            counts[class_id - 1, range_bin, size_bin, 0 if gi in matched_gt else 2] += 1
        for pi, mask in enumerate(pred):
            if pi not in matched_pred:
                range_bin, size_bin = _segment_bin(points, mask)
                counts[class_id - 1, range_bin, size_bin, 1] += 1


class SavedClasses:
    """Read prior point classes in original scan order, never oracle labels."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.frame_id = 0

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction:
        if self.frame_id < 793:
            base = self.root / "replay"
        else:
            base = self.root / "continuation-from-000793"
        path = base / "predictions/sequences/08/predictions" / f"{self.frame_id:06d}.label"
        raw = np.fromfile(path, dtype=np.uint32)
        if len(point_ids) and int(point_ids[-1]) >= len(raw):
            raise ValueError(f"saved prediction point count is too small: {path}")
        semantic = decode_semantickitti(raw).semantic[point_ids]
        if len(semantic) != len(points):
            raise ValueError("saved prediction alignment mismatch")
        self.frame_id += 1
        return SemanticPrediction(
            immutable(semantic),
            immutable(np.where(semantic == 0, 0.0, 1.0).astype(np.float64)),
            immutable(np.where(semantic == 0, 2, 0).astype(np.uint8)),
        )

    def close(self) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--saved-run", type=Path, required=True)
    parser.add_argument("--official-api", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=4071)
    args = parser.parse_args()
    if args.output.exists() or args.max_frames <= 0:
        raise ValueError("output must be new and max-frames positive")
    sys.path.insert(0, str((args.official_api / "auxiliary").resolve()))
    PanopticEval = importlib.import_module("eval_np").PanopticEval

    source = DatasetSource(args.dataset, "08", mode=Mode.ORACLE)
    predictor = SavedClasses(args.saved_run)
    engine = MappingEngine(
        MappingConfig(),
        mode=Mode.LEARNED,
        predictor=predictor,
        detector=ConnectedComponentDetector(),
    )
    evaluator = PanopticEval(20, None, [0], min_points=50)
    frames = 0
    candidates = 0
    detector_ms: list[float] = []
    process_ms: list[float] = []
    stratified_counts = np.zeros((8, 3, 3, 3), dtype=np.int64)
    nonpanoptic_point_counts = np.zeros((2, 3), dtype=np.int64)
    start = perf_counter()
    for frame in source.frames(max_frames=args.max_frames):
        if frame.annotations is None:
            raise ValueError("evaluation frame has no annotations")
        actual = replace(frame, annotations=None)
        result = engine.process(actual)
        pred_raw = panoptic_raw_labels(
            frame.point_ids,
            result.observations.point_ids,
            result.observations.semantic,
            result.instances,
        )
        annotation = frame.annotations
        gt_sem = annotation.semantic.astype(np.int64)
        gt_raw = (annotation.instance.astype(np.uint32) << 16) | LEARNING_TO_RAW[gt_sem]
        pred_sem = decode_semantickitti(pred_raw).semantic.astype(np.int64)
        _instance_counts(
            frame.points_sensor,
            pred_sem,
            pred_raw >> 16,
            gt_sem,
            annotation.instance,
            stratified_counts,
        )
        for index, class_id in enumerate((18, 19)):
            nonpanoptic_point_counts[index] += np.array(
                [
                    np.count_nonzero((pred_sem == class_id) & (gt_sem == class_id)),
                    np.count_nonzero((pred_sem == class_id) & (gt_sem != class_id)),
                    np.count_nonzero((pred_sem != class_id) & (gt_sem == class_id)),
                ]
            )
        evaluator.addBatch(pred_sem, pred_raw, gt_sem, gt_raw)
        frames += 1
        candidates += len(result.instances)
        if result.timings.detector_ms is None:
            raise ValueError("missing detector timing")
        detector_ms.append(result.timings.detector_ms)
        process_ms.append(result.timings.total_ms)
        if frames % 100 == 0:
            print(f"processed {frames}/{args.max_frames}", flush=True)
    pq, sq, rq, per_pq, per_sq, per_rq = evaluator.getPQ()
    report = {
        "scope": "offline-saved-class-t004-candidate-screen",
        "frames": frames,
        "candidates": candidates,
        "panoptic_pq_all_19": float(pq),
        "panoptic_sq_all_19": float(sq),
        "panoptic_rq_all_19": float(rq),
        "panoptic_pq_thing_1_8": float(np.mean(per_pq[1:9])),
        "per_class_pq": per_pq.tolist(),
        "per_class_sq": per_sq.tolist(),
        "per_class_rq": per_rq.tolist(),
        "per_class_tp": evaluator.pan_tp.tolist(),
        "per_class_fp": evaluator.pan_fp.tolist(),
        "per_class_fn": evaluator.pan_fn.tolist(),
        "supplemental_thing_bins": {
            "class_ids": list(range(1, 9)),
            "range_m": ["0-20", "20-50", "50+"],
            "size_points": ["50-199", "200-999", "1000+"],
            "count_order": ["tp", "fp", "fn"],
            "counts": stratified_counts.tolist(),
            "matching": "raw class, nonzero ID, >0.5 IoU, >=50 points each, greedy one-to-one",
        },
        "nonpanoptic_point_counts": {
            "class_ids": [18, 19],
            "count_order": ["tp", "fp", "fn"],
            "counts": nonpanoptic_point_counts.tolist(),
            "scope": "semantic point proxy only; no pole/sign instance or obstacle annotation",
        },
        "detector_ms_p50_p95_p99_max": np.percentile(detector_ms, [50, 95, 99, 100]).tolist(),
        "process_ms_p50_p95_p99_max": np.percentile(process_ms, [50, 95, 99, 100]).tolist(),
        "worker_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "wall_seconds": perf_counter() - start,
        "limits": [
            "saved classes, not new FRNet inference",
            "placeholder scores, no product receipt",
            "oracle annotations supplied only to offline evaluator",
            "ground truth raw class reconstructed from learning ID",
            "supplemental range/size matching does not reproduce official ignore policy",
            "supplemental counts exclude instance ID zero and supports below 50 points",
            "no independent non-panoptic obstacle annotations",
            "not complete product timing",
        ],
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("frames", "panoptic_pq_all_19", "panoptic_pq_thing_1_8", "wall_seconds")
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
