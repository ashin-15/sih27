"""AC-power complete-current-path baseline; preserve all current enabled stages."""

import argparse
import json
import runpy
import subprocess
import sys
from pathlib import Path

import numpy as np

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--frames", type=int, default=200)
args = parser.parse_args()
helpers = runpy.run_path(str(Path(__file__).with_name("0054-feature-preserving-screen.py")))
before = helpers["environment"]()
if before["power"] is None or before["power"]["ac_line_status"] != 1:
    raise RuntimeError("AC power must be verified before starting this baseline")
args.output.mkdir(parents=True, exist_ok=False)
command = [
    sys.executable,
    "-m",
    "drishti",
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
    helpers["CHECKPOINT_SHA"],
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
    "--output",
    str(args.output / "run"),
]
provenance = {
    "before": before,
    "command": command,
    "git_diff": helpers["capture"](["git", "diff", "--", "src/drishti"]),
}
helpers["save"](args.output / "provenance.json", provenance)
with (args.output / "replay.log").open("w", encoding="utf-8") as log:
    completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
provenance["after"] = helpers["environment"]()
provenance["returncode"] = completed.returncode
helpers["save"](args.output / "provenance.json", provenance)
if completed.returncode not in (0, 2):
    raise RuntimeError(f"replay failed: {completed.returncode}; inspect saved log")
rows = [json.loads(line) for line in (args.output / "run/frames.jsonl").read_text().splitlines()]
summary = json.loads((args.output / "run/summary.json").read_text())
if len(rows) != args.frames or summary["product_receipts"] != args.frames:
    raise RuntimeError("incomplete baseline")
report = {
    "frames": len(rows),
    "accepted_receipts": summary["product_receipts"],
    "deadline_misses": summary["replay_deadline_misses"],
    "cold_service_ms": rows[0]["load_process_receipt_ms"],
    "warm_service_ms": helpers["stats"]([r["load_process_receipt_ms"] for r in rows[1:]]),
    "warm_stages_ms": {
        key: (helpers["stats"]([r["timings_ms"][key] for r in rows[1:]])
              if rows[0]["timings_ms"][key] is not None else None)
        for key in rows[0]["timings_ms"]
    },
    "warm_receipt_p50_ms": float(np.median([r["receipt_ms"] for r in rows[1:]])),
    "scheduled_age_max_ms": summary["replay_receipt_age_max_ms"],
    "power_before": before["power"],
    "power_after": provenance["after"]["power"],
    "release_gate": summary["realtime_release_gate_met"],
    "limitation": "AC checked at boundaries; thermal/clock stability and full release unverified",
}
helpers["save"](args.output / "report.json", report)
print(json.dumps(report, indent=2))
