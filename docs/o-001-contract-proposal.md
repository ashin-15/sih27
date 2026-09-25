# O-001 complete-path contract for review

Status: DESIGN PROPOSAL, 2026-09-25. This document makes the remaining choices reviewable. It is
not an approved release specification, implementation record, or AC-008 result. The selected
100 ms, zero-miss, same-process evaluator-receipt boundary and evidence-only scope are recorded
in [decision 0002](decisions/0002-cuda-replay-release-platform.md). The product owner has
explicitly deferred approval of the workload/window and point cap below.

## Two milestones

| Milestone | Platform | Required evidence | Claim allowed |
| --- | --- | --- | --- |
| CPU development | Current Core Ultra 9 185H laptop, geometric path and then each approved product stage | Exact-output regression, stage and receipt timing, resource trends, failure fixtures | A measured CPU result for the named implemented slice only |
| CUDA release | Identified and inventoried NVIDIA host, complete product path, pinned model | All blocking ACs, full paced workload, complete receipts, quality and resource gates | First-release replay acceptance if every gate passes |

CPU work can proceed under a separately approved bounded slice. A CPU pass does not establish
CUDA parity or release acceptance. Lack of NVIDIA access does not block CPU implementation, but
AC-008 on the selected CUDA release platform remains NOT VERIFIED until that host is available.
Any change of release platform needs a new recorded product decision.

## Proposed immutable product result, version 1

The same-process evaluator receives one `ProductFrameResult` per accepted input scan. All arrays
are read-only at handoff and remain alive until synchronous receipt. Coordinates and units are
declared in the manifest, and every array's row order is part of the schema. Required fields:

| Group | Required fields and checks |
| --- | --- |
| Identity | `schema_version`, `run_id`, `sequence_id`, `frame_id`, `scan_timestamp_ns`, `scheduled_arrival_ns`, `source_scan_digest`, `config_digest`, `code_revision`, `backend`, `checkpoint_sha256` or explicit `none` in diagnostic mode. Version must be supported; frame IDs and timestamps strictly increase within a sequence. |
| Input and pose | Raw/accepted/rejected point counts, accepted original `point_ids` (unique nonnegative int64), rejection reason counts, pose matrix and source/quality, calibration ID and digest, coordinate frame and units. Counts conserve input; finite transforms and declared convention are mandatory. |
| Per-point prediction | Accepted-order `semantic_id` in 0..19, `semantic_confidence` finite in [0,1], semantic support/unknown reason, motion state and confidence or unknown. All arrays have exactly the accepted point count. Missing labels may not default to a known class. |
| Instances | Unique frame-local instance ID, semantic ID/confidence, finite 3D bounds and center, point-ID support, observation timestamp and uncertainty/status. Support IDs must be a subset of accepted IDs; overlapping support must be explicitly allowed by a schema flag. |
| Tracks and motion | Sequence-unique track ID, associated instance ID or prediction-only status, birth/last-observed times, lifecycle, world-frame velocity and covariance or explicit unknown, association confidence and supporting frame IDs. No velocity claim on first observation. |
| Temporal map | Cell level/index/extent with nonoverlapping ownership; occupancy state `occupied`, `observed_free`, `unknown`, `stale` or `ambiguous`; semantic evidence, last-observed time, evidence source, ray support counts, obstacle support, uncertainty and conflict flags. Each free cell must reference a valid traversing beam/return proof; missing or occluded evidence cannot create free state. |
| Diagnostics | Stage timings including load, ground, model, detector, association, visibility, fusion, transfer and evaluator; queue depth/age, dropped and invalid counts, map/track size, process RSS and device memory sample/status. Diagnostic fields cannot substitute for payload fields. |

The evaluator checks schema/version, shape/dtype/range, read-only ownership, point alignment,
unique IDs, finite geometry, provenance hashes, time/pose consistency, sequence ownership,
cell nonoverlap, proof references and conservation before issuing a `Receipt` containing
`run_id`, `sequence_id`, `frame_id`, `result_digest`, `receipt_monotonic_ns`, validation status
and error code. It must inspect actual arrays and references, not trust a digest-only report.
Rejecting an invalid result produces a failure receipt, never a successful handoff. Receipt
success is timestamped after all validation. A later mutation or aliased writable buffer is a
contract failure. This is a proposed schema; exact Python types, array layout and digest
canonicalization must be frozen in the technical design before T-002.

## Proposed replay and timing protocol

1. Pin source revision, package lock, model checkpoint and license, dataset manifest and
   scan/label hashes, config, backend, host CPU/GPU/RAM, driver, power mode and clock source.
2. Construct the engine and load the checkpoint before time zero. A separate unscored warmup
   uses a disjoint sequence or synthetic input, then resets all sequence state. It must not
   consume or skip any selected scan. Record warmup input and duration.
3. Proposed accepted windows are complete ordered SemanticKITTI sequences 08 (4,071 scans)
   and 00 (4,541 scans), each paced at 10 Hz from its first scan with a fresh engine. Run the
   sequence 10 frame 206 129,392-point scan as a separate cold-start first-frame boundary.
   Proposed input cap is 130,000 points; above-cap scans are explicit rejects, never truncation.
   These sequence, window and cap selections are still pending product approval. Sequence 08
   can serve semantic validation; sequence 00 is a performance workload, not held-out quality.
4. `scheduled_arrival_ns = t0 + frame_index * 100,000,000` on one monotonic clock. Age is
   successful evaluator receipt time minus scheduled arrival. Count every selected scan,
   including the first. A receipt after 100,000,000 ns is a miss; an error/missing receipt is
   a miss and a failed gate. Report all ages and p50/p95/p99/max. Also report actual source
   load/ready time, service time and schedule lag separately.
5. Exactly one successful complete receipt is required per valid selected scan in order.
   Count duplicates, skips, source failures, invalid inputs, rejected results, queue overflows
   and late receipts separately. The accepted clean-data window requires zero of each. A
   deliberately invalid/above-cap fixture must yield a classified failure, never a success
   receipt. Do not silently remove invalid scans from the denominator.
6. Continue after a timing miss for diagnostic coverage and mark the gate failed immediately.
   Stop safely on irrecoverable source, evaluator, resource or audit failure. Never turn a
   stale result into a fresh one by changing its arrival timestamp.

## Proposed bounded scheduling, audit and failure contract

- Use a bounded ordered work queue and bounded sequence-owned temporal state. A finite queue
  cannot absorb sustained service below 10 Hz. Queue admission, blocked source time and oldest
  queued age are measured. Full queue is a gate failure; durable ingress, if later selected,
  preserves acquisition but cannot make a late result meet the 100 ms deadline.
- Record one receipt and one audit row per selected scan with monotonically increasing IDs.
  The audit row includes schema/result digest, all stage/queue/age data, rejection/miss flags,
  resource samples and a reason code. Write failures fail the gate and stop cleanly. Report
  flush and disk sync time separately from the selected receipt deadline; cap audit buffering
  and include its downstream scheduling cost. At run end, drain the bounded audit queue,
  flush and sync files, reopen them, and verify contiguous IDs, counts and digests before
  declaring a valid run. A timeout or incomplete drain fails the gate.
- On invalid pose/time/calibration, changed checkpoint, nonmonotonic frame, exceeded capacity
  or sequence reset, return an explicit error or degraded unknown result according to a
  frozen reason table. Never emit unsupported free or measured motion. Do not reuse the
  previous sequence's tracks/map/ground estimator.
- A model failure, process crash, storage exhaustion or physical power fault has no proven
  recovery behavior today. Fault injection and restart/replay tests are required before a
  resilience claim; the replay release may fail closed and require operator restart.

## D-005 measurement and threshold worksheet

These are candidate gates, not measured quality claims. The structural limits below follow
the selected zero-miss rule and conservative evidence semantics. Statistical quality and
hardware resource ceilings remain product choices that need measured baselines and approval.

| Dimension | Proposed metric and denominator | Candidate pass rule or decision still required |
| --- | --- | --- |
| Integrity and timing | Valid selected arrivals, successful receipts, misses, duplicate/skip/drop counts; scheduled arrival to receipt | Zero missing/invalid successful outputs, zero duplicate/skip/drop, zero age over 100 ms across each complete accepted window (selected deadline; proposed window). |
| Semantic | Official learning-ID mIoU and per-class IoU on held-out sequence 08; near/mid/far strata and unknown rate over accepted points | Numeric mIoU/per-class/range floor and unknown ceiling TBD after a pinned compatible checkpoint baseline. Unknown is always reported, never counted as correct known class. |
| Detection | Recall and false positives per scan by class, near/mid/far range and thin/small/large size; publish annotation protocol and support counts | Numeric floors/ceilings TBD after a reviewed labeled object set. SemanticKITTI point labels alone do not define the needed obstacle-box truth. |
| Tracking | ID switches per trajectory, fragmentation, false tracks and track recall on held-out labeled sequences/fixtures | Numeric limits TBD with track annotation and lifecycle policy. Deterministic fixture invariant: no ID reuse across live tracks or sequence leakage. |
| Motion | Static-world velocity error and moving-object velocity error/unknown coverage by range; moving IoU where labels support it | Numeric limits TBD after time/pose error budget and labeled motion reference. First-frame measured-motion claims: zero allowed. |
| Free-space | False-free cells / evaluated truly occupied or unobserved cells, by range and visibility case; unknown/stale coverage and recovery frames after valid re-observation | Zero unsupported-free outputs on deterministic no-return/occlusion/out-of-FOV fixtures. Held-out false-free ceiling, stale TTL and recovery window TBD; no navigation-safe inference. |
| Resources | Peak process-tree RSS, peak GPU allocated/reserved memory, swap delta, map cells/tracks, queue depth/oldest age, receipt/audit bytes, disk free reserve | Numeric RSS/VRAM/disk/state caps TBD from the named host and full-path pilot. Queue must be bounded, not grow through the window; no run-induced swap growth. |

The proposed threshold-setting protocol is: pin the model and annotation set; run an unscored
development pilot on the CPU and later named CUDA host; publish distributions and failure
examples; choose numeric floors/ceilings with the product owner; freeze them before final held-out
evaluation. The final evaluation data must not be used to tune thresholds. None of these
quality and resource limits may be declared passed from current geometric receipts.

## Implementation dependencies after approval

T-002: freeze exact contract types, canonical digest and evaluator; T-003: pin licensed
SemanticKITTI-compatible checkpoint and implement learned semantics; T-004: obstacle instances
with reviewed ground truth; T-005: pose-aware association and measured motion; T-006: beam/ray
proof and bounded temporal map; T-007: complete output, audit and viewer; T-008: parity,
profiling and full gate. Optimize from measured stage/queue profiles. A native GIL-release
slice has separate authorization; it does not approve T-002 through T-007.

## Approval checklist

- [ ] Select the CPU development gate versus the later CUDA release gate relationship and
      identify the physical CUDA host when available.
- [ ] Adopt or revise the proposed 10 Hz sequences, full windows and 130,000-point cap.
- [ ] Select a compatible checkpoint, terms, class map and first model milestone.
- [ ] Freeze exact payload types, reason codes, audit bounds and failure/drain rules.
- [ ] Approve numeric semantic, detector, track, motion, free-space and resource limits after
      their required baselines, or explicitly approve a staged contract with a defined pilot.
- [ ] Explicitly approve the resulting PRD, technical design and acceptance contract for
      product implementation. AC-008 requires implementation plus a saved zero-miss run.
