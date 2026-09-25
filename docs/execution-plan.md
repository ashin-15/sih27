# Execution plan

Status: CPU-first implementation on the current laptop is selected, with CUDA as optional future support. Missing NVIDIA access blocks GPU validation, not approved CPU-only work. Contract planning and current-slice O-001 work are in progress. The remaining product stages are blocked until the draft PRD, technical design and acceptance contract under `Drishti-2.5/docs/spec-driven/drishti-perception/` are frozen and explicitly approved. Status vocabulary: TODO, IN PROGRESS, BLOCKED, VALIDATION, DONE. No product feature below is DONE.

## Objective

Build a standalone, evidence-backed LiDAR perception and adaptive 2.5D map pipeline. The milestone chain is contract -> learned perception -> object evidence -> temporal reasoning -> conservative map -> complete-path validation.

| Task | Milestone and objective | Why and dependencies | Components and implementation notes | Acceptance and validation | Status |
| --- | --- | --- | --- | --- | --- |
| T-000 | Bootstrap persistent agent context | Future sessions need recoverable facts and evidence. No product dependency. | Root `AGENTS.md`, context, assessment, interfaces, testing, research and decision templates. | Required files exist; claims reviewed against source; 42 tests, lint, format, types, build and synthetic demo checked. | DONE |
| T-010 | Standalone project workflow and archive cleanup | New research and blockers need a durable home. No product dependency. | Local `AGENTS.md` rules, work log, open-item register, research modules, process ADR, retired identifier redaction. | Links and archive provenance inspected; JSON/XML parse; identifier search clear in current working-tree content. | DONE |
| T-011 | Research and measurement foundation | Model selection and future gates need task-specific evidence. No product implementation dependency. | Source/claim screen, model candidate register, current-path replay protocol, evidence and impact updates. | Primary sources inspected; claims bounded; protocol records provenance, metric and report checks. Real-data execution is a separate open item. | DONE |
| T-012 | Profile current replay bottleneck | The measured current path cannot sustain the 10 Hz development workload. Research only. | Reproducible CLI run, timing harness, `cProfile`, digest/accounting comparison and bounded hotspot report. | Report distinguishes engine, mapping, digest and audit costs; harness outputs match CLI on overlapping frames. | DONE |
| T-013 | Evaluate cell-grouping alternative | T-012 identified row-wise grouping as the dominant hotspot. No production approval implied. | Isolated benchmark of grouping candidates with negative-coordinate, level, overflow and ordering checks. | Exact ownership/inverse and snapshot digest equivalence plus repeatable latency comparison in experiment 0003. | DONE |
| T-014 | Test durable 10 Hz ingestion and ordered scheduling | The existing audit-inclusive worker is slower than 10 Hz. User-authorized technology research is active; an approved live-source and overload policy is required before production integration. | SQLite/MCAP, concurrent replay and SQLite faults are in experiment 0008. A C++ SQLite/LMDB/custom-log comparison, long paced runs and LMDB injected faults are in experiment 0009. A separate scheduled producer with a volatile two-frame queue is in experiment 0013; it filled 93 times over 100 scans. Next test bounded ordered work with sustained concurrent durable storage/readers outside the active product path. | Real sensor retry/ack, physical disk and power faults, contiguous acknowledged IDs, exact digests, sustained throughput, queue age and capture-to-output tails on target hardware. | IN PROGRESS (research only) |
| T-001 | Freeze product and measurement contract | D-001 replay-first NVIDIA platform, strict 100 ms zero-miss deadline and same-process complete-product evaluator receipt are selected. D-003 selects evidence-only output; D-004 defers live/planner use. Physical host, complete payload schema, resources and D-002/D-005 remain open; workload/window/cap approval is explicitly deferred. The current Intel laptop is the CPU reference. The present JSONL is audit metadata only. | PRD, technical design, acceptance; specify dataset splits, classes, remaining thresholds, output boundary and navigation boundary. See the O-001 output-boundary audit and platform decision 0002. | Signed-off stable FR/AC set with no blocking TBD. Review documents and record approval. | IN PROGRESS |
| T-002 | Freeze interfaces and evaluation harness | All features need consistent point IDs, pose/time, class IDs and shared engine path. Depends T-001. | `contracts.py`, `pipeline.py`, `semantics.py`, `docs/interfaces.md`; design versioned prediction/output contracts and same-path evaluator. | AC-001, AC-009; alignment/unknown/leakage fixtures and wheel replay. | BLOCKED |
| T-003 | Learned semantic inference and reproducible model workflow | No model exists. Depends T-002 and model strategy. | Add model adapter, checkpoint provenance, offline training/evaluation commands and label-safe production mode. | AC-001, AC-007, AC-009; held-out official semantic metrics and point-order tests. | BLOCKED |
| T-004 | Obstacle instance detection | Cell nonground envelopes are not objects. Depends T-002/T-003. | Object observations with class/unknown, bounds, source points and uncertainty. | AC-002; thin/near/far/overhang fixtures and held-out recall/false positives. | BLOCKED |
| T-005 | Tracking and motion | Semantic class is not measured motion. Depends T-004 and timestamp/pose contract. | Sequence-owned association, track lifecycle and ego-motion compensated velocity. | AC-004/005; crossing, occlusion, static-wall, moving-object and reset sequences. | BLOCKED |
| T-006 | Visibility and temporal map | Single-frame map cannot prove free space or maintain history. Depends T-002/T-004/T-005. | Bounded timestamped cell state, ray evidence, unknown/stale/occupied/free, safe conflict rules. | AC-003/006; no-return, occlusion, re-observation, ghost and capacity fixtures. | BLOCKED |
| T-007 | Viewer, audit and machine contract | New states require visible provenance and stable output. The evaluator receipt is selected; implementation depends T-003 to T-006 and the T-001 complete payload schema. | Versioned machine-output schema and handoff, separate audit report, Rerun layers, model/track/visibility metrics. The present Rerun recording is a lossy visualization projection. | AC-007/010; schema, consumer handoff and real recording inspection. | BLOCKED |
| T-008 | Full-path performance and release judgment | Budget alone is not a guarantee. Depends T-003 to T-007 and an identified NVIDIA host. | An optional CuPy projection, cell ownership and reduction backend is integrated. Continue profiling and device residency, bound queues and state, and validate the selected CUDA frame path under a frozen contract. This Intel Arc laptop remains the CPU reference. Rerun is measured separately from the 100 ms gate. See the [CUDA goal brief](o-001-cuda-frame-path.md) and [platform decision](decisions/0002-cuda-replay-release-platform.md). | AC-008/012; CPU/CUDA parity and target hardware complete-path benchmark, including zero deadline misses. | IN PROGRESS |
| T-009 | Live source and navigation boundary, if approved | Depends D-003/D-004 and vehicle/sensor contract. | Calibrated timed input, deskew/quality status, planner-facing safety schema only if selected. | AC-011 plus additional safety criteria if in scope. | BLOCKED |

Product implementation moves to IN PROGRESS only after approval and prerequisites; research tasks may
progress independently under their stated scope. A task moves to VALIDATION when outputs exist and
evidence is being collected; to DONE only when its AC evidence is inspected. Update this board and
`LOOP.md` after each meaningful loop. Do not duplicate source code here.

Research modules in `docs/research/modules.md` are paired with the task chain. Current blockers
and next evidence live in `docs/open-items.md`; completed work is recorded in `docs/work-log.md`.

## Immediate next step

Continue T-001. [O-001's release-profile brief](o-001-release-profile.md) records the selected
NVIDIA platform, strict 100 ms evaluator-receipt endpoint and evidence-only output scope.
Workload/window/cap approval is explicitly deferred. Complete payload schema, model milestone,
quality/resource gates and audit/failure behavior remain open before full product implementation.
The [handoff review](work-log.md#2026-09-25---handoff-reconciliation-and-partial-output-contract)
records the fresh CPU test result and inspected schema-2 receipt runs, which each missed 100/100
scan deadlines. These do not share the timing endpoint of the earlier minimal screen below.
The earlier T-008 current-slice diagnostic (E-044) buffered audit outside a paced
loop yet missed 28/1,000 and 3/1,000 deadlines on sequences 08/00 at a
minimal in-process result check. T-001 and the authorized CUDA slice of T-008
are IN PROGRESS; full-path acceptance remains blocked until the complete output
contract and prerequisite stages are ready.
Model screen E-045 also found that Autoware's available FRNet artifacts do not
directly match the SemanticKITTI class contract; T-003 stays BLOCKED until an
allowed exact checkpoint and D-002/D-005 are approved.

User-requested CPU concurrency verification E-046 found that installed Patchwork++ 1.4.1
holds the GIL during `estimateGround`; controlled probe 0021 passed. A Python thread pool
alone does not remove this overlap blocker. Any native binding release or separate-process
experiment still needs safety, exact-output and latency checks. No runtime change was made;
T-008/O-001 remain IN PROGRESS. See the [GIL follow-up](research/experiments/0011-current-path-profile.md#2026-09-25-follow-up-installed-patchwork-gil-behavior).
