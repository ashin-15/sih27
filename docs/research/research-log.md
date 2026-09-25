# Research log

## 2026-09-25 - Strict 100 ms replay deadline and current-path check

- Research question: RQ-004. The product owner selected a 100 ms deadline for every replay
  scan on the current laptop, with zero allowed misses in the accepted window. See O-001,
  PRD D-001 and experiment 0010. This is a product requirement, not a measured capability.
- MEASURED RESULT: `drishti replay --check-100ms` completed 100 real sequence 08 scans on
  a 10 Hz virtual arrival schedule and returned code 2. All 100 scan-report ages exceeded
  100 ms; p50 was 11,371.8 ms and maximum 22,129.9 ms. Exact per-frame digests, IDs, cells
  and accounting matched the prior headless baseline.
- Engineering impact: keep O-001 and AC-008 open. The CLI now measures the current geometric
  failure, but model, fusion, viewer and complete-output publication are absent. Freeze the
  sustained window and resource limits before treating a full-path run as release evidence.

## 2026-09-25 - Packed grouping integrated and checked under the paced gate

- Research question: RQ-004; prior candidate evidence E-014 and new current-path evidence
  E-026. `_group_cells` integrates collision-free int64 packing with a row-wise overflow
  fallback in `aggregate_cells`. Edge tests cover empty, negative, wide and int64-extreme
  keys. A fresh 100-frame CLI run matched all previous frame IDs, input/map digests, cell
  counts and accounting.
- MEASURED RESULT: audit-inclusive duration p50 fell from 319.7 to 193.4 ms in two
  sequential paced sequence 08 runs. All 100 optimized scan ages still exceeded 100 ms;
  p50 age was 4,952.4 ms and maximum 9,520.3 ms as lag accumulated.
- Engineering impact: O-010 moves to VALIDATION for longer/cross-configuration evidence;
  O-001 remains IN PROGRESS. Load, preprocessing, projection and mapping are still material
  timing costs. Future model/temporal/viewer cost is unknown.

## 2026-09-25 - Nearest-return projection under the paced gate

- Research question: RQ-004. A 30-frame local candidate check compared full range-image
  arrays and collision counts before integration. The active projection now uses per-pixel
  minimum range and equal-range minimum original ID instead of sorting all eligible points.
- MEASURED RESULT: the saved 100-frame packed-plus-projection replay matched every prior
  frame ID, input/map digest, cell count and accounting record. Projection p50 was 15.7 ms
  versus 32.7 ms in the packed-only run; audit-inclusive work p50 was 177.2 versus 193.4
  ms. It still missed all 100 deadlines, with 4,172.0 ms p50 report age.
- Engineering impact: preserve nearest-return and tie semantics, profile remaining load,
  preprocessing and mapping costs. No complete-path or real-time release claim follows.

## 2026-09-25 - Current-path profile after two optimizations

- Research question: RQ-004. Experiment 0011 saved a 40-frame sequence 08 timing report
  and separate 12-frame `cProfile` text after packed grouping and minimum-at projection.
- MEASURED RESULT: `process` p50 was 133.14 ms; mapping 57.52, preprocessing 33.93,
  ground 25.65 and projection 15.60 ms p50. Frame load was 26.53 ms and snapshot digest
  16.89 ms p50 outside `process`. `cProfile` ranks repeated reductions as a remaining
  hotspot, but its instrumented totals are not deadline results.
- Engineering impact: examine reduction and ownership costs before another exact-output
  candidate. No evidence yet supports a 100 ms complete-path pass.

## 2026-09-25 - Ordered point-ID validation and rejected digest candidate

- Research question: RQ-004. A focused load profile found NumPy `unique` on already
  increasing SemanticKITTI point IDs consumed about 22 ms per scan. `ScanFrame` now uses
  an ordered-ID fast path and retains full uniqueness validation for unordered IDs.
- MEASURED RESULT: two saved 100-frame paced runs on sequences 08 and 00 matched their
  earlier exact digests, IDs, cells and accounting. Load p50 on sequence 08 fell from
  26.5 to 1.7 ms. Audited work p50 was 149.0/138.9 ms on sequences 08/00; both runs
  still missed 100/100 scan deadlines.
- Failed candidate: using memoryview for snapshot digest preserved outputs but did not
  improve full-replay p50 in a separate 100-frame sequence 08 run (149.8 ms). The code
  change was reverted; the run remains preserved as E-030.
- Engineering impact: O-001 remains open. Mapping and preprocessing dominate the next
  CPU optimization loop; the full model/temporal/viewer costs remain unknown.

## 2026-09-25 - Replay release target narrows RQ-004

- Research question: RQ-004. Input: product owner selected first-release dataset replay on
  the current laptop; see `docs/o-001-release-profile.md`. This is a product decision, not
  a new performance measurement or literature claim.
- Engineering impact: T-008's first release gate must measure the complete paced replay path
  on that laptop with a declared simulated capture timestamp. Live sensor acquisition and
  vehicle hardware are deferred. D-001 numeric deadline/miss policy and D-005 remain open.
- MEASURED RESULT unchanged: the current geometric replay missed the 100 ms development
  budget on all 200 frames in experiment 0001; no complete-path release result exists.

## 2026-09-25 - SQLite alternative: LMDB and custom append log

- Research question: RQ-005. Sources E-020 to E-023 and experiment 0009; official LMDB C
  header, SQLite WAL and Linux `fsync` documentation were checked on 2026-09-25.
- MEASURED RESULT: nine paced 100-scan local ext4 runs reverified every original payload.
  LMDB's observed commit p95 was 4.863-6.916 ms versus SQLite's 15.474-16.990 ms.
  The custom log's p95 ranged 3.538-17.855 ms. Its speed rank changed with run order.
  Matched 1,000-scan LMDB/SQLite runs completed and reverified all 1,000 IDs and payloads
  each. LMDB commit p95 was 16.271 ms versus SQLite's 18.230 ms; LMDB acquisition p95
  was slower (30.029 versus 22.080 ms) because its source-file reads took longer.
- MEASURED RESULT: LMDB reopened after an injected writer kill with only the committed
  scan, rejected a duplicate, resumed contiguously, and returned MDB_MAP_FULL at an
  artificial 8 MiB limit without losing four earlier commits.
- Contradiction: the previous provisional preference for SQLite has weaker latency evidence
  on this local workload. The custom log's favorable rounds do not compensate for its
  missing recovery, rotation and work-state implementation.
- Confidence and limits: exact results are verified; storage state and external load were
  not controlled. No physical disk/full-power fault, live sensor, continuous reader or
  complete-path freshness result exists. A 500-scan concurrent reader/current-worker run
  passed; the current worker still missed 100/100 configured processing deadlines.
- One separate-sandbox concurrent run failed its writer's final reopen with `EAGAIN`.
  Reproduction showed each separately launched command had PID 2, and LMDB source uses PID
  lock-file offsets. INFERENCE: namespace PID collision caused the failure. A held-reader
  test under one namespace (PIDs 2, 3 and 4) passed the same reopen boundary. Keep this
  as a test-harness constraint and recheck process restart on deployment hardware.
- DESIGN PROPOSAL: use LMDB for the next isolated single-writer/read-replay prototype, keep
  SQLite WAL/FULL as fallback, and select neither for production until source ack/retry,
  retention, map growth, sustained contention and fault gates pass.


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
- Review clarification: the SQLite option is a local numbered inbox with an explicit
  commit-before-ack boundary. Its measured short-run capture feasibility does not establish
  live-source no-loss behavior or sustained 10 Hz perception. The plain-language explanation
  was added to experiment 0008 after the review question.

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

## 2026-09-25 - Current-laptop paced replay check

- Research question: RQ-004. Source: E-031, two saved 100-frame SemanticKITTI run directories
  and experiment 0010. The current working-tree source digest is recorded in each manifest.
- MEASURED RESULT: all 200 frame outputs matched the original headless baselines, but all
  200 scheduled-arrival-to-report-flush ages exceeded 100 ms. Audited work p50 was 137.0 ms
  on sequence 08 and 125.1 ms on sequence 00; backlog raised age beyond 2 seconds p50.
- Confidence and limits: high for these two local runs and report comparisons. Scheduling is
  virtual, the viewer is off, and learned, temporal and durable publication stages are absent.
  Sequential timings are sensitive to local machine state.
- Engineering impact: keep O-001 open and the complete-path AC-008 gate NOT VERIFIED. Mapping
  remains the largest reported stage median on sequence 08. A one-frame random-label
  histogram microbenchmark was promising but does not establish a full-run optimization.
- Open questions: approved release workload/window, viewer publication boundary, resource
  ceilings, and complete-path implementation and validation.

## 2026-09-25 - Exact distance and semantic-histogram follow-up

- Research question: RQ-004. Source: E-032 and experiment 0010 with saved geometric and
  oracle replays on the current laptop.
- MEASURED RESULT: 200 geometric frame outputs and 50 oracle frame outputs matched prior
  baselines after the changes. Audited work p50 fell to 122.3/108.3 ms on sequences 08/00,
  while every scheduled 100 ms geometric deadline still missed.
- Negative candidate: sorting cell indices for `reduceat` bounds/sums preserved one sampled
  result but took 19.78 versus 4.97 ms for existing reductions. It was not integrated.
- Confidence and limits: exact for sampled records; sequential performance runs did not
  control thermal/cache state. No learned, temporal or viewer path was measured.
- Engineering impact: keep O-001 open. Mapping remains the largest reported stage. The
  complete-path gate requires further implementation and a frozen release profile.

## 2026-09-25 - Native ground dtype check

- Research question: RQ-004. Sources: E-033, installed Patchwork++ binding signature and
  saved geometric/oracle runs in experiment 0010.
- MEASURED RESULT: float32 Nx4 input preserved 200 geometric and 50 oracle sampled frame
  outputs. Audited work p50 was 120.3/108.4 ms on sequences 08/00, with 200/200 misses.
  Dropping the intensity column changed first-frame ground indices and was rejected.
- Confidence and limits: exact sampled outputs, sequential laptop timing subject to machine
  state; no model, temporal state, viewer or accepted sustained release gate.
- Engineering impact: keep the declared native input dtype in `PatchworkGround`, keep O-001
  open, and avoid treating a modest ground-stage saving as deadline certification.

## 2026-09-25 - Rerun recording cost and boundary

- Research question: RQ-004. Sources: E-034, experiment 0012 and same-source headless and
  record-mode sequence 08 run reports.
- MEASURED RESULT: record mode matched all 100 headless frame outputs but missed all 100
  deadlines. Its SDK submission median was 9.93 ms, audited work p50 132.2 ms, and its
  verified `.rrd` used 270.6 MB for 100 scans.
- Confidence and limits: high for those saved artifacts. Runs were sequential; the record
  path flushed once after the loop and did not measure actual viewer display or per-frame
  durable recording.
- Engineering impact: D-001/D-005 must state whether Rerun participates and which exact
  event counts as complete output. The current recorded path fails even its submission
  boundary. O-001 and AC-008 remain open.

## 2026-09-25 - High-density first-scan boundary

- Research question: RQ-004. Sources: E-035, structure-only report E-012 and the saved
  sequence 10 frame 206 one-scan replay.
- MEASURED RESULT: 129,392 input points were accepted, but the cold-start
  scheduled-arrival-to-report-flush age was 129.13 ms and its deadline missed.
- Confidence and limits: high for this one completed run; it is not a whole-sequence
  steady-state result, and map digest equality to a previous same-frame run was not tested.
- Engineering impact: retain a near-130,000-point boundary case in the candidate release
  workload. O-001 remains open even at the measured first-scan boundary.

## 2026-09-25 - Projection overlap screen

- Research question: RQ-004. Source: experiment 0011 follow-up and current
  `ground.py`/`projection.py` source.
- MEASURED RESULT: single-frame ground-plus-projection trial medians were about 37.9 ms
  sequential, 36.8 ms with a warmed thread worker, and 36.2 ms with a warmed spawned
  process worker. The process serialized point, ID and range-image arrays.
- Confidence and limits: exploratory six/eight-trial samples, no full-array equivalence
  or paced replay, no controlled machine state. No product speed claim follows.
- Engineering impact: do not add a worker pool merely for the sampled projection overlap;
  retain the existing exact path while the release contract and complete stages advance.

## 2026-09-25 - Recorded-view per-frame SDK flush boundary

- Research question: RQ-004. Sources: E-036, experiment 0012, installed Rerun SDK flush
  documentation, current CLI and saved 100-frame recording.
- MEASURED RESULT: every frame was flushed through the Rerun SDK before its JSONL report.
  The 100-frame run matched prior map outputs but missed 100/100 deadlines; audited work
  p50 was 142.0 ms and SDK flush p50 was 10.01 ms. The RRD verified and had 100
  cell/raw/semantic chunks each.
- Confidence and limits: direct local timers and parsed artifact support this diagnostic
  event. SDK flush does not imply disk `fsync` or rendered display, and the full model and
  temporal pipeline remain absent.
- Engineering impact: the viewer boundary can now be measured if selected; D-001/D-005
  still must define complete publication. O-001 remains open.

## 2026-09-25 - Separate scheduled replay producer and bounded queue

- Research questions: RQ-004/RQ-005. Sources: E-037, experiment 0013, saved sequence 08
  100-frame run and matching headless baseline.
- MEASURED RESULT: a separate 10 Hz dataset producer preserved every sampled frame
  output, but its two-slot queue filled 93 times. All 100 output ages exceeded 100 ms;
  output age p50 was 1312.4 ms and producer load-start lag p50 was 844.3 ms.
- Confidence and limits: direct saved frame/timing records support this finite local
  run. The producer blocks on a volatile Python queue and is not a live source or
  durable recorder. Machine load and scheduling were not controlled.
- Engineering impact: the current worker cannot satisfy an independent 10 Hz replay
  producer by buffering two scans. Keep O-001 and O-011 open; specify overload and
  publication behavior before a complete-path release test.

## 2026-09-25 - All-unknown cell evidence optimization

- Research question: RQ-004. Sources: E-038, experiment 0014, current `mapping.py`
  and exact frame comparisons with saved geometric/oracle baselines.
- MEASURED RESULT: direct dense evidence construction for all-unknown input reduced
  sequence 08/00 mapping p50 from 47.60/41.29 to 37.16/33.45 ms and preserved
  all 200 geometric plus 50 oracle sampled frame outputs. Audited work p50 was
  110.71/100.04 ms; both paced runs still missed 100/100 deadlines.
- Confidence and limits: saved frame digests and accounting support exact sampled
  outputs. Sequential local runs were not controlled for machine state, and the
  complete product stages are absent. A separate-producer rerun still missed all
  100 deadlines and filled the two-slot queue 89 times.
- Engineering impact: keep the exact all-unknown path, continue profiling true
  bottlenecks, and retain a failing 100 ms release status under O-001.

## 2026-09-25 - Recorded-view cost after all-unknown optimization

- Research question: RQ-004. Sources: E-039, experiment 0015, same-source
  headless/recorded 100-frame runs and verified Rerun recording.
- MEASURED RESULT: recorded sequence 08 output matched the headless baseline but
  missed all 100 deadlines. Audited work p50 was 131.34 ms; Rerun submission
  plus per-frame SDK flush p50 was 20.40 ms, including 10.16 ms flush.
- Confidence and limits: saved timings, exact frame records and RRD verifier/stats
  support this diagnostic boundary. SDK flush is not disk `fsync` or a rendered
  frame; local runs did not control machine state and omit future product stages.
- Engineering impact: viewer participation and complete-output event remain
  D-001/D-005 choices; O-001 still has no 100 ms release pass.

## 2026-09-25 - Reuse immutable arrays for fully accepted scans

- Research question: RQ-004. Sources: E-040, experiment 0016, current
  `pipeline.py` and exact frame comparisons with saved replay baselines.
- MEASURED RESULT: all 250 geometric/oracle sampled frame outputs matched after
  removing duplicate copies of already immutable full-frame points and IDs.
  Sequence 08/00 preprocessing p50 fell from 14.84/14.49 to 12.19/11.95 ms;
  audited work p50 was 108.35/98.93 ms. The strict gate still missed 100/100
  and 82/100 frames.
- Confidence and limits: saved outputs and timing sidecars support the sampled
  comparisons. Machine state was not controlled, and no full sequence or complete
  product path was measured. Filtered-point behavior remained in tests.
- Engineering impact: keep the immutable reuse path, but maintain failing O-001
  status until every scan meets the selected 100 ms complete-output gate.

## 2026-09-25 - Audit of the actual O-001 output boundary

- Research question: RQ-004. Sources: E-041, current `cli.py`/`mapping.py`/
  `pipeline.py`/`visualization.py`, saved headless and Rerun run artifacts.
- FACT: the in-process `FrameResult` contains current-slice map arrays, but the
  JSONL report saves only digests and metrics. Rerun saves a visualization
  projection without every `MapSnapshot` field. No external machine-map
  consumer or acknowledgement event is implemented.
- Confidence and limits: direct source and artifact inspection establish the
  present boundary. The final versioned output contract is still draft, so
  its exact payload and consumer are UNKNOWN.
- Engineering impact: keep the existing timed JSONL flush as a diagnostic,
  not AC-008 proof. Freeze the complete payload and handoff event before
  implementing the release clock. See `docs/o-001-output-boundary-audit.md`.

## 2026-09-25 - Current snapshot serialization screen

- Research question: RQ-004. Sources: E-042, experiment 0017, current
  `MapSnapshot` fields and ten real sequence 08 replay frames.
- MEASURED RESULT: stored and deflated ZIP/NPY archives round-tripped every
  current snapshot field exactly. Median stored size/encode time was 15.64 MB/
  13.59 ms; deflate level 6 was 0.765 MB/261.96 ms. File `fsync` p50 was
  10.02/10.74 ms, respectively.
- Confidence and limits: saved per-frame records and two independently checked
  frame-0 exemplars support the ten-scan result. The harness is unpaced,
  serializes both formats sequentially, and omits future product fields and
  consumer acknowledgement. Full-sequence size is not measured.
- Engineering impact: persisted complete output would need an approved format
  and separate budget; do not treat the digest JSONL as that output. Keep an
  in-process evaluator handoff as a review proposal, not a frozen decision.

## 2026-09-25 - Reconstructed process-return boundary

- Research question: RQ-004. Source: E-043, experiment 0018 and the saved
  100-frame sequence 08/00 headless replay reports.
- MEASURED RESULT: adding each scan's start lag to its load/process interval
  gives approximate process-ready deadline misses of 100/100 on 08 and
  67/100 on 00. Process-only maxima exceed 100 ms on both sequences.
- Confidence and limits: frame IDs were aligned across saved report and timing
  files. This is a reconstruction from the same runs, not a new consumer
  benchmark; the complete product and publication event remain unmeasured.
- Engineering impact: moving the clock before the current audit report alone
  does not pass the zero-miss rule. Keep the output consumer decision open.

## 2026-09-25 - Paced current result with buffered audit

- Research question: RQ-004. Source: E-044, experiment 0019 and its two saved
  100-frame reports, compared with experiment 0016 point/cell counts.
- MEASURED RESULT: a minimal in-process current-result check with audit records
  written after replay missed 2/100 and 3/100 deadlines on sequences 08/00.
  Receipt-age p50 was 84.38/80.12 ms; first scans failed both runs.
- Confidence and limits: IDs, counts, source metadata and per-frame miss totals
  were checked. This has no versioned complete output, exact map-digest
  comparison, model, temporal stages or approved evaluator receipt.
- Engineering impact: audit timing is material, but moving it out of the loop
  alone does not establish the zero-miss release gate. The audit must remain
  bounded and lossless if later moved off the critical path.

## 2026-09-25 - Longer paced current-result window

- Research question: RQ-004. Source: E-044 and the two 1,000-frame reports in
  experiment 0019, using the same harness/configuration as its short runs.
- MEASURED RESULT: sequence 08 missed 28/1,000 strict current-result deadlines,
  including later scans, while sequence 00 missed 3/1,000 at startup. Receipt
  age p99/max was 106.11/128.85 ms on 08 and 90.23/116.98 ms on 00.
- Confidence and limits: contiguous IDs, per-frame/summary miss totals,
  source metadata and first-100 point/cell counts were checked. Machine load
  was uncontrolled. The window is partial and omits all future product stages.
- Engineering impact: the zero-miss rule needs tail evidence over the accepted
  window, including startup; p50/p95 alone would hide these failures.

## 2026-09-25 - FRNet checkpoint contract screen

- Research questions: RQ-001/RQ-004. Sources: E-045, the authors' FRNet
  repository and the Autoware Foundation model artifact card; see screen 0020.
- FACT: the Autoware ONNX weights are 27-class T4Dataset, sensor-specific
  artifacts, not direct SemanticKITTI learning-ID weights. The authors link
  separate SemanticKITTI checkpoints, but this review could not inspect their
  exact files, hashes or separately applicable terms.
- Confidence and limits: primary repository/card metadata support the class
  and sensor distinction. The `hf` Hub query had no DNS access in this sandbox;
  no checkpoint was downloaded, run or measured on the laptop.
- Engineering impact: do not substitute the Autoware artifacts for an approved
  SemanticKITTI model. Pin and inspect an allowed checkpoint before adapter
  work, then measure full-path quality and 100 ms deadline cost.

## 2026-09-25 - CUDA replay platform decision changes RQ-004

- Research question: RQ-004. Input: product-owner platform decision in
  `docs/decisions/0002-cuda-replay-release-platform.md`; local `lspci -nn` shows
  Intel Arc and no NVIDIA GPU, and `nvidia-smi` is unavailable on this laptop.
- DESIGN DECISION: an identified NVIDIA CUDA host will own the first-release
  100 ms zero-miss replay gate; this laptop remains the CPU reference. The
  historical vrgrid CUDA reports are architecture and feasibility leads only.
- NOT VERIFIED: no physical NVIDIA host has been inventoried or used for a
  Drishti full-path run. No CUDA result or complete-output deadline result
  follows from the platform decision.
- Engineering impact: update the R-SYSTEM module, T-008 and AC-008 host boundary;
  retain CPU measurements as historical development evidence. Host inventory,
  output publication, workload and resource gates remain open.

## 2026-09-25 - Installed Patchwork++ GIL verification

- Research question/module: RQ-004, R-SYSTEM. User requested verification of the installed
  native binding before considering multithreading. See E-046 and the experiment 0011 follow-up.
- FACT: CPython 3.12.14, pypatchworkpp 1.4.1, extension SHA-256
  `9d9305bcd2e4ab8973213cca756389b9cb0b0d9dcba96ac3a061de90a6da2734`.
  Upstream v1.4.1 binds `estimateGround` without a release guard; pybind11 does not release
  the GIL implicitly. The installed-binary experiment independently confirms the behavior.
- MEASURED RESULT: two controlled runs on 130,000 synthetic float32 points observed zero
  interior Python heartbeat progress during all 48 native calls across C/F layouts.
  All 24 GIL-releasing controls progressed; all 24 GIL-holding controls blocked. Probe 0021
  saves raw trials, binary/input/harness hashes and conditions in two new JSON reports.
- Validation: Ruff lint/format and strict probe mypy passed after fixing a nullable module-path
  check; confirmation rerun passed. Package regression: 57 passed, 3 CUDA skips.
- Engineering impact: the earlier thread-overlap explanation did not isolate GIL blocking
  from executor overhead. Review a native release boundary or separate-process design before
  expecting Python-thread overlap; retain one ordered owner per estimator. No runtime or
  dependency change, dataset replay, full-array parity or speedup was performed or claimed.
