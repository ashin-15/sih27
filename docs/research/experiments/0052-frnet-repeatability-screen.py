"""Separate FRNet grouping changes from the reference CUDA reduction's repeatability."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from drishti import frnet_model
from drishti.cli import main


def screen():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--frames", type=int, default=3)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    unique = frnet_model.torch.unique
    runtime_group = frnet_model._group_frustum_coordinates
    predict = frnet_model.TorchFRNetPredictor.predict
    records = []

    def grouped(value, *positional, **kwargs):
        # Research-only replacement for the model's six row-grouping calls.
        if not positional and kwargs == {"return_inverse": True, "dim": 0}:
            packed = (value[:, 0] * 64 + value[:, 1]) * 512 + value[:, 2]
            keys, inverse = unique(packed, sorted=True, return_inverse=True)
            coors = frnet_model.torch.stack(
                (keys // (64 * 512), (keys // 512) % 64, keys % 512), dim=1
            )
            return coors, inverse
        return unique(value, *positional, **kwargs)

    # Exhaustive lattice/inverse parity, including duplicate and empty groups.
    torch = frnet_model.torch
    pixels = torch.arange(2 * 64 * 512, dtype=torch.int64, device=args.device)
    coors = torch.stack((pixels // (64 * 512), (pixels // 512) % 64, pixels % 512), dim=1)
    coors = torch.cat((coors.flip(0), coors[::2]))
    for stride in (1, 2, 4, 8):
        strided = coors.clone()
        strided[:, 1:] //= stride
        for values in (strided, strided[:1], strided[:0]):
            expected = unique(values, return_inverse=True, dim=0)
            actual = grouped(values, return_inverse=True, dim=0)
            assert all(torch.equal(a, b) for a, b in zip(expected, actual, strict=True))

    def repeated(self, *values):
        order = ("reference", "current", "current", "reference")
        outputs = {"reference": [], "current": []}
        timings = {"reference": [], "current": []}
        for label in order:
            frnet_model._group_frustum_coordinates = (
                (lambda coors: unique(coors, return_inverse=True, dim=0))
                if label == "reference"
                else (lambda coors: grouped(coors, return_inverse=True, dim=0))
            )
            if args.device == "cuda":
                frnet_model.torch.cuda.synchronize()
            start = perf_counter()
            outputs[label].append(predict(self, *values))
            timings[label].append((perf_counter() - start) * 1000)
        comparisons = {}
        for label, left, right in (
            ("reference_repeat", outputs["reference"][0], outputs["reference"][1]),
            ("current_repeat", outputs["current"][0], outputs["current"][1]),
            ("reference_current", outputs["reference"][1], outputs["current"][1]),
        ):
            delta = np.abs(left.confidence - right.confidence)
            comparisons[label] = {
                "changed_classes": int(np.count_nonzero(left.semantic_id != right.semantic_id)),
                "changed_unknown": int(
                    np.count_nonzero(left.unknown_reason != right.unknown_reason)
                ),
                "changed_confidence": int(np.count_nonzero(delta)),
                "max_confidence_delta": float(delta.max()),
                "p999_confidence_delta": float(np.quantile(delta, 0.999)),
            }
        records.append({"frame": len(records), "timings_ms": timings, "comparisons": comparisons})
        (args.output / "repeatability.json").write_text(
            json.dumps(records, indent=2), encoding="utf-8"
        )
        print(json.dumps(records[-1]), flush=True)
        frnet_model._group_frustum_coordinates = runtime_group
        return outputs["current"][1]

    frnet_model.TorchFRNetPredictor.predict = repeated
    try:
        code = main(
            [
                "replay",
                "--dataset",
                "../data/semantickitti",
                "--sequence",
                "08",
                "--mode",
                "learned",
                "--device",
                args.device,
                "--frnet-runtime",
                "torch",
                "--frnet-checkpoint",
                "../data/frnet-semantickitti_seg.pth",
                "--frnet-checkpoint-sha256",
                "09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e",
                "--max-frames",
                str(args.frames),
                "--view",
                "none",
                "--output",
                str(args.output / "replay"),
            ]
        )
        if code:
            raise RuntimeError(f"replay failed: {code}")
    finally:
        frnet_model._group_frustum_coordinates = runtime_group
        frnet_model.TorchFRNetPredictor.predict = predict


if __name__ == "__main__":
    screen()
