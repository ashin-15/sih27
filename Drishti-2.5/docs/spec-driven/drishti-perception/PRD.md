# Drishti-2.5 perception product requirements

Status: Draft, awaiting product decisions. Updated: 2026-09-25. Approval: Pending.

## Problem and goal

The current standalone application maps one LiDAR scan at a time. It cannot infer semantic classes, objects, motion, persistent state, or observed free space without ground-truth labels. It records a budget but cannot claim a deadline guarantee. The goal is a versioned, testable perception-to-map pipeline for repeated LiDAR frames, with unknown and unsupported evidence explicit.

## Users and flow

The immediate users are developers evaluating SemanticKITTI replay and operators inspecting a local 2.5D dashboard. DESIGN DECISION: first-release machine output is evidence-only for a same-process evaluator, not a planner or navigation-safe verdict. The expected flow is: load an ordered frame and pose; infer point labels; detect obstacle candidates; update motion and tracks; fuse into bounded map state; publish evidence with provenance, uncertainty and latency.

## Functional requirements

| ID | Requirement | Status |
| --- | --- | --- |
| FR-001 | In geometric production mode, predict a semantic learning ID and confidence or unknown for every accepted original point, without reading evaluation labels. | Draft |
| FR-002 | Detect obstacle instances with stable object type, bounded geometry and evidence provenance; preserve small/thin objects and ambiguous height cases. | Draft |
| FR-003 | Fuse ordered frames in a bounded local map using poses and timestamps; distinguish observed, stale and unknown evidence and reset on a new sequence. | Draft |
| FR-004 | Assign and maintain object track IDs across visible frames, occlusion and reappearance, with explicit confidence and expiry. | Draft |
| FR-005 | Estimate motion relative to the world from sequential observations; publish velocity/uncertainty or unknown. Semantic class and oracle motion labels may not substitute for measured motion. | Draft |
| FR-006 | Publish conservative occupied, observed-free and unknown evidence. Missing returns, occluded areas and out-of-FOV cells remain unknown; a free-space claim requires valid ray evidence. | Draft |
| FR-007 | Publish clear per-frame provenance: model and checkpoint, pose source, point attrition, dropped frames, stage timing, evidence age, state memory, viewer costs and release-gate result. | Draft |
| FR-008 | On the identified NVIDIA CUDA release host, a same-process evaluator must validate and acknowledge each complete versioned immutable replay result within 100 ms of scheduled arrival, with zero misses in the accepted measurement window. | Platform, deadline and receipt endpoint selected; BLOCKED by physical host, complete payload schema, deferred workload/window and resource gates |
| FR-009 | Keep oracle labels isolated to evaluation, preserve the original point order, and evaluate semantic, obstacle, motion, tracking, free-space and latency quality on held-out sequences. | Draft |
| FR-010 | Expose unknown, stale and ambiguous states in the viewer and machine output without silently turning them into drivable space. | Draft |
| FR-011 | First CUDA-backed release uses evidence-only dataset replay on an identified NVIDIA host. The current Intel laptop remains the CPU reference. Live sensor input and planner-facing output are deferred; define their safety, timestamp, calibration and deskew contracts before a later release. | Replay and evidence-only scope selected; full contract remains Draft |

## Success measures

Baseline: no measured learned accuracy, tracking, free-space quality, or full-pipeline latency. The first-release deadline is 100 ms for every scheduled scan with zero misses in the accepted window. Targets for semantic mIoU, obstacle recall by size/range, moving IoU, track ID switches, false-free rate, peak memory and disk are TBD. They must be frozen before implementation acceptance. Synthetic demo and oracle scores are not substitutes.

## Data and use rules

- Keep raw scans and labels read-only. Training uses training sequences only; validation and final evaluation must be held out. The official SemanticKITTI tasks and API define label formats and benchmark metrics: https://semantic-kitti.org/tasks.html and https://github.com/PRBonn/semantic-kitti-api.
- Preserve the 0 unknown/ignored and 1..19 learning-ID convention at every point and cell boundary.
- Do not publish a navigation-safe verdict from a height envelope or from a missing return. Stationary objects remain collision obstacles.
- Record checkpoint, configuration, code and dataset provenance for every evaluated run.

## Scope and non-goals

In scope for the first release: the existing Python package, its CLI, deterministic dataset replay on an identified NVIDIA CUDA host, CPU reference comparison on the current laptop, model adapter and training/evaluation tools, rolling local map, viewer and performance gate. Machine output is evidence-only for evaluation and visualization. Live sensor input, planner-facing or navigation-ready output, autonomous route planning and global georeferencing are out of scope for this release. These selections do not approve implementation of the remaining draft product stages.

## Open product decisions

| ID | Decision | Recommendation | Affected requirements |
| --- | --- | --- | --- |
| D-001 | Target hardware, input rate, complete-path deadline and allowed miss rate. | Implementation hardware is selected: current laptop CPU now, optional NVIDIA CUDA support later; GPU access does not block CPU work. Strict 100 ms and zero misses remain selected, not achieved. Publication is the same-process evaluator's receipt after validation of the complete versioned immutable result; persist receipts and audit evidence. Full-payload disk persistence is not part of this endpoint. The physical NVIDIA validation host and complete payload schema remain TBD; workload/window approval is explicitly deferred. The present diagnostic receipt is not the complete product result. | FR-008 |
| D-002 | First model milestone: semantic-only, joint semantic/motion, or checkpoint integration before training. | Integrate a versioned semantic checkpoint first, then measure a motion model separately. | FR-001, FR-005, FR-009 |
| D-003 | Free-space output for evidence only or navigation consumption in the first release. | Evidence-only selected. No navigation-safe or drivable-space verdict; unknown/stale states remain explicit. Evidence-quality and recovery thresholds still require D-005 approval. | FR-006, FR-010 |
| D-004 | Dataset replay only or live LiDAR and planner integration in the first release. | Dataset replay selected; live LiDAR and planner-facing output deferred beyond the first release. | FR-008, FR-011 |
| D-005 | Numeric release thresholds for every success measure. | Set thresholds after a baseline on held-out data and target hardware; do not infer them from the synthetic demo. | FR-001 to FR-010 |

## Decision log

2026-09-24: The user selected the current machine for development and delegated provisional
workload and latency choices to measured tests. Two 100-frame real-data replays and a 22-sequence
structure check support the D-001 development profile above. The current path missed 100 ms on
every measured frame, so the 100 ms number is an engineering goal, not an achieved requirement or
release approval. See `docs/research/experiments/0001-replay-baseline-protocol.md` and
`docs/research/hardware-targets.md`. D-001's release branch and D-002 to D-005 remain open; the
PRD, design and acceptance contract are not frozen.

2026-09-25: The user selected dataset replay on the current laptop as the first-release
target. This resolves the D-001 hardware/replay branch and D-004 live-input branch only.
At that point, 100 ms was still a development goal; deadline, miss policy, sustained window,
viewer costs, memory/disk ceilings and planner-facing output scope remained open. See
`docs/o-001-release-profile.md`.

2026-09-25: The user selected 100 ms as the first-release deadline for each replay scan.
No missed scans are allowed in the accepted window. The current single-frame path fails
this condition; the full path is not implemented. The measurement window, complete-output
publication boundary, viewer participation and memory/disk ceilings remain unresolved.

2026-09-25: A source-and-artifact audit found that the current frame JSONL contains
digests and metrics, not map arrays, and Rerun contains a visualization projection.
Neither is an approved complete machine output. D-001/D-005 still need a versioned
payload, consumer and successful handoff event; see `docs/o-001-output-boundary-audit.md`.

2026-09-25: The user selected a CUDA frame path as the O-001 implementation direction.
The selected current laptop has Intel Arc graphics and no NVIDIA CUDA device. D-001 must
resolve whether the release gate moves to a named NVIDIA machine or remains on this laptop
with CUDA treated as an experimental backend. The performance contract and implementation
approval remain pending; see `docs/o-001-cuda-frame-path.md`.

2026-09-25: The user delegated and finalized the platform direction: the CUDA-backed 100 ms
release gate moves to an identified NVIDIA host. This supersedes the earlier current-laptop
release hardware choice. The laptop remains the CPU development and parity reference. The
exact physical host, complete output and remaining acceptance fields are still TBD; see
`docs/decisions/0002-cuda-replay-release-platform.md`.

2026-09-25: The user excluded Rerun recording and display from the strict 100 ms deadline;
their costs are evaluated separately. An initial optional CuPy projection/reduction backend
is integrated, but it has no GPU validation on this laptop. The complete-output consumer,
receipt event and remaining product criteria remain open.

2026-09-25 handoff review: The product owner selected a same-process evaluator receipt as
the first-release publication event. The evaluator must validate and acknowledge the complete
versioned immutable product result within 100 ms of scheduled arrival. Receipts and audit
evidence are persisted; full-payload disk persistence is not part of this endpoint. The owner
selected evidence-only output, with no planner-facing or navigation-safe verdict, and explicitly
deferred approval of the proposed full-sequence workload and density cap. Rerun remains outside
the deadline. Payload schema, model, quality thresholds, physical host, resources and explicit
full-contract implementation approval remain unresolved. See
`docs/decisions/0002-cuda-replay-release-platform.md` and `docs/o-001-release-profile.md`.

2026-09-25 CPU-first clarification: The product owner selected the current laptop CPU for
implementation and execution now, with NVIDIA CUDA retained as optional support for later
hardware access. Lack of an NVIDIA device must not block approved CPU-only development.
GPU-specific validation is deferred. This closes the implementation-hardware choice, not
all of D-001: the workload/window, complete product payload and remaining quality/resource
contract are still unresolved, and neither CPU nor CUDA has achieved the release deadline.
