# Research log

## 2026-09-24 - SQLite, C++, MCAP and scheduler comparison

- Research question: RQ-005. Sources: E-017 to E-019; experiment 0008 and its measured
  C++/Python SQLite, MCAP and injected-fault reports; official SQLite, MCAP, oneTBB,
  pybind11, Rust/redb, Tokio, RocksDB and ROS 2 documentation linked in the review.
- MEASURED RESULT: all seven short recorder runs independently reverified 100/100 scan
  payloads. Python and C++ SQLite acquisition medians were about 9 ms; their concurrent
  maxima were 22.71 and 23.31 ms. Both concurrent 100-frame CLI replays still missed their
  configured 100 ms budget on every frame. MCAP one-scan files acknowledged within 13.52 ms
  observed maximum; ten-scan segments delayed acknowledgement by up to 1.02 s.
- MEASURED RESULT: after a killed writer left scan 1 uncommitted, SQLite reopened with only
  scan 0; restart completed scan 1 and rejected a duplicate. An artificial page cap raised a
  capacity error while preserving the earlier committed row.
- Contradiction: C++ recorder rewrite did not show a material latency benefit under these
  local conditions, and adding durable ingress did not make current perception meet 10 Hz.
  The MCAP buffered-segment append did not provide an immediate per-scan durable ack.
- Confidence and limits: high for exact saved-run outcomes; low for long-run, real-sensor,
  power-loss or language-wide conclusions. Storage cache, thermal state and independent
  timing were not controlled; Python recorder schedule lag was not recorded.
- DESIGN PROPOSAL and impact: start T-014 with a local SQLite WAL/FULL writer and explicit
  source ack/retry boundary, then a bounded ordered worker. Use C++ for a measured compute
  stage or required SDK and preserve exact output digests. MCAP remains an archive candidate.
  No runtime architecture is accepted while the product contract remains draft.
- Open questions: physical disk and power faults, checkpoint tails, retention, stalled
  readers, sensor loss before commit, worker service headroom and capture-to-output age.

## 2026-09-24 - Paced SQLite recorder prototype

- Research question: RQ-004. Source: E-016, experiment 0004 and SQLite WAL documentation.
- MEASURED RESULT: a real SQLite WAL/FULL transaction per scan stored and reverified all 100
  sequence 08 payloads at a scheduled 100 ms interval. On the project ext4/NVMe filesystem,
  read-through-commit p50/p95/p99/max was 9.26/20.48/22.05/23.98 ms. Database size after
  close was 196,493,312 bytes. An initial `/tmp` run was on tmpfs and is recorded separately,
  not used as persistent-storage timing evidence.
- Validation: a fresh connection checked contiguous IDs, lengths, stored hashes and source
  hashes after writer close. The script passed Ruff lint/format. This only tests recording.
- Engineering impact: SQLite is a feasible technology candidate for 10 Hz raw-scan ingress
  on this machine in a short isolated test. T-014 still needs crash, slow/full-disk, hours-long,
  live-source and concurrent compute tests. No production recorder was integrated.
- Open questions: sensor acknowledgement/retry, exact live payload, disk reserve and wear,
  checkpoint tails, power-loss behavior and output freshness policy.

## 2026-09-24 - Exact grouping and lossless arrival feasibility

- Research question: RQ-004. Sources: E-014/E-015, experiment 0003, existing CLI profile,
  SQLite WAL and Python multiprocessing primary documentation.
- MEASURED RESULT: on 30 frames each of sequences 00/08, packed grouping p50 was 9.34/10.11 ms
  versus row-wise 132.54/133.77 ms. All 60 grouping, cell-index and snapshot comparisons
  matched. The candidate geometric `process` p50 was still 143.19/150.54 ms, excluding load,
  audit and future stages. This is an isolated harness result, not an integrated CLI benchmark.
- FACT: current audit-inclusive 3.14 frames/s is below 10 frames/s arrival. A finite queue
  cannot prevent unbounded growth during indefinite overload. A 130,000-point float32 x4
  payload is 2.08 MB, before metadata. The current-path deficit implies roughly 14.3 MB/s
  raw-payload backlog growth if acquisition is retained.
- DESIGN PROPOSAL: local SQLite WAL with FULL commit as acknowledged raw-scan ingress,
  bounded shared-memory slots for later stateless workers, ordered sequence-owned ground and
  temporal state, and explicit output age/overload status. Durability, storage write rate and
  concurrent throughput are NOT VERIFIED on this hardware.
- Engineering impact: T-013 research completed; T-014 and O-011 track recorder/scheduler
  feasibility and failure behavior. Product integration still awaits the frozen contract.
- Open questions: live sensor retry, disk capacity/endurance, stale map policy, worker
  contention, thermal tails, model overhead and release hardware.

## 2026-09-24 - Mapping and audit hotspot profile

- Research question: RQ-004. Source: E-013, experiment 0002 and its fresh 50-frame replay.
- MEASURED RESULT: `aggregate_cells` p50 was 180.75 ms in the 40-frame harness. A separate
  12-frame `cProfile` pass attributed 1.601 s of 2.164 s aggregate time to row-wise
  `np.unique`, largely its sort. Snapshot digest p50 was 16.74 ms and input hash p50 was
  2.14 ms; JSON write/flush p50 was 0.12 ms. The digest is outside `mapping_ms`.
- Validation: harness input/map digests and accounting matched the CLI for the overlapping
  40 frames. Profiler overhead limits exact latency comparisons; the unprofiled CLI and harness
  supply the reported latency values.
- Engineering impact: T-013 will benchmark alternative grouping and prove exact ownership,
  ordering and digest preservation. No production algorithm or release claim was accepted.
- Open questions: candidate key overflow/collision behavior, performance across other sequences,
  thermal effects and full-path cost after model/temporal stages exist.

## 2026-09-24 - Current-machine workload and latency baseline

- Research question: RQ-004. Sources: E-011/E-012, the saved run reports, structure-only dataset
  report, current CLI/config source, and official FRNet/Autoware hardware documentation.
- MEASURED RESULT: two 100-frame real-data geometric replays passed accounting but missed 100 ms
  on all 200 frames. Audit-inclusive p50 was 310.3/326.9 ms; `mapping_ms` was the largest
  measured processing stage. Dataset metadata covers 43,552 scans with a 129,392-point maximum
  and about 104 ms median sequence cadence.
- DESIGN DECISION for development: current machine, 10 Hz, 130,000-point workload, 100 ms
  capture-to-published-output engineering goal. The current timing is an incomplete proxy and
  fails the goal. No release or vehicle deadline is accepted.
- Contradictions and limits: the earlier synthetic no-miss result does not generalize to real
  scans. Dataset validation was structure-only. Viewer, model, temporal state, live acquisition,
  queueing, thermal behavior and prolonged overload remain unmeasured.
- Engineering impact: profile mapping and audit work before choosing optimization or extra
  hardware; keep hardware procurement conditional on checkpoint and full-path evidence.
- Open questions: release platform and fault policy, model backend compatibility, quality gates,
  long-run tail latency and full-data content validation.

## 2026-09-24 - Foundation screen for model and evaluation boundaries

- Research questions: RQ-001, RQ-003, RQ-004.
- Sources: E-006 to E-010 in `evidence.md`; current `pipeline.py`, `contracts.py`,
  `deeplearningpipeline.md`, and the draft PRD/design/acceptance documents.
- Findings: LITERATURE-BACKED CLAIM, official SemanticKITTI tasks score point semantics,
  panoptic instances, 4D association and moving points separately. FRNet supplies a semantic
  candidate, not detection/tracking/free-space proof. Autoware's integration separates stage
  timings from pipeline latency. OctoMap distinguishes occupied, free and unknown observations.
- Local status: FACT, no LiDAR checkpoint was listed in the development machine's HF cache;
  the current machine has an Intel CPU, integrated graphics and NPU. No candidate was downloaded,
  executed or measured. Target hardware remains a product decision.
- Contradictions and limits: No direct contradiction in the narrow source claims. FRNet checkpoint
  terms, preprocessing compatibility, all-point mapping, and target-machine latency are UNKNOWN.
  OctoMap's 3D policy cannot be transferred unchanged to a 2.5D map.
- What changed: Added `model-candidates.md`, experiment 0001 protocol, evidence and claim entries,
  and task-specific evaluation boundaries. No model or runtime path changed.
- Engineering impact: T-002 must preserve original point IDs and separate evaluator outputs;
  T-003 screens a checkpoint before integration; T-006 requires a validated ray policy; T-008
  measures the complete path rather than network FPS.
- Open questions: D-001 to D-005, checkpoint terms and hardware support, source data access,
  instance/track ground truth for the proposed output, and a false-free annotation protocol.

## 2026-09-24 - Current contract and benchmark scope

- Research questions: RQ-001, RQ-002.
- Sources: `Drishti-2.5/src/drishti/{pipeline,semantics,dataset}.py`; [official SemanticKITTI tasks](https://semantic-kitti.org/tasks.html); [official SemanticKITTI API](https://github.com/PRBonn/semantic-kitti-api).
- Findings: FACT, current geometric mode has unknown semantic/motion outputs and oracle mode reads labels. LITERATURE-BACKED CLAIM, the official semantic task scores point labels with mIoU; its moving-object task scores static/moving point labels. The official API documents scan and label file organization.
- Supporting evidence: `docs/research/evidence.md` E-001 to E-003.
- Contradictory evidence: None found for these narrow claims. No model comparison was performed.
- Confidence/uncertainty: High for current code and official task definitions; UNKNOWN for best architecture and achievable Drishti accuracy.
- What changed: Added RQ-001/RQ-002 and linked them to T-003/T-005.
- What did not change: No model, source code or product decision.
- Implementation impact: Freeze point prediction and evaluation contracts before selecting a backend.
- Open questions: Target hardware, model milestone and accuracy thresholds.

Future sessions append entries with date, question, sources, findings, support/contradictions, confidence, changes, implementation impact and open questions. Do not overwrite failed findings.
