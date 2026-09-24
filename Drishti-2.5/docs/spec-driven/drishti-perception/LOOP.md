# Drishti-2.5 perception delivery loop

Current state: grilling
Current loop: LOOP-001
Frozen specification: none
Current objective: Resolve product decisions and freeze the contract; research and current-path measurement preparation are under way.
Blocking issue: D-001 release branch, D-002 to D-005 and explicit approval are needed before production implementation.
Next action: Record user answers, freeze PRD, technical design and acceptance, then request implementation approval.
Last updated: 2026-09-24

## Current loop - LOOP-001

- Related FRs/ACs: all draft IDs.
- Assignments: main agent only.
- Outputs: current-state audit, draft specification, standalone README and tooling cleanup; root agent operating manual and research/execution scaffold.
- Baseline checks: 42 tests passed; three-frame synthetic headless demo completed with release gate false; Ruff lint/format, mypy and source/wheel build passed. Dataset and full-path performance were not verified.
- Main-agent judgment: the current package is a valid single-frame mapping prototype. Requested perception and real-time capabilities are absent from the active path.
- Risks: model architecture, target hardware, deployment scope, safety use and numeric gates are not decided. Real dataset access was not used in this audit.
- Next state: awaiting-spec-approval after open decisions and frozen acceptance are resolved.

## Research preparation - 2026-09-24

- Related FRs/ACs: FR-001/006/008/009 and AC-001/006/008/009, all still draft.
- Outputs: primary-source evidence E-006 to E-010, model candidate screen and experiment 0001
  replay protocol in `docs/research/`. No production source or acceptance threshold changed.
- Checks: source links and local hardware/cache inspection; real-data replay, checkpoint evaluation
  and complete-path benchmarks NOT VERIFIED.
- Judgment: continue requirements grilling. The research narrows evaluation boundaries but does
  not settle D-001 to D-005 or authorize implementation.

## Local hardware baseline - 2026-09-24

- Related FRs/ACs: FR-008 and AC-008/012, all still draft.
- MEASURED RESULT: 42 tests, Ruff lint/format and mypy passed. Headless geometric replay
  completed 100 frames each on SemanticKITTI sequences 00 and 08, with 100/100 misses per run
  against the configured 100 ms budget. Audit-inclusive p50 was 310.3 and 326.9 ms. A
  structure-only dataset check passed for all 22 sequences; content validation was not run.
- DESIGN DECISION for development only: current Core Ultra 9 185H machine, 10 Hz, up to 130,000
  points per scan, and 100 ms capture-to-published-output engineering goal. The goal is not met.
- Evidence: `docs/research/experiments/0001-replay-baseline-protocol.md` and the new run reports.
- Judgment: D-001 development profile is recorded. Release hardware, deadline policy, all full
  pipeline stages and explicit implementation approval remain open.

## Replay profile - 2026-09-24

- Related FRs/ACs: FR-008 and AC-008/012, all still draft.
- MEASURED RESULT: a fresh 50-frame replay missed the configured 100 ms budget on all frames.
  An independent timed harness matched the CLI's input/map digests and accounting on 40 frames.
  Separate `cProfile` identified row-wise `np.unique` sorting as the dominant sampled cost inside
  `aggregate_cells`; digest work is outside `mapping_ms`.
- Evidence: `docs/research/experiments/0002-replay-profile.md` and saved run reports.
- Judgment: research finding only. T-013 is an isolated equivalence and latency experiment;
  no production optimization or implementation approval follows automatically.

## Exact grouping and ingress proposal - 2026-09-24

- Related FRs/ACs: FR-008 and AC-008/012, all still draft.
- MEASURED RESULT: experiment 0003 matched grouping, point-to-cell indices and snapshot
  digests on 60 real frames. Packed grouping lowered sampled `process` p50 to 143.19/150.54 ms
  on sequences 00/08. No scan acquisition or complete-path 100 ms guarantee was measured.
- DESIGN PROPOSAL: local SQLite WAL commits for recoverable raw scans, bounded shared-memory
  stateless workers, one ordered owner for stateful stages, and explicit age/overload outputs.
  No runtime database, queue or parallel scheduler was implemented.
- Evidence: `docs/research/experiments/0003-lossless-10hz-design.md` and two JSON reports.
- Judgment: T-013 research is complete. T-014 and product integration await live-source,
  freshness, disk/fault and frozen contract decisions.

## Paced recorder feasibility - 2026-09-24

- Related FRs/ACs: FR-008 and AC-008/012, all still draft.
- MEASURED RESULT: an isolated SQLite WAL/FULL prototype stored and reverified 100 raw scans
  at scheduled 100 ms intervals on the project ext4/NVMe filesystem. Read-through-commit
  p50/p95/p99/max was 9.26/20.48/22.05/23.98 ms. An earlier tmpfs result is labeled
  separately and is not persistent-storage evidence.
- Evidence: `docs/research/experiments/0004-sqlite-ingress.md` and two JSON reports.
- Judgment: this validates a short recording technology candidate, not the active runtime,
  crash durability, concurrent 10 Hz processing or a complete-path 100 ms guarantee.

## Ingress technology comparison - 2026-09-24

- Related FRs/ACs: FR-008 and AC-008/012, all still draft.
- MEASURED RESULT: experiment 0008 reverified 100 paced scans for each of four Python/C++
  SQLite runs and three MCAP runs. Two SQLite recorders ran concurrently with separate
  100-frame CLI replays; both CLI runs missed their configured 100 ms budget on every frame.
  The C++ recorder was not materially faster than Python in these short runs. An injected
  SQLite process kill and artificial page limit preserved previously committed scans.
- DESIGN PROPOSAL: use SQLite WAL/FULL as the first durable-ingress prototype, retaining C++
  for a sensor SDK or measured compute hotspot. MCAP remains an archival/interchange candidate.
- Evidence: `docs/research/experiments/0008-ingress-technology-review.md`, saved reports and
  `docs/research/experiments/0007-sqlite-faults-seq08.json`.
- Judgment: T-014 research is in progress. Live source retry, actual disk/power fault behavior,
  sustained backlog, ordered worker throughput and capture-to-output age remain unknown.
  No product implementation or release guarantee is approved.
