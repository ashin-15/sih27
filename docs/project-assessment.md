# Project assessment

Audited 2026-09-24 from source, tests, synthetic validation and two short real-data replays.
Categories are explicit; this is not an implementation claim.

## 2026-09-28 implementation and validation update

FACT: T-002's version-1 diagnostic product result and same-process evaluator
are integrated. T-003 now has a CPU FRNet worker using a hash-pinned checkpoint,
label-free learned replay, schema-2 semantic-only receipts, raw-ID prediction
files and supplemental range metrics. An installed-wheel sequence 08 scan
returned one aligned prediction per accepted original point and an accepted
semantic receipt; see [experiment 0024](research/experiments/0024-t003-frnet-drishti-integration.md).
E-051 now verifies 4,071 held-out sequence 08 point predictions and accepted
semantic receipts, with official 19-class mIoU 0.675469 and labeled accuracy
0.922835. The evaluation combined a saved 793-frame prefix and a new-engine
continuation, so continuous map state is unverified. Numeric D-005 thresholds,
checkpoint weight terms, exact public bytes and CUDA/release latency remain
UNKNOWN, so T-003 is IN PROGRESS rather than DONE. An approved T-004 CPU
candidate stage now groups accepted learned points into evidence-only
frame-local instances, with observed bounds and schema-3 receipts. E-055 and
[experiment 0028](research/experiments/0028-t004-saved-prediction-eval.md)
record source/wheel replay and a 4,071-scan panoptic baseline. Full AC-002
obstacle quality and AC-008 real-time acceptance remain open. The original audit below
describes the 2026-09-24 baseline and is retained as historical context.

## 2026-09-29 bounded tracking update

FACT: decision 0006 approves known-thing CPU association and AC-002 traffic
participant numeric targets. The shared engine now emits schema-4 tracking
evidence with stable sequence IDs and unknown velocity. E-057 and
[experiment 0030](research/experiments/0030-t005-association-eval.md) record
source/installed-wheel replay and a 200-frame development association
baseline. The diagnostic counted 69 ID switches and 39 fragmentations;
full AC-004/005 quality, independent wider-obstacle AC-002 evaluation and
AC-008 release timing remain NOT VERIFIED. The sections below preserve the
original 2026-09-24 audit as historical context.

## Current state at the 2026-09-24 audit

FACT: `Drishti-2.5/src/drishti/pipeline.py` creates one `MapSnapshot` per frame and does not read earlier snapshots. `mapping.py` computes adaptive cell ownership, ground/observed/nonground statistics and oracle semantic histograms. `cli.py` provides demo/replay, run manifests, point accounting, latency and memory reporting. `visualization.py` renders geometry/semantic cells and states limitations. `dataset.py` loads SemanticKITTI with explicit poses. `tests/` covers the present slice.

MEASURED RESULT: On 2026-09-24, 42 tests passed with warnings as errors. A three-frame synthetic headless demo completed with zero recorded 100 ms misses, peak snapshot payload 4,408,008 bytes and worker RSS peak 73,437,184 bytes. Its `realtime_release_gate_met` field remained false. This is not representative real-data or full-system performance.

## Incomplete areas

FACT for the 2026-09-24 baseline: there was no learned model or training
workflow. The 2026-09-27 update above supersedes that semantic-inference gap.
There is still no completed local training run, validated full-scope object
detector, temporal fusion, full-scope tracker, motion estimation, ray-based free-space proof, live
input or real-time release guarantee. Oracle labels remain evaluation input.
See `Drishti-2.5/docs/spec-driven/drishti-perception/CURRENT_STATE.md` for
the baseline code audit.

FACT: `Drishti-2.5/deeplearningpipeline.md` describes a proposed model and safety architecture;
it does not implement it. Its previous real-data links were absent; it now cites fresh 100-frame
sequence 00 and 08 reports in unique run directories. MEASURED RESULT: current headless
geometric replay missed the configured 100 ms budget on all 200 observed frames. This does not
measure the future complete path or prove a real-time guarantee.

## Risks and technical debt

- FACT: `README.md` previously overstated CPU deadline and memory claims; it now states the measured scope. Historical research evidence describes a different prototype and must not be quoted as a Drishti benchmark.
- FACT: `cli.py` records viewer RSS, rendering FPS and scratch memory as null; it sets release gate false. A target benchmark remains NOT VERIFIED.
- FACT: `ScanFrame.deskew_status` defaults to unavailable. Pose source quality and scan distortion are not quantified.
- FACT: A single 2.5D height per cell cannot itself prove overhang clearance or free space. Current observed min/max is a return envelope.
- FACT: Existing run artifacts had user modifications before this bootstrap. Preserve them.
- UNKNOWN: model licensing/weights, physical NVIDIA release host and vehicle dimensions. Dataset metadata and
  two short replays were checked; full scan-content validation remains NOT VERIFIED.

## High-value questions

1. Which complete payload schema and resource limits define the CUDA replay gate? The 100 ms deadline, zero misses and same-process evaluator receipt are selected; physical host and workload approval are deferred.
2. DECIDED on 2026-09-27: first learned milestone is semantic-only FRNet CPU
   integration. Weight terms, full held-out quality and local retraining remain open.
3. Which false-free, unknown/stale and recovery thresholds apply to the selected evidence-only output? Planner-facing use is deferred.
4. What timing/calibration/pose quality contract would be required for a later live release? Live input is deferred beyond this first replay release.
5. What held-out data and numeric quality thresholds are acceptable for each requested capability?

## Evidence discipline

Source: `Drishti-2.5/src/drishti/{cli,pipeline,mapping,dataset,visualization}.py`, `Drishti-2.5/pyproject.toml`, and tests. Local runs: `/tmp/drishti-review-baseline-20260924/` and saved 100-frame reports under `Drishti-2.5/runs/`. External task definitions: official SemanticKITTI tasks at https://semantic-kitti.org/tasks.html. Research and historical artifacts under `research/` are not current runtime evidence.
