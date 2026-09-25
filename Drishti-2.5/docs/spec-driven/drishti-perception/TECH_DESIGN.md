# Drishti-2.5 perception technical design

Status: Draft. Based on draft PRD updated 2026-09-25. Approval: Pending.

## Current architecture and planned flow

DESIGN DECISION, CPU-first clarification: implement and execute on the current laptop CPU
now; keep CUDA optional for later NVIDIA access. Missing GPU hardware blocks CUDA validation,
not approved CPU-side implementation. This does not waive the remaining product contract
or establish the 100 ms deadline on either backend.

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

The first CUDA-backed release targets paced dataset replay on an identified NVIDIA CUDA host; the current Core Ultra 9 185H laptop remains the CPU reference. Its deadline is 100 ms for each scan from scheduled arrival to publication of the complete output, with zero misses in the accepted window. Define both events on one monotonic clock. Measure load, preprocessing, ground, model, detection, association, visibility, fusion, device transfers, publication, audit and selected viewer work separately. Count schedule lag, dropped frames and output age, keeping it distinct from compute duration. Report p50/p95/p99/max and every deadline miss over a declared warmup and run window, plus process-tree RSS, GPU memory, model memory, allocated disk and viewer RSS if enabled. A configuration budget alone is not a guarantee. Physical host, GPU, driver, power state, input density, sequence list, backend and checkpoint are required in every benchmark manifest. Live sensor timing remains deferred.

Current-state FACT: the CLI's frame JSONL contains audit metadata and digests but
no map arrays. Rerun logs a visualization projection rather than every snapshot
field. Its SDK flush is not a complete machine-output handoff.

DESIGN DECISION: the first-release consumer is a same-process evaluator. Timestamp its
receipt after it validates and acknowledges the complete versioned immutable product result,
using the same monotonic clock as scheduled arrival. Persist receipts and audit evidence;
full-payload disk persistence is not part of this endpoint. Output is evidence-only, not
planner-facing or navigation-safe. The complete payload schema, bounded audit behavior and
numeric gates still need a frozen contract. Workload/window approval is explicitly deferred.
See `docs/o-001-output-boundary-audit.md` and decision 0002.

Current-slice FACT: paced replay now passes the in-memory `FrameResult` to a
synchronous diagnostic consumer. It checks and hashes the existing single-frame
payload, then returns a receipt before the audit JSONL flush. This is not the
approved future complete product output or consumer.

DESIGN DECISION: Rerun recording and display are excluded from the 100 ms deadline;
measure them in separate runs. An optional CuPy backend now handles range projection
and cell reductions. It has not been exercised on a CUDA device, and the other current
stages still run on CPU. This is an implementation slice, not complete-path evidence.

## Evaluation boundaries

Use labels only in oracle evaluation and scoring. SemanticKITTI semantic and moving-object tasks provide point labels, but they do not by themselves certify 3D detector boxes, track identity, ray free-space correctness or navigation safety. Add curated obstacle and visibility fixtures plus a separate labeled set or human-reviewed samples for those outputs. Compare the learned path, oracle upper bound and geometry baseline under the same filtering and map path. Report unknown coverage and false-free errors, not only IoU.

## Alternatives and blockers

A specific network architecture, framework, checkpoint source, physical NVIDIA release host, association algorithm and ray discretization remain technical decisions under the selected CUDA platform direction and unresolved D-002/D-005 gates. Choose using measured accuracy, license, integration cost and complete-path latency. Do not commit to an external model or claim real-time performance from model-only benchmarks. D-003 selects evidence-only output; evidence-quality and recovery criteria remain open. D-004 defers planner-facing output and live sensor integration beyond the first release. The proposed performance workload is also explicitly deferred pending approval.

2026-09-25 design direction: the user selected a CUDA frame path for O-001. Preserve
`MappingEngine.process` and the existing data contracts while drafting a device-resident,
bounded-buffer backend with CPU comparison and complete-path timing. This Intel Arc laptop
cannot execute CUDA. The NVIDIA target, release-machine decision, stage placement and parity
tolerances were initially BLOCKED pending the hardware decision and frozen acceptance contract. See
`docs/o-001-cuda-frame-path.md`.

2026-09-25 platform decision: the CUDA release gate moves to an identified NVIDIA host,
while the Intel laptop remains the CPU reference. Host inventory/access, stage placement,
parity tolerances and the complete-path acceptance contract remain open. The later handoff
review selected the evaluator receipt and evidence-only output, not the remaining gates. See
`docs/decisions/0002-cuda-replay-release-platform.md`.
