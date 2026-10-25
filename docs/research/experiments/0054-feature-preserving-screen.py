"""Fresh-process complete-current-path precision screen; not a release benchmark.

Run from Drishti-2.5. All variants enable candidates, tracking, visibility,
temporal terrain and paced receipts. Existing source data is read by the CLI.
"""

import argparse
import ctypes
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

CHECKPOINT_SHA = "09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e"


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def capture(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"command": command, "error": str(error)}


def environment():
    power = None
    if sys.platform == "win32":

        class PowerStatus(ctypes.Structure):
            _fields_ = [
                ("ac", ctypes.c_ubyte),
                ("battery_flag", ctypes.c_ubyte),
                ("battery_percent", ctypes.c_ubyte),
                ("reserved", ctypes.c_ubyte),
                ("life", ctypes.c_uint32),
                ("full_life", ctypes.c_uint32),
            ]

        status = PowerStatus()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            power = {"ac_line_status": status.ac, "battery_percent": status.battery_percent}
    return {
        "utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "power": power,
        "gpu": capture(["nvidia-smi", "-q"]),
    }


def stats(values):
    return {
        "p50": float(np.median(values)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "max": float(np.max(values)),
    }


def screen():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--frames", type=int, default=200)
    parser.add_argument("--dataset", type=Path, default=Path("../data/semantickitti"))
    parser.add_argument(
        "--checkpoint", type=Path, default=Path("../data/frnet-semantickitti_seg.pth")
    )
    args = parser.parse_args()
    if args.frames < 2:
        raise ValueError("at least two frames required")
    output = args.output.resolve()
    dataset = args.dataset.resolve()
    if output == dataset or dataset in output.parents:
        raise ValueError("research output must be outside source dataset")
    output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve()
    save(
        output / "provenance.json",
        {
            "script_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "git_head": capture(["git", "rev-parse", "HEAD"]),
            "git_diff": capture(["git", "diff", "--", "src/drishti"]),
            "environment": environment(),
            "frames": args.frames,
            "metric": "scheduled arrival through accepted current-product receipt",
            "limitations": "Short configuration screen; no complete fused receipt or quality pass.",
        },
    )
    variants = [
        ("reference", "fp32", False),
        ("fp16", "fp16", False),
        ("gpu_interpolation", "fp32", True),
        ("fp16_gpu", "fp16", True),
        ("reference_repeat", "fp32", False),
    ]
    reports = []
    baseline = None
    baseline_predictions = None
    for name, precision, interpolation in variants:
        run = output / name
        command = [
            sys.executable,
            "-m",
            "drishti",
            "replay",
            "--dataset",
            str(dataset),
            "--sequence",
            "08",
            "--mode",
            "learned",
            "--device",
            "cuda",
            "--frnet-runtime",
            "torch",
            "--frnet-precision",
            precision,
            "--frnet-checkpoint",
            str(args.checkpoint.resolve()),
            "--frnet-checkpoint-sha256",
            CHECKPOINT_SHA,
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
            "--check-100ms",
            "--write-predictions",
            "--output",
            str(run),
        ]
        if interpolation:
            command.append("--frnet-gpu-interpolation")
        before = environment()
        print(f"Starting {name}: {args.frames} full-path frames", flush=True)
        with (output / f"{name}.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        save(
            output / f"{name}-environment.json",
            {
                "command": command,
                "before": before,
                "after": environment(),
                "returncode": result.returncode,
            },
        )
        if result.returncode not in (0, 2):
            raise RuntimeError(f"{name} failed with {result.returncode}; see saved log")
        rows = [json.loads(line) for line in (run / "frames.jsonl").read_text().splitlines()]
        summary = json.loads((run / "summary.json").read_text())
        if len(rows) != args.frames or summary["product_receipts"] != args.frames:
            raise RuntimeError(f"{name}: incomplete receipt sequence")
        for row in rows:
            if any(
                row.get(key) is None
                for key in ("temporal_summary", "visibility_summary", "tracking_summary")
            ):
                raise RuntimeError(f"{name}: a required stage summary is absent")
        predictions = sorted((run / "predictions").rglob("*.label"))
        if len(predictions) != args.frames:
            raise RuntimeError(f"{name}: missing prediction files")
        prediction_arrays = [np.fromfile(path, dtype=np.uint32) for path in predictions]
        if baseline is None:
            baseline = rows
            baseline_predictions = prediction_arrays
        identity_fields = ("frame_id", "input_digest", "accounting")
        identity_match = all(
            a[key] == b[key] for a, b in zip(baseline, rows, strict=True) for key in identity_fields
        )
        if not identity_match:
            raise RuntimeError(f"{name}: input alignment/accounting changed")
        changed = []
        for left, right in zip(baseline_predictions, prediction_arrays, strict=True):
            if left.shape != right.shape:
                raise RuntimeError(f"{name}: prediction point count changed")
            changed.append(int(np.count_nonzero(left != right)))
        report = {
            "variant": name,
            "returncode": result.returncode,
            "frames": len(rows),
            "warm_load_through_receipt_ms": stats([r["load_process_receipt_ms"] for r in rows[1:]]),
            "warm_stage_ms": {
                key: stats([r["timings_ms"][key] for r in rows[1:]])
                for key in rows[0]["timings_ms"]
            },
            "warm_receipt_ms": stats([r["receipt_ms"] for r in rows[1:]]),
            "deadline_misses": summary["replay_deadline_misses"],
            "max_scheduled_receipt_age_ms": summary["replay_receipt_age_max_ms"],
            "input_accounting_matched": identity_match,
            "changed_predictions_per_frame": changed,
            "prediction_points": sum(len(a) for a in prediction_arrays),
            "temporal_summaries": [r["temporal_summary"] for r in rows],
            "terrain_summary_matches_reference": [
                a["temporal_summary"] == b["temporal_summary"]
                for a, b in zip(baseline, rows, strict=True)
            ],
            "quality_acceptance": "NOT VERIFIED; prediction differences are not accuracy",
            "full_fused_array_parity": "NOT VERIFIED by summary comparison",
            "release_gate_met": summary["realtime_release_gate_met"],
        }
        reports.append(report)
        save(output / "screen.json", reports)
        print(
            json.dumps(
                {
                    "variant": name,
                    "service_ms": report["warm_load_through_receipt_ms"],
                    "misses": report["deadline_misses"],
                    "changed": sum(changed),
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    screen()
