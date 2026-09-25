# Experiment 0011: current-path cost after exact grouping and projection changes

Status: Completed for 40 sequence 08 frames, 2026-09-25. RQ-004 / O-001 / T-008.
Purpose: identify the remaining measured costs before another optimization. This is a
profile of the current geometric slice, not a release benchmark.

## Setup and reproduction

Run from `Drishti-2.5/` using a fresh output path:

```sh
.venv/bin/python ../docs/research/experiments/0002-profile-harness.py \
  --dataset ../data/dataset --sequence 08 --frames 40 \
  --output /tmp/NEW-PROFILE.jsonl
```

The actual 40-frame report is
[`0011-profile-seq08-40.jsonl`](0011-profile-seq08-40.jsonl), with
[saved console and cProfile output](0011-profile-seq08-40.txt). The input is read-only
SemanticKITTI sequence 08, frames 0-39, geometric mode, default mapping config digest
`ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`.
This working tree had packed cell grouping and minimum-at range projection. The harness
wraps `aggregate_cells` and `resolve_owners` for stage timing and separately profiles
12 frames with `cProfile`. The runtime source digest recorded by the matching paced
replay was `5e4aa0e69760ec6b16966da0cbdd5a40cda166966de1660eea5c1a73e2b94bf0`;
Git HEAD was `9dd11fb6830ec8940ef354a755bb905f0cf0f27d` plus uncommitted changes.
All percentile rows exclude frame 0.

Historical boundary: this profile preceded the ordered point-ID validation change.
Experiment 0010 records the later frame-load improvement on sequences 00 and 08.

## Observed costs

| Stage | p50 ms | p95 ms |
| --- | ---: | ---: |
| Frame load | 26.53 | 29.27 |
| Preprocessing | 33.93 | 35.61 |
| Ground | 25.65 | 26.85 |
| Projection | 15.60 | 17.13 |
| Mapping | 57.52 | 65.97 |
| Whole `process` | 133.14 | 141.67 |
| Snapshot digest | 16.89 | 18.73 |

MEASURED RESULT: `aggregate_cells` accounts for nearly all reported mapping time
(56.72 ms p50); `resolve_owners` is 17.84 ms p50 within that stage. The separate
12-frame `cProfile` spent 0.696 s cumulative in aggregation, 0.414 s across NumPy
ufunc reductions and 0.114 s in packed grouping. Profile instrumentation changes
timing, so its totals are used for hotspot ranking only. Stage medians are different
distributions and should not be added as if they describe one frame.

## Next action and limits

Investigate the repeated reductions in preprocessing and aggregation, then compare an
exact-output candidate through the paced CLI. Later ordered-ID validation reduced load
but still missed all 100 ms deadlines. This profile excludes
the model, detector, temporal fusion, viewer, independent capture, resource ceilings and
the sustained release window.

## 2026-09-25 follow-up: projection overlap candidates

On the current source, a one-frame sequence 08 microbenchmark measured ground segmentation
and range projection on the same 123,389 accepted float32 points. Each timed trial used a
fresh Patchwork++ instance so ground state started identically. A thread pool with one
persistent worker ran projection concurrently with ground for six trials; a separately
warmed spawn-based process pool with one persistent worker ran eight trials. The process
case serialized the point and ID arrays and returned the range image through its worker
channel. Trial medians were approximately 37.9 ms sequential, 36.8 ms threaded and
36.2 ms process-based. The native ground and projection results had the expected point
and valid-pixel counts, but this experiment did not perform a full per-array equivalence
check or a paced CLI run.

DESIGN DECISION for this candidate: do not integrate a worker pool from this sample.
Executor overhead absorbed most of the 13 ms projection stage, leaving under 2 ms of
observed gain.
These small, order-dependent samples are not a controlled parallelism benchmark. No
runtime scheduling or interface change was made. The larger remaining release work is
the complete-path contract, model and state stages, and full-path deadline proof.

## 2026-09-25 follow-up: installed Patchwork++ GIL behavior

RQ-004 / R-SYSTEM, E-046. The user requested verification before considering threaded
stage overlap. No runtime, installed package, dataset or prior run artifact was changed.

FACT: the active environment uses CPython 3.12.14 and `pypatchworkpp` distribution 1.4.1.
Its extension SHA-256 is
`9d9305bcd2e4ab8973213cca756389b9cb0b0d9dcba96ac3a061de90a6da2734`.
The [v1.4.1 binding source](https://github.com/url-kaist/patchwork-plusplus/blob/v1.4.1/python/patchworkpp/pybinding.cpp)
binds `estimateGround` directly without a GIL-release call guard. The
[pybind11 GIL documentation](https://pybind11.readthedocs.io/en/stable/advanced/misc.html#global-interpreter-lock-gil)
states that native calls do not implicitly release the GIL. This source review corroborates,
but does not substitute for, testing the installed binary. The binary imports GIL-management
symbols, which alone cannot establish whether this particular method releases the GIL.

MEASURED RESULT: [probe 0021](0021-patchwork-gil-probe.py) tested a Python heartbeat thread
against raw `estimateGround` on 130,000 deterministic synthetic float32 points. It used
separate estimators for C- and Fortran-contiguous layouts, one warmup call each, 12 trials
per layout and rotated case order. A 0.5 s Python switch interval exceeded each timed call;
heartbeats in the first/last 1 ms were excluded to avoid boundary scheduling artifacts.
A libc `usleep` call through `ctypes.CDLL` was the releasing control; the same function
through `ctypes.PyDLL` was the holding control. The heartbeat slept 1 ms between timestamps.

Both the [initial report](0021-patchwork-gil-probe.json) and
[confirmation report](0021-patchwork-gil-probe-confirmation.json) passed their controls.
Across both runs, Python made zero interior progress in all 48 `estimateGround` calls and
all 24 holding controls; it progressed in all 24 releasing controls. In the confirmation,
C/F call durations were 29.87/29.92 ms median; releasing controls had 34-38 interior ticks
per call. These durations are instrumented synthetic measurements, not replay latency.
Both layouts produced 116,819 ground and 13,181 nonground indices after their last call;
this count check is not a full output-parity test.

Reproduce from `Drishti-2.5/` with a new output file:

```sh
.venv/bin/python ../docs/research/experiments/0021-patchwork-gil-probe.py \
  --output /tmp/NEW-PATCHWORK-GIL-REPORT.json
```

VERIFIED: probe Ruff lint/format and strict mypy passed; the package suite passed with
57 tests and 3 CUDA skips. The initial mypy run found a nullable module path; an explicit
check fixed it before the confirmation run. Both reports retain their own harness hashes.

CONCLUSION: installed `estimateGround` holds the GIL during the tested native computation.
The earlier overlap screen did not isolate GIL blocking from executor/copy overhead, so its
attribution to executor overhead was incomplete. A Python thread pool alone cannot remove
this blocker. Already-running native operations that released the GIL can still execute;
this result does not prove that all CPU work is serialized or that GIL release alone gives
a useful speedup. A future reviewed binding change could explicitly release the GIL around
pure native work, while preserving exclusive ordered ownership of each estimator and no
concurrent getters/mutation. Alternatively, a persistent separate process has its own GIL
but adds IPC costs. Neither alternative was implemented or benchmarked here; O-001 stays open.
