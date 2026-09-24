"""Measure current replay stages without modifying the production pipeline."""

import argparse
import cProfile
import hashlib
import io
import json
import pstats
from collections import defaultdict
from pathlib import Path
from statistics import median
from time import perf_counter

import numpy as np

import drishti.mapping as mapping
import drishti.pipeline as pipeline
from drishti.config import load_config
from drishti.contracts import Mode
from drishti.dataset import DatasetSource

parser = argparse.ArgumentParser()
parser.add_argument("--dataset", required=True, type=Path)
parser.add_argument("--sequence", default="08")
parser.add_argument("--frames", default=40, type=int)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
if args.frames < 13:
    parser.error("--frames must be at least 13 for the separate 12-frame cProfile pass")
DATASET = args.dataset
OUTPUT = args.output
dataset_root = DATASET.expanduser().resolve(strict=True)
output_path = OUTPUT.expanduser().resolve()
if output_path == dataset_root or dataset_root in output_path.parents:
    parser.error("--output must be outside the source dataset")
config = load_config(None)
source = DatasetSource(
    dataset_root, args.sequence, mode=Mode.GEOMETRIC, max_points=config.max_points
)
engine = pipeline.MappingEngine(config, mode=Mode.GEOMETRIC)
durations = defaultdict(list)
original_aggregate = pipeline.aggregate_cells
original_resolve = mapping.resolve_owners


def timed_aggregate(*args, **kwargs):
    start = perf_counter()
    result = original_aggregate(*args, **kwargs)
    durations["aggregate_ms"].append((perf_counter() - start) * 1000)
    return result


def timed_resolve(*args, **kwargs):
    start = perf_counter()
    result = original_resolve(*args, **kwargs)
    durations["resolve_owners_ms"].append((perf_counter() - start) * 1000)
    return result


pipeline.aggregate_cells = timed_aggregate
mapping.resolve_owners = timed_resolve
with OUTPUT.open("x", encoding="utf-8") as stream:
    frames = source.frames(max_frames=args.frames)
    for _ in range(args.frames):
        start = perf_counter()
        frame = next(frames)
        loaded = perf_counter()
        result = engine.process(frame)
        processed = perf_counter()
        input_hash = hashlib.sha256(frame.points_sensor.tobytes())
        input_hash.update(frame.map_from_sensor.tobytes())
        hashed = perf_counter()
        map_digest = result.snapshot.digest
        digested = perf_counter()
        record = {
            "frame_id": frame.frame_id,
            "input_digest": input_hash.hexdigest(),
            "map_digest": map_digest,
            "timings_ms": result.timings.__dict__,
            "accounting": result.accounting.__dict__,
            "snapshot_array_bytes": result.snapshot.array_bytes,
            "cells": len(result.snapshot.point_count),
        }
        stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        done = perf_counter()
        for name, value in (
            ("load_ms", loaded - start),
            ("process_ms", processed - loaded),
            ("input_hash_ms", hashed - processed),
            ("snapshot_digest_ms", digested - hashed),
            ("json_write_flush_ms", done - digested),
            ("mapping_ms", result.timings.mapping_ms / 1000),
            ("projection_ms", result.timings.projection_ms / 1000),
            ("preprocess_ms", result.timings.preprocess_ms / 1000),
            ("ground_ms", result.timings.ground_ms / 1000),
        ):
            durations[name].append(value * 1000)

for name in sorted(durations):
    values = np.asarray(durations[name][1:])
    p50 = np.percentile(values, 50)
    p95 = np.percentile(values, 95)
    print(f"{name}: p50={p50:.2f} p95={p95:.2f} max={max(values):.2f} ms")
print(f"frames={args.frames} output={OUTPUT} config_digest={config.digest}")
residual = np.asarray(durations["mapping_ms"])[1:] - np.asarray(durations["aggregate_ms"])[1:]
print(f"mapping minus aggregate median={median(residual):.2f} ms")

pipeline.aggregate_cells = original_aggregate
mapping.resolve_owners = original_resolve
profile = cProfile.Profile()
engine2 = pipeline.MappingEngine(config, mode=Mode.GEOMETRIC)
frames2 = source.frames(max_frames=12)
for _ in range(12):
    frame = next(frames2)
    profile.enable()
    engine2.process(frame)
    profile.disable()
stream = io.StringIO()
pstats.Stats(profile, stream=stream).strip_dirs().sort_stats("cumtime").print_stats(35)
print("PROFILE TOP CUMTIME (12 frames)")
print(stream.getvalue())
