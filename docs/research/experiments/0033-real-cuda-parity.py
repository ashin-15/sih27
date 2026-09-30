"""Real-scan CPU/CUDA parity for the full learned path (experiment 0033).

Run from Drishti-2.5 with the cuda and model extras. FRNet runs once per frame on the GPU
and both engines consume that identical semantic output, so map, candidate, tracking and
visibility payloads can be compared exactly. FRNet's own CPU/GPU agreement is measured on
every ``--frnet-cpu-every``-th frame. Labels are never read.
"""

import argparse
import hashlib
import json
import statistics
from dataclasses import fields
from pathlib import Path
from time import perf_counter
from typing import Literal

import numpy as np

from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.frnet_model import TorchFRNetPredictor
from drishti.learned import SemanticPrediction
from drishti.obstacles import ConnectedComponentDetector
from drishti.pipeline import MappingEngine
from drishti.product_result import (
    InProcessProductEvaluator,
    ProductFrameResult,
    ReceiptStatus,
    visibility_product_result,
)
from drishti.tracking import CandidateTracker
from drishti.visibility import CurrentScanVisibility


class SharedPrediction:
    """Serve one GPU FRNet prediction per scan to both engines."""

    def __init__(self, model: TorchFRNetPredictor) -> None:
        self.model = model
        self.checkpoint_sha256 = model.checkpoint_sha256
        self.weights_sha256 = model.weights_sha256
        self._key: bytes | None = None
        self._value: SemanticPrediction | None = None
        self.model_ms: list[float] = []

    def predict(self, points: np.ndarray, point_ids: np.ndarray) -> SemanticPrediction:
        key = hashlib.sha256(points.tobytes() + point_ids.tobytes()).digest()
        if key != self._key or self._value is None:
            started = perf_counter()
            self._value = self.model.predict(points, point_ids)
            self.model_ms.append((perf_counter() - started) * 1000)
            self._key = key
        return self._value

    def close(self) -> None:
        pass


def _engine(device: Literal["cpu", "cuda"], predictor: SharedPrediction) -> MappingEngine:
    return MappingEngine(
        MappingConfig(),
        mode=Mode.LEARNED,
        predictor=predictor,
        detector=ConnectedComponentDetector(device=device),
        tracker=CandidateTracker(),
        visibility=CurrentScanVisibility(device=device),
        device=device,
    )


def _differences(cpu: ProductFrameResult, cuda: ProductFrameResult) -> list[str]:
    names = [
        name
        for name in ("instances", "tracks", "beams", "visibility_summary", "tracking_summary")
        if getattr(cpu, name) != getattr(cuda, name)
    ]
    names += [
        f"cells.{field.name}"
        for field in fields(cpu.cells)
        if not np.array_equal(getattr(cpu.cells, field.name), getattr(cuda.cells, field.name))
    ]
    if cpu.beam_table is not None and cuda.beam_table is not None:
        names += [
            f"beam_table.{field.name}"
            for field in fields(cpu.beam_table)
            if not np.array_equal(
                getattr(cpu.beam_table, field.name), getattr(cuda.beam_table, field.name)
            )
        ]
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--frnet-cpu-every", type=int, default=25)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    gpu_model = TorchFRNetPredictor(
        checkpoint=args.checkpoint, checkpoint_sha256=args.checkpoint_sha256, device="cuda"
    )
    cpu_model = TorchFRNetPredictor(
        checkpoint=args.checkpoint, checkpoint_sha256=args.checkpoint_sha256, device="cpu"
    )
    shared = SharedPrediction(gpu_model)
    engines = {"cpu": _engine("cpu", shared), "cuda": _engine("cuda", shared)}
    evaluators = {"cpu": InProcessProductEvaluator(), "cuda": InProcessProductEvaluator()}
    timings: dict[str, dict[str, list[float]]] = {
        device: {"total": [], "detector": [], "visibility": [], "receipt": []}
        for device in engines
    }
    frames = []
    frnet_agreement = []
    source = DatasetSource(args.dataset, args.sequence, mode=Mode.LEARNED)
    for frame in source.frames(start_frame=args.start_frame, max_frames=args.frames):
        products: dict[str, ProductFrameResult] = {}
        for device, engine in engines.items():
            result = engine.process(frame)
            product = visibility_product_result(
                frame,
                result,
                run_id="exp0033",
                code_revision="0" * 64,
                checkpoint_sha256=shared.checkpoint_sha256,
                weights_sha256=shared.weights_sha256,
                cell_sizes_cm=MappingConfig().cell_sizes_cm,
                backend="cuda" if device == "cuda" else "cpu",
            )
            started = perf_counter()
            receipt = engine.receive_tracking(frame, result, product, evaluators[device])
            if receipt.status != ReceiptStatus.ACCEPTED:
                raise RuntimeError(f"{device} frame {frame.frame_id}: {receipt.error_code}")
            timings[device]["receipt"].append((perf_counter() - started) * 1000)
            timings[device]["total"].append(result.timings.total_ms)
            timings[device]["detector"].append(result.timings.detector_ms or 0.0)
            timings[device]["visibility"].append(result.timings.visibility_ms or 0.0)
            products[device] = product
        differences = _differences(products["cpu"], products["cuda"])
        frames.append(
            {
                "frame_id": frame.frame_id,
                "identical": not differences,
                "differences": differences,
                "free_cells": products["cpu"].visibility_summary.free_cells
                if products["cpu"].visibility_summary
                else None,
                "instances": len(products["cpu"].instances),
            }
        )
        if (frame.frame_id - args.start_frame) % args.frnet_cpu_every == 0:
            gpu = shared.predict(frame.points_sensor, frame.point_ids)
            cpu = cpu_model.predict(frame.points_sensor, frame.point_ids)
            frnet_agreement.append(
                {
                    "frame_id": frame.frame_id,
                    "class_agreement": float(np.mean(gpu.semantic_id == cpu.semantic_id)),
                    "max_confidence_difference": float(
                        np.max(np.abs(gpu.confidence - cpu.confidence))
                    ),
                }
            )
        print(frame.frame_id, "identical" if not differences else differences, flush=True)

    def summary(values: list[float]) -> dict[str, float]:
        ordered = sorted(values)
        return {
            "p50": statistics.median(ordered),
            "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
            "max": ordered[-1],
        }

    report = {
        "sequence": args.sequence,
        "start_frame": args.start_frame,
        "frames": len(frames),
        "identical_frames": sum(item["identical"] for item in frames),
        "frnet_environment": gpu_model.environment,
        "gpu_frnet_ms": summary(shared.model_ms),
        "stage_ms": {
            device: {name: summary(values) for name, values in stages.items()}
            for device, stages in timings.items()
        },
        "frnet_cpu_gpu_agreement": frnet_agreement,
        "per_frame": frames,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({key: report[key] for key in ("frames", "identical_frames")}))


if __name__ == "__main__":
    main()
