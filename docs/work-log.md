# Work log

Append dated entries for meaningful work. State what changed, what was verified, and what remains.
Detailed test evidence belongs in `testing.md`; active blockers belong in `open-items.md`.

## 2026-09-24 - Durable-ingress technology comparison

- DONE: Compared Python and C++20 SQLite WAL/FULL recorders, one-scan and ten-scan MCAP
  segments, and primary documentation for Rust/redb, RocksDB, ROS 2 QoS, oneTBB and pybind11.
  Seven paced 100-scan recorder reports are linked in experiment 0008; all stored payloads
  were reverified after reopen. Two recorder runs overlapped complete geometric CLI replays.
- MEASURED RESULT: Python and C++ SQLite acquisition p50 was about 9 ms standalone and under
  concurrent replay; observed maxima were 20.84-23.98 ms. Both concurrent CLI replays still
  missed 100 ms on every frame. One-scan MCAP files acknowledged within 13.52 ms observed
  maximum; ten-scan files delayed acknowledgement up to about 1.02 s.
- DONE: Injected a process kill before SQLite commit and an artificial database page limit.
  Previously committed scans survived and duplicate frame IDs were rejected. Built the C++
  harness with strict warnings, passed a final two-scan native smoke run and checked Python
  harness lint/format. Repeated the fault harness after formatting. The package suite passed
  42 tests. Both concurrent CLI outputs matched all 100 baseline input/map digests, frame IDs,
  cells and accounting. No production path or package dependency changed.
- RECOMMENDATION: SQLite WAL/FULL is the first durable-ingress prototype. Selective C++ is
  reserved for a sensor SDK or measured compute hotspot; MCAP is a recording/export option.
- OPEN: Source retry and capture contract, sustained concurrency, checkpoint/disk budget,
  physical/power faults, ordered worker throughput and complete-path output age. T-014 remains
  research only; the current product contract is still a draft.
- REVIEW: Clarified why a local SQLite file is a viable first capture prototype and why
  it cannot solve sustained backlog or sensor loss before commit. Updated the research review
  and its local visual explanation after feedback.

## 2026-09-24 - Standalone project assessment and bootstrap

- DONE: Inspected the current mapping, CLI, dataset, viewer, and tests. Created project context,
  assessment, interface, test, research, execution, and draft specification records.
- VERIFIED in the earlier assessment: 42 package tests passed; Ruff, mypy, build, and a
  three-frame synthetic CLI demo passed. These checks cover the current slice only.
- OPEN: Learned perception, obstacle detection, temporal fusion, tracking, motion estimation,
  free-space proof, and a complete-path real-time guarantee remain absent. Product contract
  decisions and target hardware are pending.

## 2026-09-24 - Reference structure adapted to Drishti

- DONE: Inspected the supplied code archive for its development plan, research modules/log,
  decision notes, and subsystem guidance. Added a project record entry point, active open-item
  register, research modules, local `AGENTS.md` rules, and a process ADR. Kept old team assignments,
  implementation details, and benchmark numbers out of the standalone plan.
- DONE: Removed the retired project identifier from tracked working-tree content. Historical
  evidence text and XML identifiers were redacted without changing numerical results; the
  original files remain in Git history. Removed an obsolete reference-only verification script.
- OPEN: `Drishti-2.5/deeplearningpipeline.md` is a proposed architecture to evaluate against the
  frozen product contract. Its cited real-data report files are absent in the current working
  tree, so those latency figures are NOT VERIFIED here. Existing run-file changes were preserved.

## 2026-09-24 - Research and measurement foundation

- DONE: Checked the official SemanticKITTI task/API documentation, FRNet authors' repository,
  Autoware FRNet integration documentation and OctoMap's primary description. Recorded bounded
  claims and limitations in the research evidence, claim, impact and session logs.
- DONE: Added a candidate screen and a current-path replay baseline protocol with provenance,
  split, metric and output checks. Inspected the local development machine and HF cache without
  downloading a model or touching source data.
- OPEN: User decisions on release scope and target hardware, D-001 to D-005, checkpoint terms,
  real-data baseline and all future feature acceptance. No runtime feature was implemented.

## 2026-09-24 - Current hardware and real-data workload baseline

- DONE: Re-ran 42 tests, Ruff lint/format and mypy. Ran new 100-frame geometric replays for
  SemanticKITTI sequences 00 and 08 and saved their reports in unique `Drishti-2.5/runs/`
  directories. Both completed with point accounting intact and 100/100 misses each against the
  configured 100 ms budget.
- DONE: Ran the validator in `--structure-only` mode over all 22 sequences. Its report passed
  metadata/file-size checks for 43,552 scans and found a maximum of 129,392 points per scan.
  Full scan-content validation remains NOT VERIFIED.
- DECISION for development: current laptop, 10 Hz, 130,000-point replay workload and an unmet
  100 ms complete-path engineering goal. Added hardware options and updated the draft PRD,
  experiment record, evidence, open items and loop. No production feature or release gate was
  approved by these measurements.

## 2026-09-24 - Replay hotspot profile

- DONE: A focused agent profiled a fresh 50-frame sequence 08 replay and a reproducible
  40-frame timing harness without modifying production source. Harness digests and accounting
  matched CLI outputs for overlapping frames. The report is `docs/research/experiments/0002-replay-profile.md`.
- MEASURED RESULT: row-wise `np.unique` sorting dominates sampled `aggregate_cells` time;
  snapshot hashing is material but outside `mapping_ms`. The CLI still missed 100 ms on 50/50
  frames. `cProfile` timings have instrumentation overhead and are not release measurements.
- OPEN: T-013/O-010 will test an alternative grouping method for exact outputs and latency;
  implementation remains behind the draft product contract.

## 2026-09-24 - Exact grouping and lossless arrival design

- DONE: Added experiment 0003 as an isolated real-data benchmark of row-wise, packed-int64 and
  lexicographic cell grouping. On 30 frames each from sequences 00 and 08, all grouping results,
  point-to-cell indices and snapshot digests matched. Packed geometric `process` p50 was
  143.19/150.54 ms versus baseline 266.00/276.19 ms; the 100 ms target remains unmet.
- DONE: Documented the 10 Hz capacity calculation and a concrete SQLite WAL plus bounded
  shared-memory scheduling proposal. This records acquired scans before processing and exposes
  queue age/overload; a finite queue cannot sustain indefinite service below arrival.
- VERIFIED: benchmark script Ruff lint/format passed. Two complete 30-frame harness reports
  were inspected. Production source, live sensor, durable recorder and parallel scheduler were
  not changed or tested.
- OPEN: T-014/O-011 require contract decisions, recorder crash/disk-full tests, sustained paced
  acquisition, parallel contention and all future model/temporal stages before a no-loss or
  100 ms product claim.

## 2026-09-24 - Paced WAL ingress feasibility

- DONE: Added an isolated SQLite WAL/FULL recorder harness and read-only 100-scan sequence 08
  test at scheduled 100 ms intervals. Fresh-connection validation matched every stored frame
  ID, point length and hash to its source payload. The ext4/NVMe database is in a new run
  directory; its report is `docs/research/experiments/0004-seq08-100-ext4.json`.
- MEASURED RESULT: ext4 read-through-commit p50/p95/p99/max was 9.26/20.48/22.05/23.98 ms.
  An initial `/tmp` run used tmpfs and is preserved as a separate RAM-backed result.
- VERIFIED: Ruff lint/format passed for the recorder harness. No production source changed.
- OPEN: This is a short recorder-only run. Crash/power-loss, full disk, concurrent compute,
  real sensor retry, long-run tail and 100 ms capture-to-published behavior remain unverified.
