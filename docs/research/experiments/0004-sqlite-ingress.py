"""Pace real scan files into a durable local SQLite WAL and verify them."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from time import monotonic, perf_counter, sleep, time_ns

import numpy as np


def summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(array.max()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--interval-ms", type=float, default=100.0)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 2 or args.interval_ms <= 0:
        parser.error("require at least two frames and a positive interval")
    dataset = args.dataset.expanduser().resolve(strict=True)
    db = args.db.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    if any(path == dataset or dataset in path.parents for path in (db, report_path)):
        parser.error("outputs must be outside the source dataset")
    if db.exists() or report_path.exists():
        parser.error("choose unused output paths")
    scans = sorted((dataset / "sequences" / args.sequence / "velodyne").glob("*.bin"))
    if len(scans) < args.frames:
        parser.error("not enough scan files")
    scans = scans[: args.frames]
    conn = sqlite3.connect(db)
    try:
        mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        conn.execute("PRAGMA synchronous=FULL")
        sync = conn.execute("PRAGMA synchronous").fetchone()[0]
        if mode != "wal" or sync != 2:
            raise RuntimeError("WAL and FULL synchronous mode are required")
        conn.execute(
            "CREATE TABLE scans ("
            "sequence TEXT NOT NULL, frame_id INTEGER NOT NULL, capture_ns INTEGER NOT NULL, "
            "points INTEGER NOT NULL, sha256 TEXT NOT NULL, payload BLOB NOT NULL, "
            "PRIMARY KEY (sequence, frame_id))"
        )
        read_ms: list[float] = []
        hash_ms: list[float] = []
        commit_ms: list[float] = []
        acquisition_ms: list[float] = []
        start = monotonic()
        for index, path in enumerate(scans):
            due = start + index * args.interval_ms / 1000
            sleep(max(0.0, due - monotonic()))
            began = perf_counter()
            payload = path.read_bytes()
            loaded = perf_counter()
            if len(payload) % 16:
                raise ValueError(f"invalid scan byte length: {path}")
            digest = hashlib.sha256(payload).hexdigest()
            hashed = perf_counter()
            with conn:
                conn.execute(
                    "INSERT INTO scans VALUES (?, ?, ?, ?, ?, ?)",
                    (args.sequence, index, time_ns(), len(payload) // 16, digest, payload),
                )
            committed = perf_counter()
            read_ms.append((loaded - began) * 1000)
            hash_ms.append((hashed - loaded) * 1000)
            commit_ms.append((committed - hashed) * 1000)
            acquisition_ms.append((committed - began) * 1000)
    finally:
        conn.close()
    verified = 0
    with sqlite3.connect(db) as reader:
        rows = reader.execute(
            "SELECT frame_id, points, sha256, payload FROM scans "
            "WHERE sequence=? ORDER BY frame_id",
            (args.sequence,),
        )
        for expected_id, (frame_id, points, digest, payload) in enumerate(rows):
            if frame_id != expected_id or points * 16 != len(payload):
                raise AssertionError("non-contiguous ID or point count mismatch")
            if hashlib.sha256(payload).hexdigest() != digest:
                raise AssertionError("stored payload checksum mismatch")
            if hashlib.sha256(scans[expected_id].read_bytes()).hexdigest() != digest:
                raise AssertionError("stored payload differs from source")
            verified += 1
    if verified != args.frames:
        raise AssertionError("committed scan count mismatch")
    result = {
        "sequence": args.sequence,
        "frames": args.frames,
        "interval_ms": args.interval_ms,
        "journal_mode": mode,
        "synchronous": sync,
        "verified_frames": verified,
        "read_ms": summary(read_ms),
        "hash_ms": summary(hash_ms),
        "commit_ms": summary(commit_ms),
        "acquisition_ms": summary(acquisition_ms),
        "db_bytes": db.stat().st_size,
    }
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
