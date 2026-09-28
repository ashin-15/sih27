# Drishti-2.5 perception technical design

Status: T-002 interface contract frozen 2026-09-26; T-003 semantic CPU slice
approved 2026-09-27. Other product stages and full release design stay Draft.

## Frozen T-002 result and receipt, version 1

`src/drishti/product_result.py` owns `ProductFrameResult`, `CellEvidence`, `InstanceEvidence`,
`TrackEvidence`, `BeamProof`, `ProductDiagnostics` and `ProductReceipt`. `schema_version=1`
is exact; unknown versions are rejected. All fields are required Python dataclass fields.
`stage=diagnostic` is the existing geometric producer and may only emit unknown semantic/motion,
no instances/tracks/beams, and unknown/ambiguous cells. `stage=complete` is reserved for future
learned/temporal producers and requires checkpoint and calibration hashes; a schema-valid
receipt alone does not prove quality or timing.

- Identity: nonempty run/sequence, nonnegative ordered frame ID and timestamp in ns,
  optional scheduled monotonic arrival ns, SHA-256 source scan/config/code/checkpoint hashes,
  CPU/CUDA backend. The present CLI's `code_revision` value is its source-file SHA-256, not
  a claimed Git commit. The source digest includes sequence, frame ID, timestamp, raw scan
  point/ID buffers and pose, but excludes oracle labels.
- The approved 130,000 raw-point release cap is checked for `stage=complete`; above-cap
  inputs receive an explicit rejection receipt. The current diagnostic CLI retains its
  pre-existing configurable 150,000-point default and cannot be used as the release gate.
- Input: `Accounting` conserves input and projection points; accepted original `point_ids`
  are sealed contiguous int64 in the same relative order as the input. The sealed 4x4 float64
  pose matches the input. Pose source, explicit verified/degraded/unverified quality,
  calibration ID/digest, fixed FLU map coordinate convention and metre/nanosecond units are
  explicit. Diagnostic pose quality is unverified; calibration may be absent in that mode only.
- Per point: accepted-order uint8 semantic ID (0..19), uint8 support and unknown reason,
  float64 confidence in [0,1], uint8 motion state and float64 confidence. ID 0 requires a
  reason; known IDs require support. Diagnostic mode emits 0/NO_MODEL and unknown motion.
- Instances/tracks: immutable tuples of typed records. Instance IDs are unique per frame,
  support IDs subset the accepted IDs, and overlap is rejected unless the explicit
  `allow_overlapping_instance_support` flag is true. Geometry is finite with center inside
  bounds. Track IDs
  are unique per result, associated instance IDs must exist, and velocity requires at least
  two supporting frames and a 3x3 covariance tuple. Future stages must add lifecycle and
  cross-frame identity tests before using this as tracking evidence.
- Cells: `cell_sizes_cm` begins at 5 cm and contains nested integer widths. Parallel sealed
  arrays carry level/int64 indices, occupancy enum, semantic ID/support, observed timestamp,
  source, ray/obstacle counts, uncertainty, conflict and free-beam reference. Ownership is checked
  across levels using parent indices; duplicate or overlapping cells are rejected. Unknown
  uncertainty uses -1, never NaN. Observed-free requires a beam referencing an accepted
  return, matching transformed return coordinates, and a segment through cell interior
  before a return outside the cell, with sensor origin matching pose and no accepted return
  inside the claimed free cell. This validates reference geometry only; it does not yet
  establish a full visibility/occlusion policy or AC-006.
- Diagnostics: explicit stage timings or unavailable values, queue/drop/invalid counters,
  map/track size, RSS/device sample or unavailable status. Receipt validation duration is
  measured separately after consuming the result. These fields do not replace payload fields.

Arrays must be C contiguous, little-endian/native on this little-endian runtime, and backed
by immutable `bytes`, which prevents writable aliases after receipt. `canonical_result_digest`
is SHA-256 over the entire dataclass tree encoded as UTF-8 JSON with sorted keys, compact
separators and no NaN. Arrays encode `dtype.str`, shape and C-order payload hex; tuple order is
retained. Changing any field, including diagnostics, changes the digest. This is a Python
version-1 contract, not a cross-language wire format.

`InProcessProductEvaluator.receive` checks the actual payload synchronously and stamps
`receipt_monotonic_ns` after validation/digest. It returns `accepted` with a digest or
`rejected` with a reason and no digest. Only acceptance advances sequence/frame ownership.
The `--evaluate-product-contract` CLI option builds diagnostic results immediately after the
same `MappingEngine.process` used by replay/demo/viewer and records receipts in `frames.jsonl`
under report schema 3. It does not replace the existing `--check-100ms` current-frame diagnostic
receipt or make that timing an AC-008 measurement. Audit fsync, bounded queue/drain, complete
producer and release timing remain T-007/T-008 work.

## Approved T-003 semantic-only CPU path

`MappingEngine.process` accepts `Mode.LEARNED` with a `SemanticPredictor`.
It filters accepted points exactly once, passes their sensor-frame float32
x/y/z/intensity and int64 IDs to the predictor, then aggregates all accepted
points into the same cell path. `DatasetSource` in learned mode never opens
label files. Missing or nonfinite accepted intensity rejects the frame. Oracle
annotations are not consulted by the learned engine or source.

`learned.py` verifies the local checkpoint and safe tensor-export SHA-256,
requires a clean checkout of the pinned FRNet revision, and launches a
persistent Python 3.8 CPU worker. The worker reads only per-scan accepted
points from a private temporary directory, applies the authors'
`RangeInterpolation` and model preprocessor, strictly loads all 421 state
keys, and returns original-point logits. Torch 1.8 SyncBatchNorm evaluation
uses stored statistics through CPU `batch_norm`. The host validates count,
dtype, channel range and finite score, remaps channels 0..18 to learning IDs
1..19 and channel 19 to unknown 0, then seals the arrays. The maximum
softmax score is not calibrated uncertainty. A worker timeout or invalid
output fails the run visibly.

`product_result.py` retains version-1 `stage=diagnostic` and reserved
`stage=complete` behavior. Version 2 adds `stage=semantic`, with accepted-order
point IDs/classes/scores/reasons and cell semantic evidence. It requires
checkpoint/export SHA-256, upstream revision, class-map version and model
stage time. Its motion, instances, tracks, beams and free-space claims remain
absent; occupancy is unknown or ambiguous. The same-process evaluator returns
a version-2 receipt before audit. `--write-predictions` writes one raw-ID
SemanticKITTI file per input scan under the new run directory, filling any
rejected input point with raw unknown 0. Official sequence scoring uses the
upstream SemanticKITTI API; `drishti.evaluation` adds range/unknown breakdowns.
No numeric D-005 quality threshold is frozen. See decision 0004, experiment
0024 for implementation and [experiment 0025](../../../../docs/research/experiments/0025-t003-full-sequence08.md)
for the complete held-out semantic baseline. This CPU slice is not a
complete-result release producer.

Status: The remaining design below is Draft. Based on the draft PRD.

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

The [O-001 contract proposal](../../../../docs/o-001-contract-proposal.md) details the proposed
complete immutable result groups, validation/receipt sequence, bounded ordered scheduling,
audit drain and fail-closed cases. Exact types, array layout, canonical digests and reason codes
remain to be frozen. Implementation of that future evaluator is still blocked by contract
approval; this proposal does not redefine the current diagnostic `FrameResult`.

DESIGN DECISION: Rerun recording and display are excluded from the 100 ms deadline;
measure them in separate runs. An optional CuPy backend now handles range projection
and cell reductions. It has not been exercised on a CUDA device, and the other current
stages still run on CPU. This is an implementation slice, not complete-path evidence.

## Evaluation boundaries

Use labels only in oracle evaluation and scoring. SemanticKITTI semantic and moving-object tasks provide point labels, but they do not by themselves certify 3D detector boxes, track identity, ray free-space correctness or navigation safety. Add curated obstacle and visibility fixtures plus a separate labeled set or human-reviewed samples for those outputs. Compare the learned path, oracle upper bound and geometry baseline under the same filtering and map path. Report unknown coverage and false-free errors, not only IoU.

## Alternatives and blockers

FRNet and its framework/checkpoint source are selected for the bounded D-002 semantic CPU development slice. Exact public checkpoint bytes, separate weight terms, a physical NVIDIA release host, association algorithm, ray discretization and D-005 numeric gates remain open. Choose later stages using measured accuracy, license, integration cost and complete-path latency. Do not claim real-time performance from model-only benchmarks. D-003 selects evidence-only output; evidence-quality and recovery criteria remain open. D-004 defers planner-facing output and live sensor integration beyond the first release. The proposed performance workload is also explicitly deferred pending approval.

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
