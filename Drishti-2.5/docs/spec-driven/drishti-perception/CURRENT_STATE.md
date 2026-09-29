## 2026-09-29 bounded tracking update

The shared learned CPU path now prepares schema-4 `stage=tracking` results
from observed known thing candidates and commits tracker state only after an
accepted same-process evaluator receipt. Source and installed-wheel replay
and a 200-frame saved-class association diagnostic are in experiment 0030.
Velocity, covariance, temporal map fusion and full AC-004/005/008 quality
remain NOT VERIFIED.

# Drishti-2.5 current-state audit

Checked: 2026-09-24. Status: code inspection plus local synthetic run. This document describes the standalone implementation at this date. It is not a product specification.

2026-09-27 update: the table below is the pre-T-002/T-003 baseline audit.
The approved CPU FRNet semantic slice, schema-2 semantic-only evaluator
receipt and installed-wheel one-scan replay are recorded in
`docs/research/experiments/0024-t003-frnet-drishti-integration.md` and
`docs/decisions/0004-frnet-semantic-cpu-slice.md` at the repository root.
The later [experiment 0025](../../../../docs/research/experiments/0025-t003-full-sequence08.md)
records complete sequence 08 point-semantic quality at 0.675469 official mIoU.
Numeric quality acceptance and release timing remain unverified.

2026-09-28 update: decision 0005 approves a bounded CPU obstacle candidate
stage. `obstacles.py` now groups accepted learned points into frame-local
evidence with original support IDs and observed bounds; schema-3 candidate
receipts and optional panoptic exports are recorded in
[experiment 0028](../../../../docs/research/experiments/0028-t004-saved-prediction-eval.md).
The table below remains the 2026-09-24 historical audit. Full AC-002 quality,
tracks, motion, free-space proof and AC-008 release timing are not verified.

## Active path

`drishti.cli._run` obtains `ScanFrame` values from `DatasetSource.frames` or `synthetic_frames`, calls `MappingEngine.process`, optionally publishes through `RerunView`, and writes JSON audit files. `MappingEngine.process` validates the ordered stream, filters/transforms points, calls Patchwork++ ground segmentation, constructs a diagnostic range image, and calls `aggregate_cells`. The returned `MapSnapshot` is explicitly `single-frame`.

## Capability inventory

| Need | What code currently proves | Missing work | Primary files |
| --- | --- | --- | --- |
| Learned semantic model | `Mode.GEOMETRIC` initializes every accepted semantic ID to 0. `Mode.ORACLE` copies point-aligned annotation IDs. No model dependency, checkpoint loader, training entry point, or inference mode exists. | Define a prediction contract, training/evaluation workflow, versioned checkpoint, inference adapter, latency and accuracy gates. Preserve original point order and unknown ID 0. | `contracts.py`, `pipeline.py`, `semantics.py`, `dataset.py`, `pyproject.toml` |
| Obstacle detection | `aggregate_cells` stores nonground height bounds; `cell_geometry` draws observed envelopes. These are neither object instances nor collision volumes. | Cluster evidence into objects, classify static/dynamic candidates, fit conservative shape and vertical clearance, expose unknown/ambiguous states, evaluate thin objects, curbs, overhangs and partial views. | `mapping.py`, `visualization.py` |
| Temporal fusion | `MappingEngine` retains only stream ID and last frame/time for validation. A new snapshot is constructed per call; no previous cells are read. | Bounded rolling state with timestamped evidence, ego-pose alignment, conflict and decay policy, reset/recovery and replay behavior. | `pipeline.py`, `mapping.py` |
| Object tracking | `Annotations.instance` exists for oracle input but is not passed into the engine or map. No track state or IDs are produced. | Associate detections across frames, handle births, occlusion, misses, split/merge and ID lifecycle, evaluate ID switches and fragmentation. | `semantics.py`, `pipeline.py` |
| Motion estimation | Geometric mode initializes motion to `UNKNOWN`; oracle mode copies dataset motion labels. There is no measured object velocity or static/moving inference. | Ego-motion compensate sequential observations, estimate velocity with uncertainty, distinguish moving from temporarily stationary and unknown, keep all collision obstacles regardless of motion. | `pipeline.py`, `mapping.py` |
| Free-space proof | Range projection returns winners, collisions and outside-FOV counts. No ray-traced free cells, visibility misses or occlusion policy exist. | Produce explicit observed-free, occupied and unknown evidence with beam geometry, valid farther-return guards, sensor FoV and return confidence. Never clear unseen space. | `projection.py`, `mapping.py` |
| Real-time guarantee | `frame_budget_ms` defaults to 100. The CLI reports latency and misses, but `realtime_release_gate_met` is hardcoded false. The viewer's FPS, memory and scratch memory are null. | Specify target hardware and full input path; bound queues/state/memory; benchmark p50/p95/p99/max, deadline misses, drops, recovery, model and viewer costs on representative sequences. | `config.py`, `cli.py`, `visualization.py` |
| Input timing and pose | Replay requires external poses and monotonically increasing timestamps. `deskew_status` is `unavailable`. | Define live sensor contract, per-point time and deskew or explicit unsupported-sensor limitation; propagate pose quality and calibration checks. | `dataset.py`, `contracts.py`, `geometry.py` |
| Safety/use boundary | Ground height is invalidated for large vertical spans, but observed min/max is an envelope, not occupancy. No planner contract exists. | Define clearance, traversability, stale/unknown behavior and conditions for navigation use. | `mapping.py`, `visualization.py` |

## Verified baseline and limits

- `uv run --frozen --extra viz pytest -q -W error`: 42 passed on 2026-09-24.
- `uv run --frozen drishti demo --output /tmp/drishti-review-baseline-20260924 --view none --frames 3`: completed. The run recorded 0 deadline misses for three synthetic frames, 4,408,008 peak snapshot array bytes, and 73,437,184 worker peak RSS bytes. Its release gate remained false. This is a small synthetic functional check, not a performance distribution or a complete-pipeline benchmark.
- Real dataset files were not read for this audit. Existing run artifacts under `runs/` were already modified before this work and were left untouched.

## Repository cleanup boundary

The standalone package is `Drishti-2.5/`. Older prototype-specific research and reports are historical evidence, not active implementation or performance proof. The license attribution remains in `THIRD_PARTY_NOTICES`. Re-run dataset and model evaluation on this package before making release claims.
