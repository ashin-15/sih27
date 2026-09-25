"""Measure a paced dataset producer and the current geometric worker independently."""

import argparse
import hashlib
import json
import resource
from dataclasses import asdict, dataclass
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread
from time import perf_counter, sleep

import numpy as np

from drishti.config import MappingConfig
from drishti.contracts import Mode, ScanFrame
from drishti.dataset import DatasetSource
from drishti.pipeline import MappingEngine


@dataclass(frozen=True)
class Arrival:
    frame: ScanFrame
    scheduled_at: float
    load_started_at: float
    loaded_at: float
    queue_was_full: bool


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
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--queue-capacity", type=int, default=2)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.frames <= 0 or args.queue_capacity <= 0:
        parser.error("frames and queue capacity must be positive")
    root = args.dataset.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    if output == root or root in output.parents:
        parser.error("output must be outside the source dataset")
    config = MappingConfig()
    source = DatasetSource(root, args.sequence, max_points=config.max_points)
    expected = min(args.frames, source.frame_count)
    engine = MappingEngine(config, mode=Mode.GEOMETRIC)
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(
        json.dumps(
            {
                "dataset": str(root),
                "sequence": source.sequence,
                "expected_frames": expected,
                "queue_capacity": args.queue_capacity,
                "schedule_hz": 10.0,
                "deadline_ms": 100.0,
                "source_digest": source_digest(),
                "config_digest": config.digest,
                "dataset_metadata_hashes": source.metadata_hashes,
                "scope": "research-only current geometric path",
                "publication_event": "frame-jsonl-flushed-from-python",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    queue: Queue[Arrival] = Queue(maxsize=args.queue_capacity)
    done = Event()
    stop = Event()
    errors: list[Exception] = []
    producer_block_ms: list[float] = []
    origin = perf_counter()

    def produce() -> None:
        frames = source.frames(max_frames=expected)
        try:
            for index in range(expected):
                if stop.is_set():
                    break
                scheduled_at = origin + index * 0.1
                sleep(max(0.0, scheduled_at - perf_counter()))
                load_started_at = perf_counter()
                frame = next(frames)
                loaded_at = perf_counter()
                arrival = Arrival(frame, scheduled_at, load_started_at, loaded_at, False)
                wait_started = perf_counter()
                try:
                    queue.put_nowait(arrival)
                except Full:
                    arrival = Arrival(frame, scheduled_at, load_started_at, loaded_at, True)
                    while not stop.is_set():
                        try:
                            queue.put(arrival, timeout=0.05)
                            break
                        except Full:
                            continue
                producer_block_ms.append((perf_counter() - wait_started) * 1000)
        except Exception as exc:
            errors.append(exc)
        finally:
            done.set()

    producer = Thread(target=produce, name="dataset-producer")
    producer.start()
    ages: list[float] = []
    source_lags: list[float] = []
    worker_lags: list[float] = []
    full_events = 0
    max_queue_depth = 0
    run_error: Exception | None = None
    try:
        with (
            (output / "frames.jsonl").open("x", encoding="utf-8") as frames_stream,
            (output / "timing.jsonl").open("x", encoding="utf-8") as timing_stream,
        ):
            while len(ages) < expected:
                try:
                    arrival = queue.get(timeout=0.1)
                except Empty:
                    if done.is_set() and queue.empty():
                        break
                    continue
                processing_started = perf_counter()
                max_queue_depth = max(max_queue_depth, queue.qsize() + 1)
                result = engine.process(arrival.frame)
                input_hash = hashlib.sha256(arrival.frame.points_sensor.tobytes())
                input_hash.update(arrival.frame.map_from_sensor.tobytes())
                frames_stream.write(
                    json.dumps(
                        {
                            "frame_id": arrival.frame.frame_id,
                            "input_digest": input_hash.hexdigest(),
                            "map_digest": result.snapshot.digest,
                            "cells": len(result.snapshot.point_count),
                            "accounting": asdict(result.accounting),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                frames_stream.flush()
                output_at = perf_counter()
                age_ms = (output_at - arrival.scheduled_at) * 1000
                source_lag_ms = (arrival.load_started_at - arrival.scheduled_at) * 1000
                worker_lag_ms = (processing_started - arrival.scheduled_at) * 1000
                ages.append(age_ms)
                source_lags.append(source_lag_ms)
                worker_lags.append(worker_lag_ms)
                full_events += int(arrival.queue_was_full)
                timing_stream.write(
                    json.dumps(
                        {
                            "frame_id": arrival.frame.frame_id,
                            "scheduled_arrival_offset_ms": (arrival.scheduled_at - origin) * 1000,
                            "producer_load_start_lag_ms": source_lag_ms,
                            "load_ms": (arrival.loaded_at - arrival.load_started_at) * 1000,
                            "worker_start_lag_ms": worker_lag_ms,
                            "post_load_wait_ms": (processing_started - arrival.loaded_at) * 1000,
                            "report_output_age_ms": age_ms,
                            "deadline_missed": age_ms > 100.0,
                            "queue_was_full": arrival.queue_was_full,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                timing_stream.flush()
    except Exception as exc:
        run_error = exc
    finally:
        stop.set()
        producer.join()

    status = "completed" if run_error is None and not errors and len(ages) == expected else "failed"
    summary = {
        "status": status,
        "expected_frames": expected,
        "frames": len(ages),
        "deadline_misses": sum(age > 100.0 for age in ages),
        "queue_full_events": full_events,
        "max_queue_depth_observed": max_queue_depth,
        "output_age_ms": percentiles(ages) if ages else None,
        "producer_load_start_lag_ms": percentiles(source_lags) if source_lags else None,
        "worker_start_lag_ms": percentiles(worker_lags) if worker_lags else None,
        "producer_block_ms": percentiles(producer_block_ms) if producer_block_ms else None,
        "worker_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "realtime_release_gate_met": False,
        "error": str(run_error or errors[0]) if run_error or errors else None,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{status}: {len(ages)}/{expected} frames; report: {output}")
    if status == "failed":
        return 1
    return 2 if summary["deadline_misses"] or full_events else 0


if __name__ == "__main__":
    raise SystemExit(main())
