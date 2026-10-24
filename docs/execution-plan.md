# Execution plan

Status: CPU reference and optional CUDA paths are implemented; the RTX 4050
laptop is the selected replay release host. T-002 is DONE for its bounded
schema/evaluator slice; T-003 remains IN PROGRESS under explicit owner
approval. Full-release quality, resource and CUDA timing gates remain draft
or unverified. Status vocabulary: TODO, IN PROGRESS, BLOCKED, VALIDATION, DONE.

## Objective

Build a standalone, evidence-backed LiDAR perception and adaptive 2.5D map pipeline. The milestone chain is contract -> learned perception -> object evidence -> temporal reasoning -> conservative map -> complete-path validation.

2026-10-24 G0 implementation pass: the staged approval already selected complete
sequences 08/00, the sequence 10 frame 206 cold start and the 130,000-point
cap. Schema-6 `stage=complete`, the `drishti-g0-v1` fused-cell payload,
executable D-005 v0.2 checks and host-derived resource ceilings are now
implemented. D-005 v0.2 and the resource ceilings were approved on 2026-10-24.
T-001 remains IN PROGRESS because independent final quality data, complete
producer/replay integration and controlled full-path resource evidence are not
complete. See the [work log](work-log.md) and [decision 0012](decisions/0012-g0-complete-result-and-d005-contract.md).

The [production readiness roadmap](production-roadmap.md) orders the remaining
work into contract, quality, map/output, 100 ms feasibility and release gates.
It cross-checks each gate against SIH26053. No additional task or release gate
became DONE from the roadmap alone.

## 2026-10-14 submission readiness audit

FACT: Of the 20 tasks below, six bounded or historical tasks are DONE
(T-000/T-010/T-011/T-012/T-013/T-002), ten remain IN PROGRESS, T-009 is
BLOCKED, and T-015/T-016/T-018 are TODO. The statuses below apply to their
stated scope; a completed CPU slice is not a complete SIH26053 release.

VERIFIED this audit: the current working tree passes 147 tests with four
skipped, Ruff lint/format, strict mypy, source/wheel build, and a two-frame
synthetic CLI run with the diagnostic temporal map from both source and a
separately installed wheel. Input/map digests and fused summaries matched;
both runs retained a fixed 53,737,911-byte temporal allocation and exceeded
the configured 100 ms budget on both frames. A regression fixture reproduced
and fixed a temporal evidence error where an old free observation reappeared
after a newer obstacle hit.
See [testing](testing.md) and the [work log](work-log.md).

NOT VERIFIED for submission: the frozen complete result and numeric D-005
contract; independent final semantic, obstacle, tracking, terrain and motion
quality; T-015 speed/direction foveation; T-016 exact merge/split and fair
uniform-3D memory comparison; T-018 measured moving/static state; complete
receipt and viewer acceptance; and the full paced zero-miss 100 ms gate on the
RTX 4050. [The production readiness roadmap](production-roadmap.md) gives the
gate sequence and evidence requirements. No release status is promoted by
this audit.

2026-10-14 follow-up: a pinned-action Windows/Linux package-quality workflow
is defined under O-009; local model-enabled checks pass, while its first hosted
run and release/security policy remain pending.
[Experiment 0044](research/experiments/0044-temporal-cost-and-neighbour-screen.md)
found 30/30 matching synthetic map outputs with and without diagnostic fusion,
while the fused stage reached 324.454 ms p50 as published cells grew. An exact
neighbour-index candidate saved only about 12.5 ms in one late-frame isolated
screen and was not integrated. T-008/O-006 remain IN PROGRESS.

T-008 update 2026-10-15: [experiment 0047](research/experiments/0047-temporal-neighbor-integration.md)
integrates an exact diagnostic temporal neighbour lookup. A same-state
isolated A/B reduced three-level step calculation from 149.005 to 117.044 ms;
30 saved synthetic records retained input/map digests, accounting and fused
summaries. The complete path remains above the 100 ms goal and T-008 stays
IN PROGRESS.

T-008 follow-up 2026-10-15: [experiment 0050](research/experiments/0050-visibility-chunk-screen.md)
retains a 16,384-beam CUDA visibility batch after 24 accepted current-path
receipts, six-frame output parity across four runs, and a full-evidence CUDA
boundary fixture. It reduced the small-run visibility medians but did not
meet 100 ms; controlled tails and peak memory remain open.

T-008 screen 2026-10-13: [experiment 0042](research/experiments/0042-visibility-chunk-screen.md)
retained a larger internal visibility beam chunk with exact six-frame map
digests and a chunk-boundary evidence fixture. Warm visibility median improved
in the small run, but the whole path still missed every configured 100 ms frame
budget. T-008 stays IN PROGRESS; AC-008 is not met.

RQ-004 research 2026-10-13: [experiment 0043](research/experiments/0043-100ms-feasibility-options.md)
prioritizes a controlled critical-path trace and exact-output model,
visibility, temporal/map and evaluator screens. No candidate speedup or
complete-path deadline pass was measured in this research-only update.

| Task | Milestone and objective | Why and dependencies | Components and implementation notes | Acceptance and validation | Status |
| --- | --- | --- | --- | --- | --- |
| T-000 | Bootstrap persistent agent context | Future sessions need recoverable facts and evidence. No product dependency. | Root `AGENTS.md`, context, assessment, interfaces, testing, research and decision templates. | Required files exist; claims reviewed against source; 42 tests, lint, format, types, build and synthetic demo checked. | DONE |
| T-010 | Standalone project workflow and archive cleanup | New research and blockers need a durable home. No product dependency. | Local `AGENTS.md` rules, work log, open-item register, research modules, process ADR, retired identifier redaction. | Links and archive provenance inspected; JSON/XML parse; identifier search clear in current working-tree content. | DONE |
| T-011 | Research and measurement foundation | Model selection and future gates need task-specific evidence. No product implementation dependency. | Source/claim screen, model candidate register, current-path replay protocol, evidence and impact updates. | Primary sources inspected; claims bounded; protocol records provenance, metric and report checks. Real-data execution is a separate open item. | DONE |
| T-012 | Profile current replay bottleneck | The measured current path cannot sustain the 10 Hz development workload. Research only. | Reproducible CLI run, timing harness, `cProfile`, digest/accounting comparison and bounded hotspot report. | Report distinguishes engine, mapping, digest and audit costs; harness outputs match CLI on overlapping frames. | DONE |
| T-013 | Evaluate cell-grouping alternative | T-012 identified row-wise grouping as the dominant hotspot. No production approval implied. | Isolated benchmark of grouping candidates with negative-coordinate, level, overflow and ordering checks. | Exact ownership/inverse and snapshot digest equivalence plus repeatable latency comparison in experiment 0003. | DONE |
| T-014 | Test durable 10 Hz ingestion and ordered scheduling | The existing audit-inclusive worker is slower than 10 Hz. User-authorized technology research is active; an approved live-source and overload policy is required before production integration. | SQLite/MCAP, concurrent replay and SQLite faults are in experiment 0008. A C++ SQLite/LMDB/custom-log comparison, long paced runs and LMDB injected faults are in experiment 0009. A separate scheduled producer with a volatile two-frame queue is in experiment 0013; it filled 93 times over 100 scans. Next test bounded ordered work with sustained concurrent durable storage/readers outside the active product path. | Real sensor retry/ack, physical disk and power faults, contiguous acknowledged IDs, exact digests, sustained throughput, queue age and capture-to-output tails on target hardware. | IN PROGRESS (research only) |
| T-001 | Freeze product and measurement contract | D-001 replay-first RTX 4050 host, strict 100 ms zero-miss deadline, same-process complete-product evaluator receipt, complete sequences 08/00, sequence 10 frame 206 cold start and 130,000-point cap are selected. D-002 selects FRNet for bounded semantic CPU development. D-003 selects evidence-only output; D-004 defers live/planner use. G0 implementation `drishti-g0-v1` / schema 6, approved D-005 v0.2 checks and approved host-derived resource ceilings are present. Independent final labels, complete producer/replay integration and controlled full-path resource evidence remain open. The current Intel laptop is the CPU reference. The present JSONL is audit metadata only. | PRD, technical design, acceptance, [G0 threshold bundle](d-005-g0-thresholds-v0.2.md) and [decision 0012](decisions/0012-g0-complete-result-and-d005-contract.md). | Signed-off stable FR/AC set with no blocking TBD; complete producer/replay wiring and final evidence. | IN PROGRESS |
| T-002 | Freeze interfaces and evaluation harness | The product owner approved the bounded CPU slice. Version-1 diagnostic result and same-process evaluator are integrated from the handoff worktree. | `product_result.py`, CLI schema-3 receipts, interfaces and decision 0003. Schema-1 digest compatibility with the handoff was checked. | AC-013: final broader suite 71 passed, 3 skipped; strict mypy/Ruff/build; installed-wheel 2/2 diagnostic receipts accepted and release gate false. | DONE for T-002 slice |
| T-003 | Learned semantic inference and reproducible model workflow | The owner approved the semantic-only CPU slice on 2026-09-27. The checkpoint and source are hash/revision pinned; T-002 is integrated. | Isolated FRNet worker, label-free `Mode.LEARNED` on the shared engine path, schema-2 semantic-only receipts, raw-ID prediction files and supplemental range evaluator. See [decision 0004](decisions/0004-frnet-semantic-cpu-slice.md), [experiment 0025](research/experiments/0025-t003-full-sequence08.md) and [experiment 0026](research/experiments/0026-t003-cpu-semantic-verification.md). | AC-014 implementation evidence: source and wheel replay, point alignment, tests/lint/types/build; E-052 rechecked the current CPU path. E-051: all 4,071 held-out sequence 08 scans scored officially at 0.675469 mIoU; range report saved. D-005 v0.2 gates are approved, but independent final semantic/range evidence, separate weight terms and exact public checkpoint-byte identity remain open. 2026-09-30: an in-process PyTorch runtime ([decision 0009](decisions/0009-release-host-and-torch-frnet.md), [experiment 0034](research/experiments/0034-release-host-torch-frnet.md)) reproduces the authors' scan-000000 prediction byte for byte on CPU and runs on the release GPU; its GPU full-sequence score is 0.675473 mIoU versus 0.675469 for the authors' runtime ([experiment 0035](research/experiments/0035-t006-gpu-sequence08.md)). | IN PROGRESS |
| T-004 | Obstacle instance detection | Cell nonground envelopes are not objects. Depends T-002/T-003. | The [approved CPU candidate slice](t-004-obstacle-candidate-proposal.md) adds deterministic observed-point components and schema-3 receipts; [decision 0005](decisions/0005-obstacle-candidate-cpu-slice.md). | AC-015 bounded implementation is verified with [experiment 0028](research/experiments/0028-t004-saved-prediction-eval.md). AC-002 traffic-participant numeric targets are approved; independent final/wider-obstacle labels and quality acceptance remain open. | IN PROGRESS (bounded CPU slice verified; full quality open) |
| T-005 | Tracking and motion | Semantic class is not measured motion. Depends T-004 and timestamp/pose contract. | [Approved bounded tracking contract](t-005-tracking-proposal.md) and [decision 0006](decisions/0006-tracking-cpu-slice.md) add sequence-owned known-thing association, explicit lifecycle, schema-4 receipts and unknown velocity. | [AC-016 bounded CPU implementation](research/experiments/0030-t005-association-eval.md) accepted with caveats: source/wheel replay and 200-frame diagnostic; full AC-004/005 quality remains open. | IN PROGRESS (bounded CPU slice verified; full quality/motion open) |
| T-006 | Visibility and temporal map | Single-frame map cannot prove free space or maintain history. Depends T-002/T-004/T-005. | Bounded timestamped cell state, ray evidence, unknown/stale/occupied/free, safe conflict rules. [Experiment 0037](research/experiments/0037-t006-visibility-screen.md) screens SemanticKITTI completion voxels for false-free scoring; the [draft T-006 contract](t-006-visibility-proposal.md) proposes a current-scan-only schema-5 slice with temporal fusion/stale deferred. | AC-003/006; no-return, occlusion, re-observation, ghost and capacity fixtures. Numeric false-free gate is O-003/D-005. | IN PROGRESS (bounded current-scan slice approved in [decision 0007](decisions/0007-visibility-cpu-slice.md) and implemented; fixture/package checks pass; free-cell cap raised to 262,144; full sequence-08 GPU replay accepted, static false-free 0.549% over 815 voxel frames and real CPU/CUDA parity 30/30 ([experiment 0035](research/experiments/0035-t006-gpu-sequence08.md)); installed-wheel replay and numeric false-free gate open. Temporal slice approved in [decision 0011](decisions/0011-temporal-fusion-terrain-dashboard.md) and implemented 2026-10-05 as a diagnostic fused layer: rolling fixed 53.7 MB windows, per-cell Kalman ground height, log-odds occupancy with STALE and ghost clearing; fixtures pass; real sequence-08 runs in [experiment 0038](research/experiments/0038-temporal-drivability.md); not yet in the receipt-validated schema) |
| T-007 | Viewer, audit and machine contract | New states require visible provenance and stable output. The evaluator receipt is selected; full implementation depends T-003 to T-006 and the T-001 complete payload schema. The [semantic dashboard class visibility slice](t-007-semantic-dashboard-proposal.md) is accepted as current-snapshot UX evidence; it does not unblock remaining full T-007 work. | Versioned machine-output schema and handoff, separate audit report, Rerun layers, model/track/visibility metrics. The present Rerun recording is a lossy visualization projection. | SD-AC-001 to SD-AC-004 accepted; AC-007/010 remain for full T-007. | IN PROGRESS (bounded SD class-view slice accepted; full T-007 blocked) |
| T-008 | Full-path performance and release judgment | Budget alone is not a guarantee. Depends T-003 to T-007. Release host identified 2026-09-30: the RTX 4050 laptop ([decision 0009](decisions/0009-release-host-and-torch-frnet.md)). | An optional CuPy projection, cell ownership and reduction backend is integrated and, since 2026-09-29, runs on the release RTX 4050 with exact synthetic CPU parity; optional CUDA candidate and visibility stages are added ([decision 0008](decisions/0008-cuda-learned-stages.md), [experiment 0032](research/experiments/0032-cuda-stage-parity.md)). A light per-frame receipt with sampled deep audit and a schema-5 beam table cut real-frame receipt time from about 3.0 s to 0.47 s ([decision 0010](decisions/0010-light-receipt-sampled-audit.md)). Real-frame GPU path about 0.7-1.1 s before receipt (FRNet 155-450 ms, visibility 330-420 ms, varying with power state); fp16 and GPU interpolation options are implemented but not yet measured on the full sequence. Continue profiling and device residency, bound queues and state, and validate the selected CUDA frame path under a frozen contract. This Intel Arc laptop remains the CPU reference. Rerun is measured separately from the 100 ms gate. See the [CUDA goal brief](o-001-cuda-frame-path.md) and [platform decision](decisions/0002-cuda-replay-release-platform.md). | AC-008/012; CPU/CUDA parity and target hardware complete-path benchmark, including zero deadline misses. | IN PROGRESS |
| T-009 | Live source and navigation boundary, if approved | Depends D-003/D-004 and vehicle/sensor contract. | Calibrated timed input, deskew/quality status, planner-facing safety schema only if selected. | AC-011 plus additional safety criteria if in scope. | BLOCKED |
| T-015 | Anisotropic speed-scaled foveation | Owner-clarified 2026-09-29. The current lattice picks cell size from sensor distance only (fixed 5/10/50 cm radial or square rings). Foveation should give obstacles finer cells as ego speed rises, weighted toward the direction of travel, recomputed for the current pose each frame. Depends on T-003 semantics, T-004 obstacle evidence, pose-derived speed/heading (T-005 timing) and T-006 visibility cells; interacts with T-008 cost. | DESIGN DECISION (owner): no separate output schema; foveation changes only per-frame cell ownership for the current pose, inside the existing multiresolution `CellEvidence` (levels from the configured nested sizes), with the policy captured in the config digest. Score form proposed by owner: `R(p) = w_d D(p) + w_dir Q_dir(p) + w_speed S(p) + w_sem C(p)` (distance, alignment with travel direction, ego speed, semantic/obstacle criticality); higher speed must make obstacle cells finer, never coarser. UNKNOWN: term normalisation and weights, mapping from R to level, fovea shape (forward-elongated regions over square nested cells), hysteresis against resolution flicker, and a rule that a model error in C can only refine, never coarsen, an obstacle. Speed/heading come from pose differences, whose quality is unverified. Must preserve nonoverlapping ownership, accounting conservation, deterministic replay and bounded cell counts. | Research screen and draft contract before code: fixtures for straight/turning ego, stop/start and speed ramps, near/far and critical/misclassified obstacles, seam nonoverlap; cell-count/memory and latency against current rings on the same scans; false-free/occupancy effects once T-006 scoring exists. Weights and limits need owner approval under D-005. | TODO (owner-proposed; no research or contract yet) |
| T-016 | Fixed-capacity layered map store and memory benchmark | SIH26053 asks for a memory reduction against a uniform high-resolution 3D map; the current snapshot is per scan and unbounded in history. Depends T-002, T-006 temporal slice, T-015. | Preallocated rolling window per level (L0 20 m, L1 50 m, L2 200 m), delegated-ownership mask, additive integer statistics so ring changes merge and split exactly; elevation, semantic, occupancy and provenance layers per the [draft representation](t-016-layered-foveated-map-proposal.md). Design estimate about 20.5 MB fixed versus about 576 MB uniform 5 cm 2.5D and about 2 GB uniform 5 cm 3D. | Exact merge/split and nonoverlap tests; memory measured at startup and constant over a full sequence; measured comparison against uniform baselines on the same scans. | TODO (draft design; needs approval) |
| T-017 | Terrain and drivability layer | SIH26053 task 1 requires drivable versus non-drivable terrain, and curbs, potholes and overhangs. The diagnostic fused grid now emits terrain states; release output and acceptance remain open. Depends T-003, T-006, T-016. | Terrain state per cell from drivable semantic class, observed ground, step, slope and overhang clearance; curb, drop and overhang features. Evidence only; unknown never drivable (D-003). | Curb, pothole, overhang, slope and unknown fixtures; labelled drivable-surface metric on sequence 08; numeric thresholds approved under D-005. | IN PROGRESS (decision 0011 terrain layer implemented 2026-10-05: drivable/non-drivable/obstacle/unknown/stale with curb, drop and overhang flags; fixtures pass; experiment 0038 drivable IoU 0.943 / 0.782 and false drivable on obstacle cells 0.10% / 0.09% on two 250-frame chunks; experiment 0040 investigated the recall gap, mainly parking predicted as sidewalk and false interior curb flags; slope/pothole truth, threshold approval and validated release output remain open) |
| T-018 | Motion layer: static versus moving | SIH26053 asks to separate static obstacles from dynamic objects; motion is currently unknown. Depends T-005 motion quality or a moving-object segmentation model. | Per-cell and per-track static, moving or unknown; moving points kept out of static fusion. | Moving-object IoU on SemanticKITTI moving labels; static-wall-under-ego-motion and parked-car fixtures; velocity error where claimed. | TODO (draft design; needs approval) |
| T-019 | Dashboard map layers | SIH26053 requires a real-time colour-coded dashboard showing memory reduction. Extends T-007. Depends T-016 to T-018. | Rerun layers for terrain state, semantic group, occupancy and staleness, moving cells and the memory comparison. | Real recording inspection; viewer excluded from the 100 ms gate and measured separately. | IN PROGRESS (decision 0011: Terrain, Occupancy, Elevation and Free-space tabs, terrain legend and fused counts/memory in the status panel; 100-frame real recording verified by `rerun rrd verify`; visual inspection by the owner and motion layer open) |

Product implementation moves to IN PROGRESS only after approval and prerequisites; research tasks may
progress independently under their stated scope. A task moves to VALIDATION when outputs exist and
evidence is being collected; to DONE only when its AC evidence is inspected. Update this board and
`LOOP.md` after each meaningful loop. Do not duplicate source code here.

Research modules in `docs/research/modules.md` are paired with the task chain. Current blockers
and next evidence live in `docs/open-items.md`; completed work is recorded in `docs/work-log.md`.

## Immediate next step

The approved bounded T-005 CPU association slice passed AC-016 with caveats
on 2026-09-29. [Experiment 0030](research/experiments/0030-t005-association-eval.md)
records source/installed-wheel three-scan parity and the 200-frame development
association baseline. Full AC-004/005 tracking and motion acceptance needs
numeric quality gates, independent final association evidence and calibrated
world-velocity evidence. The approved AC-002 traffic targets also need an
independent final set; curb/overhang labels and numeric gates remain open.

T-003 sequence 08 semantic evaluation is complete. [Experiment 0025](research/experiments/0025-t003-full-sequence08.md)
records the interrupted 219-scan attempt, saved 793-scan prefix and new-engine
continuation. E-051 confirms all 4,071 predictions and accepted receipts,
official mIoU 0.675469, labeled accuracy 0.922835 and supplemental range
metrics. The split cannot prove continuous map state. Run the approved D-005
numeric gates on independent final data and resolve checkpoint terms/identity
before T-003 closure.
[D-005 semantic threshold sheet v0.1](d-005-semantic-thresholds-v0.1.md)
proposes the exact semantic gates and an independent final evaluation route;
the values are approved in D-005 v0.2, and the labeled range set is TBD.

Continue T-001. [O-001's release-profile brief](o-001-release-profile.md) records the selected
NVIDIA platform, strict 100 ms evaluator-receipt endpoint and evidence-only output scope.
The [complete-path contract proposal](o-001-contract-proposal.md) now makes the result schema,
evaluator checks, pacing, audit/failure behavior and D-005 metric worksheet reviewable, but
the proposed values are not frozen. CPU development remains a separate milestone from the
later CUDA release gate.
The bounded T-002/T-003 CPU slices are approved and implemented; the full
release workload, resource/quality gates and audit/failure behavior remain
open before complete product acceptance.
The [handoff review](work-log.md#2026-09-25---handoff-reconciliation-and-partial-output-contract)
records the fresh CPU test result and inspected schema-2 receipt runs, which each missed 100/100
scan deadlines. These do not share the timing endpoint of the earlier minimal screen below.
The earlier T-008 current-slice diagnostic (E-044) buffered audit outside a paced
loop yet missed 28/1,000 and 3/1,000 deadlines on sequences 08/00 at a
minimal in-process result check. T-001 and the authorized CUDA slice of T-008
are IN PROGRESS; full-path acceptance remains blocked until the complete output
contract and prerequisite stages are ready.
E-050 and [experiment 0024](research/experiments/0024-t003-frnet-drishti-integration.md)
now show the pinned FRNet checkpoint running on Drishti's shared learned path
from both source and installed wheel. The official evaluator was checked on
all 4,071 held-out sequence 08 scans (E-051). Release-byte identity, separate
weight terms and D-005 numeric gates remain unresolved; T-003
stays IN PROGRESS until those acceptance items are evidenced.

User-requested CPU concurrency verification E-046 found that installed Patchwork++ 1.4.1
holds the GIL during `estimateGround`; controlled probe 0021 passed. A Python thread pool
alone does not remove this overlap blocker. Any native binding release or separate-process
experiment still needs safety, exact-output and latency checks. No runtime change was made;
T-008/O-001 remain IN PROGRESS. See the [GIL follow-up](research/experiments/0011-current-path-profile.md#2026-09-25-follow-up-installed-patchwork-gil-behavior).
