# Drishti-2.5 perception technical design

Status: Draft. Based on draft PRD dated 2026-09-24. Approval: Pending.

## Current architecture and planned flow

Current: `ScanFrame -> MappingEngine.process -> Patchwork++ / projection / aggregate_cells -> MapSnapshot -> CLI and Rerun`. The engine does not use prior snapshots. The intended flow is `ScanFrame -> geometry and timing validation -> semantic inference -> obstacle observations -> ego-motion compensated association and motion -> conservative visibility evidence -> bounded temporal map -> immutable frame result -> audit and viewer`. Keep `MappingEngine.process` as the single public execution path, with explicit stage interfaces and a sequence-owned state object.

## Module boundaries and contracts

| Boundary | Proposed contract and invariant | FRs |
| --- | --- | --- |
| Input | Extend `ScanFrame` only with optional, validated per-point timing/pose quality. Preserve immutable original point IDs and aligned arrays. Never access `annotations` in production inference. | 001, 009, 011 |
| Semantic predictor | `predict(points, projection, metadata) -> (N,) learning IDs, (N,) confidence, provenance` for all accepted points in original accepted order. Any projection winner result must scatter back with unknown for unsupported points. Checkpoint hash and class map are mandatory. | 001, 007 |
| Detector | Consume accepted points, ground evidence and predicted semantics; emit instance observations with 3D bounds, class distribution, uncertainty and point IDs. A cell height envelope alone cannot define occupied volume. | 002 |
| Tracker/motion | Sequence-owned, pose-aligned state keyed by track IDs. Associate geometric instances across timestamps; estimate world-relative velocity and uncertainty. Use UNKNOWN for insufficient evidence. Track and static map lifecycles remain separate. | 003 to 005 |
| Visibility | Consume calibrated beam origins/endpoints and valid returns. Mark traversed cells free only within the supported ray/FoV corridor and only when no nearer current return conflicts. Keep no-return and occluded areas unknown. | 006 |
| Temporal map | Bounded rolling cell store with last-observed timestamp, source, semantic evidence, ground/obstacle evidence, occupancy state and visibility counters. Finer/coarser ownership must remain nonoverlapping. Dynamic detections are transient observations; stationary obstacles still block occupancy. | 003, 006, 010 |
| Output | Version `MapSnapshot` and audit schema. Distinguish single-frame observation, fused state, occupied, free, unknown, stale and ambiguous. Consumers must reject unsupported or old schema versions. | 007, 010 |

## Implementation order

1. Freeze point, class, pose, time, checkpoint and output schemas. Add an evaluator that runs the same `MappingEngine.process` path as the CLI.
2. Build a model adapter and reproducible offline training/inference package. Keep model choice replaceable and evaluate point order, class IDs and unknown coverage before map integration.
3. Add conservative obstacle instances from geometry and learned semantics, with unknown class fallback and height/clearance tests.
4. Add pose-aligned tracking and motion estimation. Validate static structures under ego motion before enabling moving labels. Separate dynamic tracks from static map fusion.
5. Add ray-based visibility and a timestamped rolling map. Explicitly test moving-object departure, occlusion, blind regions, repeated scans, sequence reset and frame gaps.
6. Extend the viewer and audit, then profile and optimize the complete path on selected hardware. Keep the release gate false until all acceptance criteria pass.

## State, failure and recovery

The first frame has unknown motion and no temporal confidence. A missing or invalid pose, nonmonotonic timestamp, changed calibration, checkpoint mismatch, dropped input, or exceeded state capacity must produce a visible error or degraded/unknown output. Reset state at sequence boundaries; never carry tracks or ground estimator state across streams. Bound map cells, tracks, queues and model memory explicitly. Replaying identical input and config should produce the same logical result where deterministic backends permit; document any model/backend nondeterminism.

## Performance and observability

Measure load, preprocessing, ground, model, detection, association, visibility, fusion, publication, audit and viewer work separately. Count queue wait, dropped frames and time from sensor timestamp to published output. Report p50/p95/p99/max and deadline misses over a declared warmup and run window, plus process RSS, model memory and viewer RSS. A configuration budget is an alert threshold, not a guarantee. Hardware, input density, sequence list, backend and checkpoint are required in every benchmark manifest.

## Evaluation boundaries

Use labels only in oracle evaluation and scoring. SemanticKITTI semantic and moving-object tasks provide point labels, but they do not by themselves certify 3D detector boxes, track identity, ray free-space correctness or navigation safety. Add curated obstacle and visibility fixtures plus a separate labeled set or human-reviewed samples for those outputs. Compare the learned path, oracle upper bound and geometry baseline under the same filtering and map path. Report unknown coverage and false-free errors, not only IoU.

## Alternatives and blockers

A specific network architecture, framework, checkpoint source, target accelerator, association algorithm and ray discretization remain technical decisions after D-001/D-002/D-004. Choose using measured accuracy, license, integration cost and complete-path latency. Do not commit to an external model or claim real-time performance from model-only benchmarks. Navigation output and its clearance threshold are blocked by D-003 and a vehicle geometry contract.
