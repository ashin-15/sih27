"""Compare exact cell grouping methods on read-only Drishti replay frames."""

import argparse
import json
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np
from numpy.typing import NDArray

import drishti.mapping as mapping
from drishti.config import load_config
from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.pipeline import MappingEngine

type Grouped = tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.int64]]


def rows(keys: NDArray[np.int64]) -> Grouped:
    unique, inverse, counts = np.unique(keys, axis=0, return_inverse=True, return_counts=True)
    return unique, inverse, counts


def packed(keys: NDArray[np.int64]) -> Grouped:
    if not len(keys):
        return keys.copy(), np.empty(0, np.int64), np.empty(0, np.int64)
    lower = [int(keys[:, column].min()) for column in range(3)]
    upper = [int(keys[:, column].max()) for column in range(3)]
    width_x = upper[1] - lower[1] + 1
    width_y = upper[2] - lower[2] + 1
    space = (upper[0] - lower[0] + 1) * width_x * width_y
    if space > np.iinfo(np.int64).max:
        return rows(keys)
    values = ((keys[:, 0] - lower[0]) * width_x + (keys[:, 1] - lower[1])) * width_y + (
        keys[:, 2] - lower[2]
    )
    unique_values, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    plane = width_x * width_y
    unique = np.column_stack(
        (
            unique_values // plane + lower[0],
            unique_values // width_y % width_x + lower[1],
            unique_values % width_y + lower[2],
        )
    )
    return unique, inverse, counts


def lexicographic(keys: NDArray[np.int64]) -> Grouped:
    if not len(keys):
        return keys.copy(), np.empty(0, np.int64), np.empty(0, np.int64)
    order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
    ordered = keys[order]
    starts = np.empty(len(keys), dtype=np.bool_)
    starts[0] = True
    starts[1:] = np.any(ordered[1:] != ordered[:-1], axis=1)
    first = np.flatnonzero(starts)
    inverse = np.empty(len(keys), dtype=np.int64)
    inverse[order] = np.cumsum(starts, dtype=np.int64) - 1
    counts = np.diff(np.append(first, len(keys))).astype(np.int64)
    return ordered[first], inverse, counts


def assert_equal(candidate: Grouped, expected: Grouped) -> None:
    for actual, reference in zip(candidate, expected, strict=True):
        if not np.array_equal(actual, reference):
            raise AssertionError("cell grouping changed unique keys, inverse indices or counts")


def edge_cases() -> None:
    samples = [
        np.empty((0, 3), dtype=np.int64),
        np.array([[0, -2, 3], [2, -2, 3], [0, -2, 3], [1, 0, -4]], dtype=np.int64),
        np.array(
            [[0, -20_000_000, 20_000_000], [2, 20_000_000, -20_000_000]],
            dtype=np.int64,
        ),
        np.array([[0, -(2**63), 0], [0, 2**63 - 1, 0]], dtype=np.int64),
    ]
    for sample in samples:
        expected = rows(sample)
        assert_equal(packed(sample), expected)
        assert_equal(lexicographic(sample), expected)


def timed(method, keys: NDArray[np.int64]) -> tuple[Grouped, float]:
    start = perf_counter()
    result = method(keys)
    return result, (perf_counter() - start) * 1000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--verify-frames", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 2 or args.verify_frames < 1 or args.verify_frames > args.frames:
        parser.error("require at least two frames and 1 <= verify-frames <= frames")
    root = args.dataset.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    if output == root or root in output.parents:
        parser.error("output must be outside the source dataset")
    edge_cases()
    config = load_config(None)
    source = DatasetSource(root, args.sequence, mode=Mode.GEOMETRIC, max_points=config.max_points)
    engine = MappingEngine(config, mode=Mode.GEOMETRIC)
    alternate = MappingEngine(config, mode=Mode.GEOMETRIC)
    unique_original = np.unique
    measurements: list[dict[str, object]] = []
    for index, frame in enumerate(source.frames(max_frames=args.frames)):
        process_start = perf_counter()
        result = engine.process(frame)
        baseline_process_ms = (perf_counter() - process_start) * 1000
        owners = mapping.resolve_owners(
            result.observations.points_map_m[:, :2], frame.map_from_sensor[:2, 3], config
        )
        keys = np.column_stack((owners.level, owners.indices))
        expected, row_ms = timed(rows, keys)
        alternative, packed_ms = timed(packed, keys)
        sorted_group, lex_ms = timed(lexicographic, keys)
        assert_equal(alternative, expected)
        assert_equal(sorted_group, expected)

        def replace_unique(ar, *positional, **keyword):
            if (
                keyword.get("axis") == 0
                and keyword.get("return_inverse")
                and keyword.get("return_counts")
                and isinstance(ar, np.ndarray)
                and ar.ndim == 2
                and ar.shape[1] == 3
            ):
                return packed(ar)
            return unique_original(ar, *positional, **keyword)

        process_start = perf_counter()
        with patch.object(mapping.np, "unique", side_effect=replace_unique):
            alternate_result = alternate.process(frame)
        packed_process_ms = (perf_counter() - process_start) * 1000
        if index < args.verify_frames:
            if alternate_result.snapshot.digest != result.snapshot.digest:
                raise AssertionError(f"snapshot digest changed on frame {frame.frame_id}")
            if not np.array_equal(
                alternate_result.observations.cell_indices, result.observations.cell_indices
            ):
                raise AssertionError(f"point-to-cell assignment changed on frame {frame.frame_id}")
        measurements.append(
            {
                "frame_id": frame.frame_id,
                "points": len(keys),
                "cells": len(expected[0]),
                "row_ms": row_ms,
                "packed_ms": packed_ms,
                "lexsort_ms": lex_ms,
                "baseline_process_ms": baseline_process_ms,
                "packed_process_ms": packed_process_ms,
                "snapshot_verified": index < args.verify_frames,
            }
        )
    if len(measurements) != args.frames:
        raise AssertionError("dataset yielded fewer frames than requested")
    report = {
        "sequence": args.sequence,
        "frames": args.frames,
        "verified_snapshots": args.verify_frames,
        "config_digest": config.digest,
        "measurements": measurements,
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    for name in (
        "row_ms",
        "packed_ms",
        "lexsort_ms",
        "baseline_process_ms",
        "packed_process_ms",
    ):
        values = np.asarray([float(row[name]) for row in measurements[1:]])
        print(
            name,
            "p50",
            round(float(np.percentile(values, 50)), 2),
            "p95",
            round(float(np.percentile(values, 95)), 2),
        )
    print("output", output)


if __name__ == "__main__":
    main()
