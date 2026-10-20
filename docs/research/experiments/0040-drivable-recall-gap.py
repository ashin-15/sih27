"""Why labelled-drivable cells are not judged drivable (experiment 0040).

Run from Drishti-2.5 with the cuda and model extras, same pipeline as experiment 0038.
Labels come from a separate ORACLE source and are used only for scoring. Every fused cell
holding current-scan points whose label majority is road/parking but whose terrain is not
DRIVABLE is attributed to the first failing decision-0011 rule:

- obstacle: the cell is occupied with an obstacle below vehicle clearance;
- semantic: the fused dominant class is not road/parking (split by that class, and by
  whether this scan's FRNet majority in the cell already disagreed with the label);
- step: drivable class but a curb/drop flag (split into edge cells, where a labelled
  4-neighbour is not drivable, and interior cells, where all labelled neighbours are
  drivable, with the step size recorded);
- unknown: ground invalid or no semantic evidence.

Also counts FRNet's per-point predictions for points labelled road/parking.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

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
from drishti.semantics import CLASS_NAMES
from drishti.temporal import TemporalMap, TerrainFlag, TerrainState
from drishti.tracking import CandidateTracker
from drishti.visibility import CurrentScanVisibility

DRIVABLE = (9, 10)


class RecordingTemporalMap(TemporalMap):
    """Keeps the per-cell rise and drop of the last published view, in view order."""

    def update(self, **kwargs):  # type: ignore[no-untyped-def,override]
        self.steps: list[tuple[np.ndarray, np.ndarray]] = []
        return super().update(**kwargs)

    def _steps(self, window, slots):  # type: ignore[no-untyped-def]
        rise, drop = super()._steps(window, slots)
        self.steps.append((rise, drop))
        return rise, drop


def _code(level: np.ndarray, kx: np.ndarray, ky: np.ndarray) -> np.ndarray:
    offset = 1 << 28
    return (level.astype(np.int64) << 58) | ((kx + offset) << 29) | (ky + offset)


def _truth(label: np.ndarray) -> np.ndarray:
    truth = np.full(len(label), 2, dtype=np.int64)
    truth[np.isin(label, DRIVABLE)] = 0
    truth[np.isin(label, (11, 12, 17))] = 1
    truth[label == 0] = 3
    return truth


def _lookup(
    code_sorted: np.ndarray, cell_order: np.ndarray, code: np.ndarray, target: np.ndarray
) -> np.ndarray:
    """Index of each target code among the published cells, or -1."""
    hit = np.minimum(np.searchsorted(code_sorted, target), len(code) - 1)
    index = cell_order[hit]
    return np.where(code[index] == target, index, -1)


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
    fused_map = RecordingTemporalMap(config)
    engine = MappingEngine(
        config,
        mode=Mode.LEARNED,
        predictor=model,
        detector=ConnectedComponentDetector(device="cuda"),
        tracker=CandidateTracker(),
        visibility=CurrentScanVisibility(device="cuda"),
        temporal=fused_map,
        device="cuda",
    )
    evaluator = InProcessProductEvaluator(audit_every=0)
    learned = DatasetSource(args.dataset, args.sequence, mode=Mode.LEARNED)
    oracle = DatasetSource(args.dataset, args.sequence, mode=Mode.ORACLE)
    reasons: Counter[str] = Counter()
    semantic_class: Counter[str] = Counter()
    by_level: Counter[str] = Counter()
    by_distance: Counter[str] = Counter()
    point_predictions = np.zeros(len(CLASS_NAMES), dtype=np.int64)
    obstacle_height: dict[str, list[float]] = {}
    for name in (
        "obstacle:nonground_on_road_points",
        "obstacle:mixed_cell_other_label",
        "obstacle:history_only",
    ):
        obstacle_height[name] = []
    interior_steps: list[float] = []
    edge_steps: list[float] = []
    drivable_cells = 0
    frames = 0
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
            run_id="exp0040",
            code_revision="0" * 64,
            checkpoint_sha256=model.checkpoint_sha256,
            weights_sha256=model.weights_sha256,
            cell_sizes_cm=config.cell_sizes_cm,
            backend="cuda",
        )
        receipt = engine.receive_tracking(frame, result, product, evaluator)
        if receipt.status != ReceiptStatus.ACCEPTED:
            raise RuntimeError(f"frame {frame.frame_id}: {receipt.error_code}")
        view = result.fused
        assert view is not None
        rise = np.concatenate([item[0] for item in fused_map.steps])
        drop = np.concatenate([item[1] for item in fused_map.steps])
        observations = result.observations
        order = np.argsort(labelled.point_ids)
        position = order[np.searchsorted(labelled.point_ids, observations.point_ids, sorter=order)]
        label = labelled.annotations.semantic[position]
        road_points = np.isin(label, DRIVABLE)
        point_predictions += np.bincount(
            observations.semantic[road_points], minlength=len(CLASS_NAMES)
        )
        sensor = frame.map_from_sensor[:2, 3]
        owners = resolve_owners(observations.points_map_m[:, :2], sensor, config)
        point_code = _code(owners.level, owners.indices[:, 0], owners.indices[:, 1])
        code = _code(view.level, view.indices[:, 0], view.indices[:, 1])
        cell_order = np.argsort(code)
        code_sorted = code[cell_order]
        found = np.minimum(np.searchsorted(code_sorted, point_code), len(code) - 1)
        cell = cell_order[found]
        matched = code[cell] == point_code
        votes = np.zeros((len(code), 4), dtype=np.int64)
        np.add.at(votes, (cell[matched], _truth(label[matched])), 1)
        frnet_votes = np.zeros((len(code), len(CLASS_NAMES)), dtype=np.int64)
        np.add.at(frnet_votes, (cell[matched], observations.semantic[matched]), 1)
        scored = votes.sum(axis=1) > 0
        truth = np.where(scored, votes.argmax(axis=1), -1)
        frnet_majority = frnet_votes.argmax(axis=1)
        # Current non-ground returns per cell, split by their label: road/parking or other.
        nonground = matched & (observations.ground == 2)
        road_label = np.isin(label, DRIVABLE)
        nonground_road = np.bincount(cell[nonground & road_label], minlength=len(code))
        nonground_other = np.bincount(
            cell[nonground & ~road_label & (label != 0)], minlength=len(code)
        )
        parking_votes = np.bincount(cell[matched & (label == 10)], minlength=len(code))
        road_votes = np.bincount(cell[matched & (label == 9)], minlength=len(code))

        neighbour_index = np.column_stack(
            [
                _lookup(
                    code_sorted,
                    cell_order,
                    code,
                    _code(view.level, view.indices[:, 0] + dx, view.indices[:, 1] + dy),
                )
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ]
        )
        neighbours = np.where(neighbour_index >= 0, truth[neighbour_index], -1)
        edge = np.any((neighbours >= 1) & (neighbours <= 2), axis=1)
        target = truth == 0
        drivable_cells += int(np.count_nonzero(target))
        missed = target & (view.terrain != TerrainState.DRIVABLE)
        distance = np.hypot(*(view.centers_xy_m - sensor).T)
        for index in np.flatnonzero(missed):
            terrain = view.terrain[index]
            dominant = int(view.semantic[index])
            if terrain == TerrainState.OBSTACLE:
                if nonground_road[index]:
                    reason = "obstacle:nonground_on_road_points"
                elif nonground_other[index]:
                    reason = "obstacle:mixed_cell_other_label"
                else:
                    reason = "obstacle:history_only"
                if view.ground_valid[index]:
                    obstacle_height[reason].append(
                        float(view.obstacle_low_m[index] - view.ground_height_m[index])
                    )
            elif (
                terrain in (TerrainState.UNKNOWN, TerrainState.STALE)
                or not view.ground_valid[index]
            ):
                reason = "unknown_or_invalid_ground"
            elif dominant not in DRIVABLE:
                current = (
                    "frnet_now_wrong"
                    if frnet_majority[index] not in DRIVABLE
                    else ("frnet_now_right_history_wrong")
                )
                which = "parking" if parking_votes[index] > road_votes[index] else "road"
                reason = f"semantic:{which}:{current}"
                semantic_class[CLASS_NAMES[dominant]] += 1
            elif view.flags[index] & (TerrainFlag.CURB | TerrainFlag.DROP):
                step = float(max(rise[index], drop[index]))
                if edge[index]:
                    reason = "step:labelled_edge"
                    edge_steps.append(step)
                else:
                    reason = "step:interior"
                    interior_steps.append(step)
            else:
                reason = "other"
            reasons[reason] += 1
            by_level[f"{reason}|L{int(view.level[index])}"] += 1
            band = "0-20" if distance[index] < 20 else "20-50" if distance[index] < 50 else "50+"
            by_distance[f"{reason}|{band}"] += 1
        frames += 1
        print(frame.frame_id, int(np.count_nonzero(missed)), flush=True)

    def steps(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        array = np.asarray(values)
        return {
            "count": len(values),
            "p50": float(np.median(array)),
            "p90": float(np.percentile(array, 90)),
            "share_below_0.15m": float(np.mean(array < 0.15)),
            "share_below_0.20m": float(np.mean(array < 0.20)),
        }

    road_total = int(point_predictions.sum())
    report = {
        "sequence": args.sequence,
        "start_frame": args.start_frame,
        "frames": frames,
        "labelled_drivable_cells": drivable_cells,
        "missed": sum(reasons.values()),
        "reasons": dict(reasons.most_common()),
        "reason_share_of_drivable": {
            key: value / drivable_cells for key, value in reasons.most_common()
        },
        "semantic_dominant_class": dict(semantic_class.most_common()),
        "by_level": dict(sorted(by_level.items())),
        "by_distance": dict(sorted(by_distance.items())),
        "obstacle_bottom_above_ground_m": {
            name: (
                {
                    "count": len(values),
                    "p10": float(np.percentile(values, 10)),
                    "p50": float(np.median(values)),
                    "p90": float(np.percentile(values, 90)),
                }
                if values
                else None
            )
            for name, values in obstacle_height.items()
        },
        "interior_step_m": steps(interior_steps),
        "edge_step_m": steps(edge_steps),
        "frnet_on_road_parking_points": {
            CLASS_NAMES[index]: {"points": int(count), "share": float(count / road_total)}
            for index, count in enumerate(point_predictions)
            if count
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
