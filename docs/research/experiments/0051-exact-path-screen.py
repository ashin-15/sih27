"""A/B replay and same-input parity for visibility and schema-5 digest optimizations.

Run from Drishti-2.5. Reference directory must contain the pre-change visibility.py
and product_result.py. Source data is consumed only by the normal replay CLI.
"""

import argparse
import ast
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from drishti import product_result, visibility
from drishti.cli import main


def reference_function(path, name, namespace, cls=None):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    body = tree.body
    if cls is not None:
        body = next(
            node for node in body if isinstance(node, ast.ClassDef) and node.name == cls
        ).body
    node = next(node for node in body if isinstance(node, ast.FunctionDef) and node.name == name)
    scope = dict(namespace)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), scope)
    return scope[name]


def stats(values):
    return {
        "p50": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
    }


def screen():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--frames", type=int, default=6)
    args = parser.parse_args()
    if args.frames < 2:
        raise ValueError("at least two frames required")
    args.output.mkdir(parents=True, exist_ok=False)
    current_pairs = visibility.CurrentScanVisibility._corridor_pairs
    current_feed = product_result._feed_raw
    old_pairs = reference_function(
        args.reference / "visibility.py",
        "_corridor_pairs",
        vars(visibility),
        "CurrentScanVisibility",
    )
    old_feed = reference_function(
        args.reference / "product_result.py", "_feed_raw", vars(product_result)
    )
    reports = []
    report_rows = []
    argv = [
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
        "../data/frnet-semantickitti_seg.pth",
        "--frnet-checkpoint-sha256",
        "09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e",
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
        str(args.frames),
    ]
    try:
        for index, use_current in enumerate((False, True, True, False)):
            label = "current" if use_current else "reference"
            visibility.CurrentScanVisibility._corridor_pairs = (
                current_pairs if use_current else old_pairs
            )
            product_result._feed_raw = current_feed if use_current else old_feed
            directory = args.output / f"run{index}-{label}"
            if main([*argv, "--output", str(directory)]) != 0:
                raise RuntimeError(f"{label} replay failed")
            rows = [
                json.loads(line)
                for line in (directory / "frames.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            if len(rows) != args.frames:
                raise ValueError("incomplete replay")
            if any(row["product_result_receipt"]["status"] != "accepted" for row in rows):
                raise ValueError("rejected receipt")
            metrics = {
                "run": index,
                "implementation": label,
                "frames": len(rows),
                "cold_load_process_publish_ms": rows[0]["load_process_publish_ms"],
                "audit_budget_misses": sum(row["load_process_publish_ms"] > 100 for row in rows),
                "warm_processing_ms": stats([r["timings_ms"]["total_ms"] for r in rows[1:]]),
                "warm_visibility_ms": stats([r["timings_ms"]["visibility_ms"] for r in rows[1:]]),
                "warm_receipt_validation_ms": stats(
                    [r["product_result_receipt"]["validation_duration_ns"] / 1e6 for r in rows[1:]]
                ),
                "warm_load_process_publish_ms": stats(
                    [r["load_process_publish_ms"] for r in rows[1:]]
                ),
            }
            reports.append(metrics)
            report_rows.append(rows)
            print(json.dumps(metrics), flush=True)

        # Compare all reported evidence, excluding measured timings and run identities.
        evidence = (
            "frame_id",
            "input_digest",
            "map_digest",
            "accounting",
            "cells",
            "candidate_instances",
            "tracks",
            "tracking_summary",
            "visibility_summary",
            "temporal_summary",
            "semantic_unknown_points",
            "snapshot_array_bytes",
        )
        for rows in report_rows[1:]:
            for before, after in zip(report_rows[0], rows, strict=True):
                for key in evidence:
                    if before[key] != after[key]:
                        raise ValueError(f"frame {before['frame_id']} differs in {key}")

        # Separate, instrumented replay: exact reduced arrays and complete digests on
        # the same inputs. Do not use this run's elapsed timings as a path benchmark.
        parity = {"chunks": 0, "digests": 0}
        isolated = {
            "pairs_reference": [],
            "pairs_current": [],
            "digest_reference": [],
            "digest_current": [],
        }

        def checked_pairs(self, *values):
            outputs = {}
            order = (("reference", old_pairs), ("current", current_pairs))
            if parity["chunks"] % 2:
                order = order[::-1]
            for label, function in order:
                start = perf_counter()
                outputs[label] = function(self, *values)
                isolated[f"pairs_{label}"].append((perf_counter() - start) * 1000)
            np.testing.assert_array_equal(outputs["reference"], outputs["current"])
            parity["chunks"] += 1
            return outputs["current"]

        def checked_digest(value):
            outputs = {}
            for label, function in (("reference", old_feed), ("current", current_feed)):
                digest = hashlib.sha256(b"drishti-raw-digest-v1\n")
                start = perf_counter()
                function(digest, value)
                isolated[f"digest_{label}"].append((perf_counter() - start) * 1000)
                outputs[label] = digest.hexdigest()
            if outputs["reference"] != outputs["current"]:
                raise ValueError("schema-5 stream changed")
            parity["digests"] += 1
            return outputs["current"]

        visibility.CurrentScanVisibility._corridor_pairs = checked_pairs
        product_result._feed_raw = current_feed
        original_digest = product_result.canonical_result_digest
        product_result.canonical_result_digest = checked_digest
        try:
            if main([*argv, "--output", str(args.output / "parity")]) != 0:
                raise RuntimeError("parity replay failed")
        finally:
            product_result.canonical_result_digest = original_digest
        result = {
            "runs": reports,
            "parity": parity,
            "isolated_ms": {name: stats(values) for name, values in isolated.items()},
            "scope": "unpaced current schema-5 plus diagnostic temporal; not AC-008",
            "power_and_thermals": "uncontrolled",
            "release_gate_met": False,
        }
        (args.output / "screen.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result), flush=True)
    finally:
        visibility.CurrentScanVisibility._corridor_pairs = current_pairs
        product_result._feed_raw = current_feed


if __name__ == "__main__":
    screen()
