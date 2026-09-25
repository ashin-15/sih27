"""Screen exact current-slice snapshot serialization on real replay frames."""

import argparse
import hashlib
import json
import os
import resource
from dataclasses import fields
from enum import Enum
from io import BytesIO
from pathlib import Path
from statistics import median
from time import perf_counter
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import numpy as np

from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.mapping import MapSnapshot
from drishti.pipeline import MappingEngine


def source_digest() -> str:
    digest = hashlib.sha256()
    package = Path(__file__).resolve().parents[3] / "Drishti-2.5/src/drishti"
    for path in sorted(package.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def payload(snapshot: MapSnapshot) -> tuple[dict[str, np.ndarray], bytes]:
    arrays: dict[str, np.ndarray] = {}
    metadata: dict[str, str | int | float] = {}
    for field in fields(snapshot):
        value = getattr(snapshot, field.name)
        if isinstance(value, np.ndarray):
            arrays[field.name] = value
        else:
            metadata[field.name] = value.value if isinstance(value, Enum) else value
    encoded = json.dumps(metadata, sort_keys=True, allow_nan=False).encode()
    arrays["__metadata__"] = np.frombuffer(encoded, dtype=np.uint8)
    return arrays, encoded


def verify_roundtrip(encoded: bytes, arrays: dict[str, np.ndarray]) -> None:
    with np.load(BytesIO(encoded), allow_pickle=False) as archive:
        if set(archive.files) != set(arrays):
            raise ValueError("serialized field names differ from the snapshot")
        for name, original in arrays.items():
            loaded = archive[name]
            if (
                loaded.dtype != original.dtype
                or loaded.shape != original.shape
                or loaded.tobytes() != original.tobytes()
            ):
                raise ValueError(f"serialized field differs: {name}")


def percentiles(values: list[float]) -> dict[str, float]:
    ordered = np.asarray(values, dtype=np.float64)
    return {
        "p50": float(median(values)),
        "p95": float(np.percentile(ordered, 95)),
        "max": float(np.max(ordered)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.frames <= 0:
        parser.error("frames must be positive")
    root = args.dataset.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    if output == root or root in output.parents:
        parser.error("output must be outside the source dataset")
    config = MappingConfig()
    source = DatasetSource(root, args.sequence, max_points=config.max_points)
    count = min(args.frames, source.frame_count)
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "scope": "research-only current MapSnapshot arrays and scalar metadata",
                "dataset": str(root),
                "sequence": source.sequence,
                "frames": count,
                "config_digest": config.digest,
                "source_digest": source_digest(),
                "dataset_metadata_hashes": source.metadata_hashes,
                "formats": ["npz-stored", "npz-deflated"],
                "fsync_scope": "file only; directory entry and power-loss recovery untested",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    engine = MappingEngine(config, mode=Mode.GEOMETRIC)
    records: list[dict[str, object]] = []
    samples: dict[str, dict[str, list[float]]] = {
        label: {metric: [] for metric in ("bytes", "encode_ms", "write_ms", "file_fsync_ms")}
        for label in ("stored", "deflated")
    }
    error: str | None = None
    try:
        for frame in source.frames(max_frames=count):
            result = engine.process(frame)
            snapshot = result.snapshot
            arrays, _ = payload(snapshot)
            record: dict[str, object] = {
                "frame_id": frame.frame_id,
                "cells": len(snapshot.point_count),
                "array_bytes": snapshot.array_bytes,
                "snapshot_digest": snapshot.digest,
                "process_ms": result.timings.total_ms,
            }
            for label, compression in (
                ("stored", ZIP_STORED),
                ("deflated", ZIP_DEFLATED),
            ):
                buffer = BytesIO()
                start = perf_counter()
                with ZipFile(buffer, mode="w", compression=compression, compresslevel=6) as archive:
                    for name, array in arrays.items():
                        with archive.open(f"{name}.npy", mode="w") as member:
                            np.lib.format.write_array(member, array, allow_pickle=False)
                encoded = buffer.getvalue()
                encode_ms = (perf_counter() - start) * 1000
                verify_roundtrip(encoded, arrays)
                path = output / f"frame-{frame.frame_id:06d}-{label}.npz"
                write_start = perf_counter()
                with path.open("xb") as stream:
                    stream.write(encoded)
                    write_ms = (perf_counter() - write_start) * 1000
                    flush_start = perf_counter()
                    stream.flush()
                    os.fsync(stream.fileno())
                    fsync_ms = (perf_counter() - flush_start) * 1000
                record[label] = {
                    "bytes": len(encoded),
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                    "encode_ms": encode_ms,
                    "write_ms": write_ms,
                    "file_fsync_ms": fsync_ms,
                    "roundtrip_bit_exact": True,
                }
                for metric, value in (
                    ("bytes", len(encoded)),
                    ("encode_ms", encode_ms),
                    ("write_ms", write_ms),
                    ("file_fsync_ms", fsync_ms),
                ):
                    samples[label][metric].append(float(value))
                if frame.frame_id != 0:
                    path.unlink()
            records.append(record)
    except Exception as exc:
        status = "failed"
        error = str(exc)
    else:
        status = "completed"
        error = None
    with (output / "frames.jsonl").open("x", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    summary = {
        "status": status,
        "error": error,
        "frames": len(records),
        "expected_frames": count,
        "worker_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "formats": {
            label: {metric: percentiles(values) for metric, values in metrics.items()}
            for label, metrics in samples.items()
        }
        if records
        else {},
    }
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{status}: {len(records)}/{count} frames; report: {output}")
    return 0 if status == "completed" and len(records) == count else 1


if __name__ == "__main__":
    raise SystemExit(main())
