# Drishti-2.5 current-state audit

Checked: 2026-09-24. Status: code inspection plus local synthetic run. This document describes the standalone implementation at this date. It is not a product specification.

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
