# Experiment 0001: current-path replay baseline

Status: two 100-frame real-data runs completed; full content validation and future path NOT VERIFIED. This measures the existing single-frame
pipeline and establishes provenance for later comparisons. It cannot validate the future model,
temporal map, vehicle response, or real-time release gate.

## Preconditions

- Authorized access to a read-only SemanticKITTI root with sequence 08 scans, calibration,
  timestamps, and poses. Do not edit the dataset. Validate metadata with the repository's
  validator and inspect its final `status` and coverage before relying on the data.
- A fresh output directory outside the dataset and existing `runs/` directories.
- Record Git revision plus dirty status, config digest, Python/package versions, CPU/GPU/RAM,
  power/thermal mode if known, dataset metadata hashes, pose source, sequence, frame interval,
  point-density distribution, and exact command in an accompanying experiment note.

## Current-path command template

Run from `Drishti-2.5/`, replacing placeholders with authorized paths:

```sh
uv run --frozen drishti replay --dataset <dataset-root> --sequence 08 --mode geometric --output <new-output-dir> --view none --max-frames 50
```

Inspect `manifest.json`, `frames.jsonl`, and `summary.json`. Check frame count, point-accounting
conservation, skipped/dropped frames, pose source, measured processing and end-to-end definitions,
p50/p95/p99/max, configured budget misses, and memory fields. Repeat warm and long runs only
after the initial report is valid; a 50-frame sample is not a sustained deadline guarantee.
Use a separate new directory for oracle evaluation and never treat its labels as model output.

## Future comparison conditions

Hold dataset split, frame IDs, accepted original point IDs, config, hardware, warmup, and summary
definitions fixed. Compare geometric, learned, and oracle modes through the same engine path.
For learned results, run the [official semantic evaluator](https://github.com/PRBonn/semantic-kitti-api)
after inverse-mapping learning IDs to raw IDs, and report unknown coverage and per-class/range
quality. Keep obstacle instances, tracking, moving-point quality, and false-free claims in separate
evaluations with their own annotations and fixtures. Report complete-path age and misses once
those stages exist.

## Current evidence gap

The earlier run files cited by `Drishti-2.5/deeplearningpipeline.md` were absent from this
working tree. New reports were saved in unique run directories without changing the old paths.
The earlier three-frame synthetic demo remains a smoke check only.

## Results on 2026-09-24

MEASURED RESULT: `uv run --frozen --extra viz pytest -q -W error` passed 42 tests; Ruff lint,
Ruff format check and mypy passed. Two headless geometric replays completed with the command
template above, using sequences 00 and 08 and 100 frames each. Reports are preserved under
`Drishti-2.5/runs/drishti-hardware-baseline-20260924-seq{00,08}-100/` with manifests,
per-frame JSONL and summaries. Source digest in both manifests:
`fa72a9a15edfde2e40b9cc7ed3a9fe4c6da0bc74814fed805607355822f34b64`;
config digest: `ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`.
Git HEAD was `998e83ee4bc04769f98e73c20f97e900732300b1` with a dirty working tree.

| Measure | Sequence 00 | Sequence 08 |
| --- | ---: | ---: |
| Input points per scan, min / median / max | 113,139 / 121,499 / 124,668 | 119,593 / 122,736 / 124,704 |
| Median scan timestamp interval | 103.64 ms | 103.99 ms |
| Steady processing p50 / p95 / p99 | 260.2 / 271.2 / 279.8 ms | 271.2 / 282.4 / 301.4 ms |
| Audit-inclusive p50 / p95 / p99 | 310.3 / 324.4 / 353.5 ms | 326.9 / 342.6 / 367.0 ms |
| Median `mapping_ms` stage | 170.3 ms | 179.8 ms |
| 100 ms budget misses | 100 / 100 | 100 / 100 |
| Observed run throughput | 3.21 frames/s | 3.05 frames/s |
| Worker peak RSS | 186.8 MiB | 203.0 MiB |

Both runs completed with point-accounting conservation for all frames. The audit-inclusive
measure includes loading, engine work and JSON/hash reporting. It excludes live acquisition,
model inference, temporal fusion, viewer and planner. The stage medians are over frames 1-99;
the summary p50/p95/p99 for audit-inclusive time includes all 100 frames. These are observed
samples, not a deterministic upper bound.

MEASURED RESULT: a separate `--structure-only` validator run reported `status: pass` for all
22 sequences, 43,552 scans and 23,201 public labels. It computed a mean of 121,661 points per
scan from file sizes; global maximum was 129,392 and zero scans exceeded the current 150,000
point cap. Median sequence timestamp intervals were near 104 ms. The report is saved as
`0001-dataset-structure-20260924.json`; scan contents and labels were not
read by this validation mode, so full-data content integrity is NOT VERIFIED.

DESIGN DECISION for development measurement: use this machine, 10 Hz input, up to 130,000
points per scan with the 150,000-point configured capacity, and a 100 ms capture-to-published
output engineering goal for the future complete path. The 100 ms goal reflects the approximately
104 ms dataset cadence and leaves a small margin; it is not currently met or a safety guarantee.
The current audit-inclusive CLI timing is only a proxy because replay starts timing after the
scan was captured and has no model, viewer or planner.
For current-path regression comparison, retain the measured report distributions rather than
calling the configured budget a passing gate. Validate future changes on longer, varied runs
and account for model, viewer, queues and memory before any release claim.
