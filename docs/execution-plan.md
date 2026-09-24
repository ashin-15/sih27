# Execution plan

Status: planning only. Product implementation is blocked until the draft PRD, technical design and acceptance contract under `Drishti-2.5/docs/spec-driven/drishti-perception/` are frozen and explicitly approved. Status vocabulary: TODO, IN PROGRESS, BLOCKED, VALIDATION, DONE. No product feature below is DONE.

## Objective

Build a standalone, evidence-backed LiDAR perception and adaptive 2.5D map pipeline. The milestone chain is contract -> learned perception -> object evidence -> temporal reasoning -> conservative map -> complete-path validation.

| Task | Milestone and objective | Why and dependencies | Components and implementation notes | Acceptance and validation | Status |
| --- | --- | --- | --- | --- | --- |
| T-000 | Bootstrap persistent agent context | Future sessions need recoverable facts and evidence. No product dependency. | Root `AGENTS.md`, context, assessment, interfaces, testing, research and decision templates. | Required files exist; claims reviewed against source; 42 tests, lint, format, types, build and synthetic demo checked. | DONE |
| T-010 | Standalone project workflow and archive cleanup | New research and blockers need a durable home. No product dependency. | Local `AGENTS.md` rules, work log, open-item register, research modules, process ADR, retired identifier redaction. | Links and archive provenance inspected; JSON/XML parse; identifier search clear in current working-tree content. | DONE |
| T-011 | Research and measurement foundation | Model selection and future gates need task-specific evidence. No product implementation dependency. | Source/claim screen, model candidate register, current-path replay protocol, evidence and impact updates. | Primary sources inspected; claims bounded; protocol records provenance, metric and report checks. Real-data execution is a separate open item. | DONE |
| T-012 | Profile current replay bottleneck | The measured current path cannot sustain the 10 Hz development workload. Research only. | Reproducible CLI run, timing harness, `cProfile`, digest/accounting comparison and bounded hotspot report. | Report distinguishes engine, mapping, digest and audit costs; harness outputs match CLI on overlapping frames. | DONE |
| T-013 | Evaluate cell-grouping alternative | T-012 identified row-wise grouping as the dominant hotspot. No production approval implied. | Isolated benchmark of grouping candidates with negative-coordinate, level, overflow and ordering checks. | Exact ownership/inverse and snapshot digest equivalence plus repeatable latency comparison in experiment 0003. | DONE |
| T-014 | Test durable 10 Hz ingestion and ordered scheduling | T-013 still has 143-151 ms process p50 and the existing audit-inclusive worker is slower than 10 Hz. User-authorized technology research is active; an approved live-source and overload policy is required before production integration. | Short Python/C++ SQLite WAL/FULL and MCAP recorder comparisons, concurrent current-path replay and injected SQLite faults are recorded in experiment 0008. Next prototype a bounded ordered worker and long-run storage behavior outside the active product path. | Real sensor retry/ack, physical disk and power faults, contiguous acknowledged IDs, exact digests, sustained throughput, queue age and capture-to-output tails on target hardware. | IN PROGRESS (research only) |
| T-001 | Freeze product and measurement contract | D-001 development profile is measured; D-001 release branch and D-002 to D-005 remain open. | PRD, technical design, acceptance; specify release hardware, dataset splits, classes, thresholds and navigation boundary. | Signed-off stable FR/AC set with no blocking TBD. Review documents and record approval. | IN PROGRESS |
| T-002 | Freeze interfaces and evaluation harness | All features need consistent point IDs, pose/time, class IDs and shared engine path. Depends T-001. | `contracts.py`, `pipeline.py`, `semantics.py`, `docs/interfaces.md`; design versioned prediction/output contracts and same-path evaluator. | AC-001, AC-009; alignment/unknown/leakage fixtures and wheel replay. | BLOCKED |
| T-003 | Learned semantic inference and reproducible model workflow | No model exists. Depends T-002 and model strategy. | Add model adapter, checkpoint provenance, offline training/evaluation commands and label-safe production mode. | AC-001, AC-007, AC-009; held-out official semantic metrics and point-order tests. | BLOCKED |
| T-004 | Obstacle instance detection | Cell nonground envelopes are not objects. Depends T-002/T-003. | Object observations with class/unknown, bounds, source points and uncertainty. | AC-002; thin/near/far/overhang fixtures and held-out recall/false positives. | BLOCKED |
| T-005 | Tracking and motion | Semantic class is not measured motion. Depends T-004 and timestamp/pose contract. | Sequence-owned association, track lifecycle and ego-motion compensated velocity. | AC-004/005; crossing, occlusion, static-wall, moving-object and reset sequences. | BLOCKED |
| T-006 | Visibility and temporal map | Single-frame map cannot prove free space or maintain history. Depends T-002/T-004/T-005. | Bounded timestamped cell state, ray evidence, unknown/stale/occupied/free, safe conflict rules. | AC-003/006; no-return, occlusion, re-observation, ghost and capacity fixtures. | BLOCKED |
| T-007 | Viewer, audit and machine contract | New states require visible provenance and stable output. Depends T-003 to T-006. | Versioned snapshot/report schema, Rerun layers, model/track/visibility metrics. | AC-007/010; schema checks and real recording inspection. | BLOCKED |
| T-008 | Full-path performance and release judgment | Budget alone is not a guarantee. Depends T-003 to T-007 and target platform. | Instrument complete path; bound queues and state; profile/optimize only measured bottlenecks. | AC-008/012; target hardware benchmark and regression suite. | BLOCKED |
| T-009 | Live source and navigation boundary, if approved | Depends D-003/D-004 and vehicle/sensor contract. | Calibrated timed input, deskew/quality status, planner-facing safety schema only if selected. | AC-011 plus additional safety criteria if in scope. | BLOCKED |

Product implementation moves to IN PROGRESS only after approval and prerequisites; research tasks may
progress independently under their stated scope. A task moves to VALIDATION when outputs exist and
evidence is being collected; to DONE only when its AC evidence is inspected. Update this board and
`LOOP.md` after each meaningful loop. Do not duplicate source code here.

Research modules in `docs/research/modules.md` are paired with the task chain. Current blockers
and next evidence live in `docs/open-items.md`; completed work is recorded in `docs/work-log.md`.

## Immediate next step

Continue T-001. The current-machine workload is recorded; release scope, model milestone,
navigation boundary and numeric quality gates still need decisions before product implementation.
