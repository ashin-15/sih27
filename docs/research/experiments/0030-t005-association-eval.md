# Experiment 0030: bounded T-005 CPU association

Date: 2026-09-29. RQ-002 / T-005 / decision 0006. Status: bounded CPU
implementation and development diagnostic verified; full AC-004/005 quality
and AC-008 remain open.

## Method and provenance

The approved [T-005 contract](../../t-005-tracking-proposal.md) fixes a
sequence-owned deterministic map-frame association gate, 512-track default
capacity, two-observation confirmation and expiry after three missed frames.
The existing learned FRNet and candidate path feed the new tracker. It emits
schema-4 `stage=tracking` results with unknown metric velocity/covariance and
commits state only after a same-process evaluator accepts the sealed result.
Oracle labels remain outside inference. Product diagnostics report association
time and track count; JSONL records each lifecycle transition and rejected
births. A rejected product result fails the engine closed because native ground
preprocessing cannot be rolled back; recovery is a fresh sequence replay.

The fixed diagnostic evaluates frames 0..199 of SemanticKITTI sequence 08,
which is held out from the FRNet training split but was previously inspected
for T-004 development. It is a development baseline, not an untouched final
AC-004 evaluation. Script: [0030-t005-association-eval.py](0030-t005-association-eval.py).
It reads saved point classes from the pinned T-003 run, creates the ordinary
single-sequence mapping/detector path with annotations removed, then runs the
production `CandidateTracker` implementation. The offline score path does not
run fresh FRNet inference or publish product receipts. It reads sequence IDs
only after inference for evaluation. The ignored report is
`artifacts/t005-association-200-20260929.json`, with input/pose, annotation,
accepted-class and track-trace SHA-256 values, source digest, dataset metadata
hashes and evaluator settings. It records a parent-process RSS peak; there is
no FRNet worker in this offline process.

Reproduce the offline screen from the repository root with a new output path:

```bash
PYTHONPATH=Drishti-2.5/src Drishti-2.5/.venv/bin/python \
  docs/research/experiments/0030-t005-association-eval.py \
  --dataset data/dataset \
  --saved-run artifacts/t003-seq08-restart-20260928 \
  --output artifacts/NEW-t005-association-200.json
```

For source replay, run `Drishti-2.5/.venv/bin/drishti replay` with
`--dataset data/dataset --sequence 08 --mode learned --view none
--max-frames 3 --detect-obstacles --track-obstacles
--write-panoptic-predictions --output artifacts/NEW-t005-source` plus the
six FRNet path/hash flags listed in [experiment 0026](0026-t003-cpu-semantic-verification.md).
For the installed wheel, use the same arguments with the CLI in the separate
wheel environment and another new output path. The complete manifests record
the pinned checkpoint, export, class map and source revision.

The local metric matches predicted track observations to GT thing instances of
the same learning class if each has >=50 supporting points and point-support
IoU is strictly greater than 0.5. It reports object-observation TP/FP/FN, ID
switches, fragmentation after a missed visible match, predicted track IDs that
never match, and an association Jaccard averaged over matched observations.
This is a documented equivalent diagnostic for the bounded association slice;
it is **not** official SemanticKITTI 4D LSTQ or a metric velocity score.
Classes without >=50-point GT support are not a quality pass.

## Measured result

| 200 ordered sequence-08 scans | Value |
| --- | ---: |
| Matched / unmatched predicted / missed GT observations | 1,433 / 170 / 141 |
| ID switches / fragmentations | 69 / 39 |
| Predicted track IDs never matched | 39 |
| Association Jaccard | 0.723003 |
| Peak live tracks / rejected births | 54 / 0 |
| Tracker-only p50 / p95 / p99 / max, ms | 3.654 / 4.347 / 4.566 / 4.658 |
| Offline parent peak RSS | 249,417,728 bytes |
| Offline elapsed wall time | 61.08 s |

The class table and denominators are in the ignored JSON report. Its car
subset has 43 switches; person has 25. Motorcycle and motorcyclist have no
eligible GT observations in this 200-frame slice. These errors and missing
classes prevent a full T-005 quality conclusion. The CPU association cost
excludes model inference, candidate grouping, receipt validation and audit.

Source and an independently installed wheel both replayed real scans 0..2 in
learned mode with `--detect-obstacles --track-obstacles --view none` and the
pinned FRNet checkpoint/export from experiment 0026. The final output paths
are `artifacts/t005-source-verified-20260929/` and
`artifacts/t005-wheel-verified-20260929/`; source digest is
`0502866f9bedd39f807945785b07a6749a96110260c18ab4f529db9397bb9f4d`.
The replayed installed wheel SHA-256 is
`c66318d34365aea9971717a70d8336959a9e0ab8254c01572a7e7b59d07e6e27`.
The ignored `artifacts/t005-verification-20260929.json` stores per-scan hashes
and parity checks. Three
schema-4 receipts in each run were accepted; candidate and track traces,
input/map digests and all three full-order panoptic prediction files matched
between source and wheel. The wheel module imported from its separate
`site-packages` directory. Receipt digests differ as stage timings are part of
each receipt; trace and prediction parity are compared fieldwise. The first
scan had 22 tentative tracks, and later scans had 31 and 29 emitted lifecycle
records. The trace uses no oracle labels.
After the dated package documentation was finalized, a fresh source/wheel
build produced wheel SHA-256
`771f87b7dc494fd3a458282b67f4e2bfa3359495b42a50c6d2695bcacfadf0b2`.
All 23 Python modules in that wheel are byte-identical to the replayed wheel
and current source, as recorded in the ignored
`artifacts/t005-final-wheel-code-parity-20260929.json`.
The saved-class 200-frame report was produced before a later CLI wording and
evaluator class-gate refinement; its report records its own source digest.
The production association algorithm and fixed data window did not change.

## Verification and judgment

The focused 10 authored tests cover crossing, near neighbors, occlusion and
expiry, reappearance, ego pose change, unknown/stuff filtering, capacity,
sequence reset, invalid geometry/time, bounded two-frame history, tampered
payload rejection and transactional state recovery. The full package tests,
Ruff lint/format, strict mypy, source/wheel build and final replay are recorded
in the dated work log. The viewer test needs `.venv/bin` on `PATH` so its
`rerun rrd verify` subprocess resolves the installed CLI.
The final full suite passed 87 tests and skipped 3 CUDA tests; Ruff lint and
format, strict mypy on 41 source files and the offline source/wheel build
passed. A first offline build with a fresh uv cache could not resolve pinned
setuptools; using the populated local uv cache completed the same build.

AC-016 bounded implementation and measurement is ACCEPTED_WITH_CAVEATS after
all checks pass. Full AC-004 tracking quality, AC-005 quantitative motion and
AC-008 release timing remain NOT VERIFIED. AC-002 traffic gates are approved
but not passed; wider obstacle labels and gates are absent.
