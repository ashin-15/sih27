"""Compare identical synthetic CLI runs with and without diagnostic temporal fusion."""

import argparse
import json
from pathlib import Path

import numpy as np


def records(directory: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (directory / "frames.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def distribution(values: list[float]) -> dict[str, float]:
    samples = np.asarray(values, dtype=np.float64)
    return {
        "p50_ms": float(np.percentile(samples, 50)),
        "p95_ms": float(np.percentile(samples, 95)),
        "max_ms": float(samples.max()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("temporal", type=Path)
    args = parser.parse_args()
    before = records(args.reference)
    after = records(args.temporal)
    if not before or len(before) != len(after):
        raise ValueError("runs need the same nonzero frame count")
    for index, (left, right) in enumerate(zip(before, after, strict=True)):
        for field in (
            "frame_id",
            "timestamp_s",
            "input_digest",
            "map_digest",
            "accounting",
            "cells",
        ):
            if left[field] != right[field]:
                raise ValueError(f"frame {index} differs in {field}")
        if left["temporal_summary"] is not None or right["temporal_summary"] is None:
            raise ValueError(f"frame {index} has unexpected temporal output")

    def stage(rows: list[dict[str, object]], name: str) -> dict[str, float]:
        return distribution([float(row["timings_ms"][name]) for row in rows])

    summaries = [row["temporal_summary"] for row in after]
    allocations = {int(summary["allocated_bytes"]) for summary in summaries}
    report = {
        "frames": len(before),
        "matched_input_map_and_accounting": True,
        "reference_process": stage(before, "total_ms"),
        "temporal_process": stage(after, "total_ms"),
        "temporal_stage": stage(after, "temporal_ms"),
        "temporal_allocation_bytes": sorted(allocations),
        "published_cells_first_last": [
            int(summaries[0]["published_cells"]),
            int(summaries[-1]["published_cells"]),
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
