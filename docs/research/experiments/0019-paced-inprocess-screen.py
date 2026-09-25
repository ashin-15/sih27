"""Screen the current geometric result under paced replay without in-loop audit I/O."""

import argparse
import hashlib
import json
import resource
from pathlib import Path
from time import perf_counter, sleep

import numpy as np

from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.pipeline import MappingEngine


def percentiles(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(np.max(array)),
    }


def source_digest() -> str:
    digest = hashlib.sha256()
    package = Path(__file__).resolve().parents[3] / "Drishti-2.5/src/drishti"
    for path in sorted(package.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sequence", choices=("00", "08"), required=True)
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frames <= 0:
        parser.error("frames must be positive")
    dataset_root = args.dataset.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    if output == dataset_root or dataset_root in output.parents:
        parser.error("output must be outside the source dataset")

    config = MappingConfig()
    source = DatasetSource(dataset_root, args.sequence, max_points=config.max_points)
    expected = min(args.frames, source.frame_count)
    engine = MappingEngine(config, mode=Mode.GEOMETRIC)
    manifest = {
        "dataset": str(dataset_root),
        "sequence": args.sequence,
        "frames": expected,
        "schedule_hz": 10.0,
        "deadline_ms": 100.0,
        "mode": Mode.GEOMETRIC,
        "source_digest": source_digest(),
        "config_digest": config.digest,
        "dataset_metadata_hashes": source.metadata_hashes,
        "scope": "research-only current geometric result",
        "receipt_event": "same-process current-result sanity check",
        "audit_timing": "JSONL and summary written after paced loop",
    }
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    records: list[dict[str, float | int | bool]] = []
    frames = source.frames(max_frames=expected)
    origin = perf_counter()
    for index in range(expected):
        scheduled = origin + index * 0.1
        sleep(max(0.0, scheduled - perf_counter()))
        load_start = perf_counter()
        frame = next(frames)
        loaded = perf_counter()
        result = engine.process(frame)
        processed = perf_counter()
        if (
            result.snapshot.sequence != frame.sequence
            or result.snapshot.frame_id != frame.frame_id
            or result.accounting.input_points != len(frame.points_sensor)
            or result.accounting.accepted_points != len(result.observations.point_ids)
            or result.observations.cell_indices.shape != (len(result.observations.point_ids),)
        ):
            raise ValueError("current-result identity or point alignment check failed")
        receipt = perf_counter()
        records.append(
            {
                "frame_id": frame.frame_id,
                "points": len(frame.points_sensor),
                "cells": len(result.snapshot.point_count),
                "load_start_lag_ms": (load_start - scheduled) * 1000,
                "load_ms": (loaded - load_start) * 1000,
                "process_ms": (processed - loaded) * 1000,
                "sanity_check_ms": (receipt - processed) * 1000,
                "receipt_age_ms": (receipt - scheduled) * 1000,
                "deadline_missed": receipt - scheduled > 0.1,
            }
        )

    with (output / "frames.jsonl").open("x", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
    ages = [float(record["receipt_age_ms"]) for record in records]
    summary = {
        "status": "completed",
        "frames": len(records),
        "deadline_misses": sum(bool(record["deadline_missed"]) for record in records),
        "receipt_age_ms": percentiles(ages),
        "load_start_lag_ms": percentiles(
            [float(record["load_start_lag_ms"]) for record in records]
        ),
        "process_ms": percentiles([float(record["process_ms"]) for record in records]),
        "sanity_check_ms": percentiles([float(record["sanity_check_ms"]) for record in records]),
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "realtime_release_gate_met": False,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{args.sequence}: {summary['deadline_misses']}/{expected} misses; report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
