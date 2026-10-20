"""Single-scan versus fused terrain on identical inputs (experiment 0039).

Run from Drishti-2.5 with the cuda and model extras. One learned engine with ``--temporal``
semantics produces the fused view; the same frame's points, ground classes, semantics and
free cells also feed a fresh ``TemporalMap`` (same rules, no history), which is the
single-scan baseline. Labels come from a separate ORACLE source and are used only for
scoring, exactly as in experiment 0038.

Per variant: drivability confusion on cells with current-scan points; frame-to-frame
flicker (cells published in consecutive frames whose drivable verdict flips); coverage
(area within 20 m of the sensor with a drivable or any known verdict); update time.
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
from drishti.temporal import FusedMapView, TemporalMap, TerrainState
from drishti.tracking import CandidateTracker
from drishti.visibility import CurrentScanVisibility

TRUTH = ("drivable", "non-drivable", "obstacle", "unlabelled")
VARIANTS = ("single_scan", "fused")
KNOWN = (TerrainState.DRIVABLE, TerrainState.NON_DRIVABLE, TerrainState.OBSTACLE)


def _truth_class(label: np.ndarray) -> np.ndarray:
    truth = np.full(len(label), 2, dtype=np.int64)
    truth[np.isin(label, (9, 10))] = 0
    truth[np.isin(label, (11, 12, 17))] = 1
    truth[label == 0] = 3
    return truth


def _code(level: np.ndarray, keys: np.ndarray) -> np.ndarray:
    offset = 1 << 28
    return (level.astype(np.int64) << 58) | ((keys[:, 0] + offset) << 29) | (keys[:, 1] + offset)


class _Tally:
    def __init__(self) -> None:
        self.confusion = np.zeros((len(TerrainState), len(TRUTH)), dtype=np.int64)
        self.common = 0
        self.flips = 0
        self.changes = 0
        self.drivable_area: list[float] = []
        self.known_area: list[float] = []
        self.update_ms: list[float] = []
        self.previous: tuple[np.ndarray, np.ndarray] | None = None

    def add(
        self,
        view: FusedMapView,
        point_code: np.ndarray,
        truth: np.ndarray,
        sensor: np.ndarray,
        update_ms: float,
    ) -> None:
        self.update_ms.append(update_ms)
        code = _code(view.level, view.indices)
        order = np.argsort(code)
        code_sorted = code[order]
        found = np.minimum(np.searchsorted(code_sorted, point_code), len(code) - 1)
        cell = order[found]
        matched = code[cell] == point_code
        votes = np.zeros((len(code), len(TRUTH)), dtype=np.int64)
        np.add.at(votes, (cell[matched], truth[matched]), 1)
        scored = votes.sum(axis=1) > 0
        np.add.at(self.confusion, (view.terrain[scored], votes.argmax(axis=1)[scored]), 1)
        terrain_sorted = view.terrain[order]
        if self.previous is not None:
            old_code, old_terrain = self.previous
            _, here, there = np.intersect1d(code_sorted, old_code, return_indices=True)
            now, before = terrain_sorted[here], old_terrain[there]
            self.common += len(here)
            self.changes += int(np.count_nonzero(now != before))
            self.flips += int(
                np.count_nonzero(
                    (now == TerrainState.DRIVABLE) != (before == TerrainState.DRIVABLE)
                )
            )
        self.previous = (code_sorted, terrain_sorted)
        near = np.hypot(*(view.centers_xy_m - sensor).T) < 20.0
        area = view.size_m**2
        self.drivable_area.append(float(area[near & (view.terrain == TerrainState.DRIVABLE)].sum()))
        self.known_area.append(float(area[near & np.isin(view.terrain, KNOWN)].sum()))

    def report(self) -> dict[str, object]:
        matrix = self.confusion
        drivable = TerrainState.DRIVABLE
        predicted = matrix[drivable, :3].sum()
        actual = matrix[:, 0].sum()
        hit = matrix[drivable, 0]
        obstacle = matrix[:, 2].sum()

        def p(values: list[float]) -> dict[str, float]:
            ordered = sorted(values)
            return {
                "p50": statistics.median(ordered),
                "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
                "max": ordered[-1],
            }

        return {
            "confusion_cells": matrix.tolist(),
            "drivable_precision": float(hit / predicted),
            "drivable_recall": float(hit / actual),
            "drivable_iou": float(hit / (predicted + actual - hit)),
            "false_drivable_on_obstacle_cells": float(matrix[drivable, 2] / obstacle),
            "obstacle_recall": float(matrix[TerrainState.OBSTACLE, 2] / obstacle),
            "state_change_rate": self.changes / self.common if self.common else None,
            "drivable_flip_rate": self.flips / self.common if self.common else None,
            "drivable_area_within_20m_m2": p(self.drivable_area),
            "known_area_within_20m_m2": p(self.known_area),
            "update_ms": p(self.update_ms),
        }


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
        device="cuda",
    )
    fused_map = TemporalMap(config)
    evaluator = InProcessProductEvaluator(audit_every=0)
    tallies = {name: _Tally() for name in VARIANTS}
    learned = DatasetSource(args.dataset, args.sequence, mode=Mode.LEARNED)
    oracle = DatasetSource(args.dataset, args.sequence, mode=Mode.ORACLE)
    started = perf_counter()
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
            run_id="exp0039",
            code_revision="0" * 64,
            checkpoint_sha256=model.checkpoint_sha256,
            weights_sha256=model.weights_sha256,
            cell_sizes_cm=config.cell_sizes_cm,
            backend="cuda",
        )
        receipt = engine.receive_tracking(frame, result, product, evaluator)
        if receipt.status != ReceiptStatus.ACCEPTED:
            raise RuntimeError(f"frame {frame.frame_id}: {receipt.error_code}")
        observations = result.observations
        visibility = result.visibility
        assert visibility is not None
        sensor = frame.map_from_sensor[:2, 3].astype(np.float64)
        inputs = {
            "points_map_m": observations.points_map_m,
            "ground": observations.ground,
            "semantic": observations.semantic,
            "sensor_xy_m": sensor,
            "timestamp_ns": round(frame.timestamp_s * 1e9),
            "free_level": visibility.free_level,
            "free_indices": visibility.free_indices,
        }
        single_map = TemporalMap(config)  # allocation excluded from the timed update
        views = {}
        for name, target in (("single_scan", single_map), ("fused", fused_map)):
            tic = perf_counter()
            views[name] = (target.update(**inputs), (perf_counter() - tic) * 1000)
        del single_map
        order = np.argsort(labelled.point_ids)
        position = order[np.searchsorted(labelled.point_ids, observations.point_ids, sorter=order)]
        truth = _truth_class(labelled.annotations.semantic[position])
        owners = resolve_owners(observations.points_map_m[:, :2], sensor, config)
        point_code = _code(owners.level, owners.indices)
        for name, (view, elapsed) in views.items():
            tallies[name].add(view, point_code, truth, sensor, elapsed)
        frames += 1
        print(
            frame.frame_id,
            {name: round(elapsed, 1) for name, (_, elapsed) in views.items()},
            flush=True,
        )
    report = {
        "sequence": args.sequence,
        "start_frame": args.start_frame,
        "frames": frames,
        "wall_s": perf_counter() - started,
        "truth_classes": TRUTH,
        "terrain_states": [state.name for state in TerrainState],
        "variants": {name: tally.report() for name, tally in tallies.items()},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    summary = {
        name: {key: value for key, value in values.items() if key != "confusion_cells"}
        for name, values in report["variants"].items()  # type: ignore[attr-defined]
    }
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
