"""Screen CUDA visibility chunk sizes on the same complete current path."""

import argparse
import json
from pathlib import Path

import numpy as np

from drishti import visibility
from drishti.cli import main


def read_frames(directory: Path) -> list[dict]:
    with (directory / "frames.jsonl").open(encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def main_screen() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    checkpoint = "../data/frnet-semantickitti_seg.pth"
    digest = "09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e"
    reports: list[tuple[int, list[dict]]] = []
    for index, chunk_size in enumerate((8192, 16384, 16384, 8192)):
        visibility._BEAM_CHUNK = chunk_size
        directory = args.output / f"run{index}-{chunk_size}"
        result = main(
            [
                "replay",
                "--dataset",
                "../data/semantickitti",
                "--sequence",
                "08",
                "--mode",
                "learned",
                "--device",
                "cuda",
                "--frnet-runtime",
                "torch",
                "--frnet-checkpoint",
                checkpoint,
                "--frnet-checkpoint-sha256",
                digest,
                "--detect-obstacles",
                "--track-obstacles",
                "--visibility",
                "--temporal",
                "--evaluate-product-contract",
                "--audit-every",
                "100",
                "--view",
                "none",
                "--max-frames",
                "6",
                "--output",
                str(directory),
            ]
        )
        if result != 0:
            raise RuntimeError(f"run {index} failed with exit code {result}")
        rows = read_frames(directory)
        reports.append((chunk_size, rows))
        durations = np.array([row["timings_ms"]["visibility_ms"] for row in rows[1:]])
        print(
            f"run={index} chunk={chunk_size} warm_visibility_p50_ms="
            f"{np.median(durations):.3f} warm_visibility_p95_ms={np.percentile(durations, 95):.3f}",
            flush=True,
        )
    reference = reports[0][1]
    fields = ("frame_id", "input_digest", "map_digest", "accounting", "visibility_summary")
    for run, (_, rows) in enumerate(reports[1:], 1):
        if len(rows) != len(reference):
            raise ValueError(f"run {run} frame count differs")
        for frame, (old, new) in enumerate(zip(reference, rows, strict=True)):
            for field in fields:
                if old.get(field) != new.get(field):
                    raise ValueError(f"run {run} frame {frame} differs in {field}")
    print(f"matched={len(reference)} frames across all four runs; fields={','.join(fields)}")


if __name__ == "__main__":
    main_screen()
