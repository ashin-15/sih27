"""Fused terrain against SemanticKITTI labels (experiment 0038, decision 0011).

Run from Drishti-2.5 with the cuda and model extras. The learned engine reads a LEARNED
source (no annotations); a second ORACLE source over the same frames supplies labels for
scoring only. For every frame, each published fused cell that holds current-scan points is
scored against the majority label of those points:

- drivable: road, parking;
- non-drivable ground: sidewalk, other-ground, terrain;
- obstacle: every other known class;
- unlabelled: majority unknown (excluded from rates).
"""

import argparse
import json
import statistics
from pathlib import Path
from time import perf_counter

import numpy as np

from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.frnet_model import TorchFRNetPredictor
from drishti.mapping import resolve_owners
from drishti.obstacles import ConnectedComponentDetector
from drishti.pipeline import MappingEngine
from drishti.product_result import (
    InProcessProductEvaluator,
    ReceiptStatus,
    visibility_product_result,
)
from drishti.temporal import TemporalMap, TerrainState
from drishti.tracking import CandidateTracker
from drishti.visibility import CurrentScanVisibility

TRUTH = ("drivable", "non-drivable", "obstacle", "unlabelled")
_GROUND_NON_DRIVABLE = (11, 12, 17)
_DRIVABLE = (9, 10)


def _truth_class(label: np.ndarray) -> np.ndarray:
    truth = np.full(len(label), 2, dtype=np.int64)
    truth[np.isin(label, _DRIVABLE)] = 0
    truth[np.isin(label, _GROUND_NON_DRIVABLE)] = 1
    truth[label == 0] = 3
    return truth


def _code(level: np.ndarray, keys: np.ndarray) -> np.ndarray:
    offset = 1 << 28
    return (level.astype(np.int64) << 58) | ((keys[:, 0] + offset) << 29) | (keys[:, 1] + offset)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    config = MappingConfig()
    model = TorchFRNetPredictor(
        checkpoint=args.checkpoint, checkpoint_sha256=args.checkpoint_sha256, device="cuda"
    )
    engine = MappingEngine(
        config,
        mode=Mode.LEARNED,
        predictor=model,
        detector=ConnectedComponentDetector(device="cuda"),
        tracker=CandidateTracker(),
        visibility=CurrentScanVisibility(device="cuda"),
        temporal=TemporalMap(config),
        device="cuda",
    )
    evaluator = InProcessProductEvaluator(audit_every=0)
    learned = DatasetSource(args.dataset, args.sequence, mode=Mode.LEARNED)
    oracle = DatasetSource(args.dataset, args.sequence, mode=Mode.ORACLE)
    confusion = np.zeros((len(TerrainState), len(TRUTH)), dtype=np.int64)
    by_level = np.zeros((3, len(TerrainState), len(TRUTH)), dtype=np.int64)
    temporal_ms: list[float] = []
    total_ms: list[float] = []
    sigma: list[float] = []
    frames = 0
    started = perf_counter()
    for frame, labelled in zip(
        learned.frames(start_frame=args.start_frame, max_frames=args.frames),
        oracle.frames(start_frame=args.start_frame, max_frames=args.frames),
        strict=True,
    ):
        if frame.frame_id != labelled.frame_id or labelled.annotations is None:
            raise RuntimeError("label source out of step")
        result = engine.process(frame)
        product = visibility_product_result(
            frame,
            result,
            run_id="exp0038",
            code_revision="0" * 64,
            checkpoint_sha256=model.checkpoint_sha256,
            weights_sha256=model.weights_sha256,
            cell_sizes_cm=config.cell_sizes_cm,
            backend="cuda",
        )
        receipt = engine.receive_tracking(frame, result, product, evaluator)
        if receipt.status != ReceiptStatus.ACCEPTED:
            raise RuntimeError(f"frame {frame.frame_id}: {receipt.error_code}")
        fused = result.fused
        assert fused is not None and result.timings.temporal_ms is not None
        temporal_ms.append(result.timings.temporal_ms)
        total_ms.append(result.timings.total_ms)
        # Labels for the accepted points (point IDs index the original scan).
        order = np.argsort(labelled.point_ids)
        position = order[
            np.searchsorted(labelled.point_ids, result.observations.point_ids, sorter=order)
        ]
        label = labelled.annotations.semantic[position]
        points = result.observations.points_map_m
        owners = resolve_owners(points[:, :2], frame.map_from_sensor[:2, 3], config)
        point_code = _code(owners.level, owners.indices)
        cell_code = _code(fused.level, fused.indices)
        cell_order = np.argsort(cell_code)
        found = np.searchsorted(cell_code, point_code, sorter=cell_order)
        found = np.minimum(found, len(cell_code) - 1)
        cell = cell_order[found]
        matched = cell_code[cell] == point_code
        truth_votes = np.zeros((len(cell_code), len(TRUTH)), dtype=np.int64)
        np.add.at(truth_votes, (cell[matched], _truth_class(label[matched])), 1)
        scored = truth_votes.sum(axis=1) > 0
        truth = truth_votes.argmax(axis=1)
        np.add.at(confusion, (fused.terrain[scored], truth[scored]), 1)
        np.add.at(by_level, (fused.level[scored], fused.terrain[scored], truth[scored]), 1)
        valid = fused.ground_valid & scored
        sigma.extend(np.asarray(fused.ground_sigma_m[valid][::50]).tolist())
        frames += 1
        print(frame.frame_id, round(result.timings.temporal_ms, 1), flush=True)

    def rates(matrix: np.ndarray) -> dict[str, float | None]:
        drivable = TerrainState.DRIVABLE
        predicted = matrix[drivable, :3].sum()
        actual = matrix[:, 0].sum()
        hit = matrix[drivable, 0]
        obstacle = matrix[:, 2].sum()
        union = predicted + actual - hit
        return {
            "drivable_precision": float(hit / predicted) if predicted else None,
            "drivable_recall": float(hit / actual) if actual else None,
            "drivable_iou": float(hit / union) if union else None,
            "false_drivable_on_obstacle_cells": float(matrix[drivable, 2] / obstacle)
            if obstacle
            else None,
            "false_drivable_on_non_drivable_ground": float(matrix[drivable, 1] / matrix[:, 1].sum())
            if matrix[:, 1].sum()
            else None,
            "obstacle_recall": float(matrix[TerrainState.OBSTACLE, 2] / obstacle)
            if obstacle
            else None,
        }

    def percentiles(values: list[float]) -> dict[str, float]:
        ordered = sorted(values)
        return {
            "p50": statistics.median(ordered),
            "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
            "max": ordered[-1],
        }

    report = {
        "sequence": args.sequence,
        "start_frame": args.start_frame,
        "frames": frames,
        "wall_s": perf_counter() - started,
        "truth_classes": TRUTH,
        "terrain_states": [state.name for state in TerrainState],
        "confusion_cells": confusion.tolist(),
        "rates": rates(confusion),
        "rates_by_level": {str(level): rates(by_level[level]) for level in range(3)},
        "confusion_by_level": by_level.tolist(),
        "ground_sigma_m_sampled": percentiles(sigma) if sigma else None,
        "temporal_ms": percentiles(temporal_ms),
        "total_ms": percentiles(total_ms),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({key: report[key] for key in ("frames", "rates", "temporal_ms")}, indent=1))


if __name__ == "__main__":
    main()
