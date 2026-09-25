# Work log

Append dated entries for meaningful work. State what changed, what was verified, and what remains.
Detailed test evidence belongs in `testing.md`; active blockers belong in `open-items.md`.

## 2026-09-25 - Ordered point-ID validation and second-sequence replay

- DONE: Profiled `DatasetSource.frames` and found a full NumPy uniqueness operation on
  already increasing original IDs cost about 22 ms per real scan. `ScanFrame` now uses
  a linear ordered-ID check with the original uniqueness fallback for unordered IDs.
  Added tests for ordered and unordered unique IDs, duplicates and negatives.
- MEASURED RESULT: Fresh paced 100-frame runs on sequences 08 and 00 matched every prior
  input/map digest, ID, cell count and accounting record. Load p50 on sequence 08 fell
  from 26.5 to 1.7 ms. Audited work p50 was 149.0/138.9 ms, but all 200 deadlines
  still missed.
- REJECTED: A memoryview snapshot-digest trial matched outputs but did not improve
  full-replay p50; the code was reverted and the run preserved. See experiment 0010.
- VERIFIED: the full suite passed 49 tests, Ruff check/format and mypy passed, and source
  and wheel builds completed after the ordered-ID change. `git diff --check` passed.
- OPEN: O-001 still needs preprocessing/mapping improvement, complete product stages,
  sustained release evidence and remaining resource/overload decisions.

## 2026-09-25 - Range projection optimization under O-001

- DONE: Replaced per-frame range-image sorting with minimum range per pixel and original-ID
  tie resolution. Existing nearest-return, tie and FoV tests still pass.
- MEASURED RESULT: The third 100-frame paced real replay matched all earlier frame IDs,
  input/map digests, cell counts and accounting. Projection p50 was 15.7 ms versus 32.7 ms
  in the packed-only run; audit-inclusive work p50 was 177.2 versus 193.4 ms. It still
  missed 100/100 deadlines, with 7,985.2 ms maximum report age.
- VERIFIED: full package suite passed 48 tests; Ruff check/format, mypy, source/wheel build
  and `git diff --check` passed after the projection edit.
- OPEN: The complete path is absent and the current path remains too slow.

## 2026-09-25 - Remaining current-path hotspot profile

- DONE: Saved a fresh 40-frame sequence 08 timing report and 12-frame `cProfile` output
  after both exact-output optimizations. See experiment 0011.
- MEASURED RESULT: geometric `process` p50 was 133.14 ms. Mapping 57.52 ms and
  preprocessing 33.93 ms remain the largest measured Python stages; frame load 26.53 ms
  and snapshot digest 16.89 ms are outside `process`. Profiled reductions are a lead,
  not an uninstrumented deadline measurement.
- OPEN: The 100 ms complete-path release deadline remains unmet and future model/temporal
  stages are absent; investigate only candidates that preserve exact contracts.

## 2026-09-25 - Exact grouping integration under O-001

- DONE: Integrated packed int64 cell grouping with a row-wise fallback when the full key
  space cannot fit in signed int64. Added edge-case tests for empty, negative, wide and
  extreme keys against the original grouping contract.
- MEASURED RESULT: A fresh 100-frame paced sequence 08 CLI replay matched every earlier
  input/map digest, frame ID, cell count and accounting record. Audit-inclusive work p50
  fell from 319.7 to 193.4 ms. Output age still missed 100/100 deadlines, reaching
  9,520.3 ms maximum, so O-001 remains open and O-010 is in VALIDATION.
- OPEN: Profile and reduce remaining load, preprocessing, projection and mapping costs;
  validate longer and varied sequences. Full model, temporal and viewer costs are absent.

## 2026-09-25 - O-001 strict deadline implementation and test

- DESIGN DECISION: The product owner selected a 100 ms deadline for every first-release
  replay scan on the current laptop, with zero allowed misses in the accepted window.
- DONE: Added `drishti replay --check-100ms` for 10 Hz scheduled arrivals, per-scan
  report age and deadline result, `replay-timing.jsonl`, and exit code 2 on a miss.
  The release gate remains false because the model and temporal path are absent.
- MEASURED RESULT: Saved a 100-frame real sequence 08 check in a unique run directory.
  It completed with 100/100 misses; output age was 11,371.8 ms p50 and 22,129.9 ms max.
  All input/map digests, IDs, cells and accounting matched the earlier headless baseline.
- VERIFIED: the full package suite passed 44 tests, including native paced-replay and
  oracle-guard checks. Ruff check/format, mypy, source build and wheel build passed.
  `git diff --check` and local documentation links passed.
- OPEN: O-001 still needs the complete model/fusion/viewer path, final publication boundary,
  sustained window, overload behavior and memory/disk limits before AC-008 can be judged.

## 2026-09-25 - First-release target selected

- DESIGN DECISION: The product owner selected dataset replay on the current Core Ultra 9 185H
  laptop for the first release. Updated the O-001 brief, PRD, acceptance draft, delivery loop,
  execution plan and open-item register. Live sensor input is deferred.
- OPEN: The 100 ms development goal is not yet an accepted release deadline. Miss policy,
  sustained window, viewer participation, memory/disk bounds, overload behavior and
  planner-facing output remain TBD. No runtime code or release performance was changed.

## 2026-09-25 - O-001 release profile review

- DONE: Reconciled the development profile, geometric CLI baselines, exact-grouping experiment
  and latest durable-ingress research in `docs/o-001-release-profile.md`. The brief separates
  replay compute duration from capture-to-published-output age and lists the fields a release
  gate must freeze. No runtime code or accepted product decision changed.
- OPEN: Product owner selection of replay-first versus live-vehicle scope. Deadline/miss,
  output age, duration, memory/disk and overload thresholds remain TBD under D-001/D-005.

## 2026-09-25 - Durable storage alternatives

- DONE: Built a strict-warning C++20 harness for SQLite WAL/FULL, LMDB default synchronous
  commits and a custom `fdatasync` append log. Three paced 100-scan local ext4 rounds each
  reverified exact payloads, digest and IDs after reopen. Matched 1,000-scan LMDB and
  SQLite runs also passed, with zero measured acquisition intervals above 100 ms.
- DONE: Injected `SIGKILL` during an uncommitted LMDB transaction and an 8 MiB map limit;
  the committed prefixes survived, duplicate ID was rejected and restart resumed in order.
- MEASURED RESULT: LMDB commit p95 was 4.863-6.916 ms in the short rounds versus SQLite's
  15.474-16.990 ms; custom log p95 varied from 3.538 to 17.855 ms. This revises the
  earlier SQLite-first research preference to an LMDB-next prototype recommendation.
- DONE: A 500-scan LMDB writer ran with an independent reader and 100-frame current replay;
  all scans reverified, no acquisition interval exceeded 100 ms, and replay digests/cells
  matched baseline. The replay still missed all 100 processing deadlines. A separate-sandbox
  PID collision caused one writer final-reopen failure; a targeted same-namespace held-reader
  reproduction with unique PIDs passed. See experiment 0009 for the failed and passing runs.
- OPEN: longer concurrent duration, reader lifetime and map growth, source ack/retry,
  physical disk/power faults, retention and
  capture-to-output age. No product runtime path was changed.


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

## 2026-09-25 - O-001 current-laptop paced replay

- DONE: Replayed 100 real scans each from SemanticKITTI sequences 08 and 00 at virtual 10 Hz
  on the selected laptop. Both runs completed, returned expected deadline-failure code 2 and
  saved unique manifests, frame records, timing sidecars and summaries.
- MEASURED RESULT: 200/200 scan deadlines missed. Audited work p50 was 137.0/125.1 ms;
  output-age p50 was 2135.6/1423.0 ms as schedule lag accumulated. All 200 frame IDs,
  input/map digests, cell counts and accounting matched the original headless baselines.
- VERIFIED: 49 pytest cases, Ruff lint/format, mypy and source/wheel build passed after the
  current preprocessing changes. Report IDs, timing counts and summary miss totals agree.
- OPEN: O-001 remains IN PROGRESS. The tested path has no learned or temporal stages and the
  selected 100 ms deadline is unmet. Release workload/window, viewer boundary and resource
  ceilings still need a frozen contract. Evidence is in experiment 0010 and E-031.

## 2026-09-25 - O-001 exact reduction follow-up

- DONE: Simplified radial distance calculations in ownership, preprocessing and projection;
  replaced per-point semantic evidence scattering with an integer histogram. A nonzero-label
  test covers unknown and two distinct learning classes in one cell.
- MEASURED RESULT: fresh sequence 08/00 paced 100-frame runs matched 200/200 original
  geometric outputs. Audited work p50 was 122.3/108.3 ms, but all 200 deadlines missed.
  A 50-frame oracle replay also matched its prior output. Negative `reduceat` candidate
  was left out after a slower one-frame benchmark.
- VERIFIED: 50 tests, Ruff lint/format, mypy, source/wheel build and `git diff --check`
  passed. Evidence and limits are in experiment 0010 and E-032.
- OPEN: O-001 and AC-008 remain unmet. The complete pipeline and accepted sustained
  release gate are still absent.

## 2026-09-25 - Native ground dtype follow-up

- DONE: Passed float32 Nx4 accepted points to the installed Patchwork++ binding and aligned
  the local typing protocol with its declared input. Retained intensity because omitting it
  changed native ground results in a first-frame comparison.
- MEASURED RESULT: final-source 100-frame sequence 08/00 geometric replays matched all
  original baseline outputs; audited work p50 was 120.3/108.4 ms and 200/200 deadlines
  missed. A 50-frame oracle replay also matched its prior outputs.
- VERIFIED: 50 tests, Ruff, mypy and source/wheel build passed. See experiment 0010 and
  E-033. O-001 remains open; full product stages and gate fields are unresolved.

## 2026-09-25 - O-001 Rerun recording measurement

- DONE: Ran a same-source 100-frame paced sequence 08 replay with `--view record`. All
  frame digests, cell counts and accounting matched the headless run; Rerun verified the
  saved recording file.
- MEASURED RESULT: audited work p50 was 132.2 ms and all 100 deadlines missed. Rerun SDK
  submission p50 was 9.93 ms; the `.rrd` file occupied 270.6 MB. Final viewer flush
  occurred after the scan loop, outside the per-frame deadline.
- OPEN: Decide viewer participation and complete-output publication boundary in D-001/D-005.
  O-001 remains IN PROGRESS; see experiment 0012 and E-034.

## 2026-09-25 - O-001 maximum-density cold scan

- DONE: Identified the extracted dataset's largest scan by file size, sequence 10 frame 206,
  and replayed it through the current 100 ms checker from a new engine.
- MEASURED RESULT: all 129,392 points were accepted, but report age was 129.13 ms and the
  one strict deadline missed. The one-scan result does not establish full-sequence behavior.
- OPEN: Keep this boundary in the proposed release workload; O-001 remains IN PROGRESS.
  Evidence is in experiment 0010 and E-035.

## 2026-09-25 - O-001 proposed release gate for review

- DESIGN PROPOSAL: the O-001 brief now specifies full sequence 08 and 00 10 Hz replay,
  a 129,392-point cold boundary scan, an all-frame accepted window, zero loss/duplicates,
  per-scan age at most 100 ms, and provisional 8 GiB RSS/32 GiB artifact ceilings.
- BASIS: sequence counts and density come from saved manifests and the structure-only
  dataset report; record-mode and headless costs come from experiments 0010 and 0012.
  Resource ceilings are explicit assumptions for product review, not measured full-path
  limits or accepted decisions.
- OPEN: the product owner still must approve the workload, resource limits, viewer
  participation and complete-output event. D-002/D-003/D-005 and the full product contract
  remain draft; current code fails the selected deadline.

## 2026-09-25 - O-001 projection-overlap screen

- DONE: Compared warmed thread and spawned-process projection workers against sequential
  ground plus projection on one real sequence 08 frame. Approximate medians were 36.8,
  36.2 and 37.9 ms, respectively.
- DECISION for this candidate: no worker-pool runtime change. Serialization and scheduling
  consumed most of the available overlap in this exploratory sample. See experiment 0011.
- OPEN: O-001 remains IN PROGRESS. Viewer publication choice and full product contract
  are pending; current geometric path still misses 100 ms.

## 2026-09-25 - O-001 per-frame Rerun SDK flush

- DONE: Added per-frame Rerun SDK flush to paced record-mode replay before each frame
  report, with `viewer_flush_ms` and a precise manifest publication label. A viewer
  regression test checks two frame flushes and the final close flush.
- MEASURED RESULT: the fresh 100-frame sequence 08 recording matched prior frame outputs,
  and Rerun verified its 100 cell/raw/semantic chunks. Audited work p50 was 142.0 ms;
  SDK flush p50 was 10.01 ms and all 100 deadlines missed.
- VERIFIED: 51 tests, Ruff lint/format, mypy, source/wheel build and run artifacts passed.
  See experiment 0012 and E-036. Disk `fsync`, display and complete-path timing remain
  unverified; O-001 stays IN PROGRESS.

## 2026-09-25 - O-001 separate scheduled replay producer

- DONE: Added a research-only 10 Hz dataset producer with a bounded two-frame queue,
  one sequence-owned worker, exact frame reports and scheduled-arrival age records.
- MEASURED RESULT: the sequence 08 100-frame run matched all prior frame IDs, input/map
  digests, cell counts and accounting. It missed 100/100 deadlines; queue-full events
  occurred on 93 frames, output age p50 was 1312.4 ms and producer load-start lag
  p50 was 844.3 ms. No frames were silently discarded in this finite run.
- VERIFIED: harness Ruff lint/format and targeted mypy passed; the 10-frame smoke and
  100-frame runs completed with expected failing-gate exit code 2. See experiment 0013
  and E-037.
- OPEN: a blocking in-memory queue cannot establish live or durable no-loss behavior.
  O-001/O-011 remain IN PROGRESS pending the full pipeline and approved overload gate.

## 2026-09-25 - O-001 exact all-unknown aggregation path

- DONE: Profiled 40 real sequence 08 scans, then made all-unknown semantic and motion
  aggregation construct the same dense cell arrays directly. Nonzero inputs retain
  the generic histogram and motion path.
- MEASURED RESULT: 100 sequence 08 and 100 sequence 00 geometric outputs, plus 50
  sequence 00 oracle outputs, matched their saved frame baselines exactly. Mapping
  p50 fell from 47.60/41.29 to 37.16/33.45 ms on 08/00; audited work p50 fell
  from 120.31/108.41 to 110.71/100.04 ms. Both paced runs missed 100/100 deadlines.
  A same-source separate producer missed 100/100 and filled its queue 89 times.
- VERIFIED: focused 18 and full 51 tests, Ruff lint/format, mypy, source/wheel build,
  run output IDs, digests and accounting. See experiment 0014 and E-038.
- OPEN: O-001 remains IN PROGRESS. The complete product path and selected publication
  event still need an approved contract and a full 100 ms gate.

## 2026-09-25 - O-001 recorded replay after aggregation change

- DONE: Replayed 100 sequence 08 frames through the optimized current path with
  Rerun recording and a per-frame SDK flush before each JSONL report.
- MEASURED RESULT: all frame IDs, input/map digests, cell counts and accounting
  matched the same-source headless run. Audited work p50 was 131.34 ms, with
  20.40 ms p50 Rerun submission plus flush; all 100 deadlines missed.
- VERIFIED: `rerun rrd verify` passed and decoded stats showed 100 geometry,
  raw-point and semantic-cell chunks each. See experiment 0015 and E-039.
- OPEN: SDK flush does not prove disk `fsync` or displayed output. O-001 remains
  IN PROGRESS; viewer participation and the complete publication event are open.

## 2026-09-25 - O-001 reuse of fully accepted frame arrays

- DONE: Changed `MappingEngine.process` to reuse a `ScanFrame`'s already immutable
  point and ID arrays when every input point is accepted. Rejected-point scans
  retain the filtered-copy path.
- MEASURED RESULT: all 200 sequence 08/00 geometric and 50 sequence 00 oracle
  frame outputs matched pre-change IDs, digests, cells and accounting. Preprocess
  p50 fell from 14.84/14.49 to 12.19/11.95 ms on 08/00. Audited work p50 was
  108.35/98.93 ms; strict deadline misses were 100/100 and 82/100.
- VERIFIED: focused 10 and full 51 tests, Ruff lint/format, mypy, source/wheel
  build and saved timing-sidecar consistency. See experiment 0016 and E-040.
- OPEN: O-001 remains IN PROGRESS. The current headless path still fails the
  all-frame 100 ms gate, and complete product stages are absent.

## 2026-09-25 - O-001 publication-boundary correction

- DONE: Audited `FrameResult`, current JSONL fields, Rerun logging and saved
  artifacts. Wrote the reviewable output-boundary audit and aligned draft
  acceptance, technical design, interfaces and release brief.
- FACT: `frames.jsonl` is a digest/metrics audit, not a serialized map. Rerun
  includes selected geometry, semantic classes and points, not every snapshot
  field. The existing 100 ms checker therefore measures a diagnostic report
  event, not a verified complete machine-output handoff.
- OPEN: D-001/D-005 must name the first-release payload, consumer and successful
  handoff event before AC-008 can use a publication endpoint. O-001 remains
  IN PROGRESS. See the output-boundary audit and E-041.

## 2026-09-25 - O-001 current snapshot serialization screen

- DONE: Added a research-only stored/deflated ZIP/NPY writer for current
  `MapSnapshot` arrays and scalar metadata; ran ten real sequence 08 frames
  without changing the runtime CLI or source dataset.
- MEASURED RESULT: all ten snapshots round-tripped bit-exact in both formats.
  Stored median was 15.64 MB and 13.59 ms encode; deflate level 6 median was
  0.765 MB and 261.96 ms encode. The sampled stored process-plus-write sum
  was 115.03 ms median; this unpaced screen is not AC-008.
- VERIFIED: Ruff lint/format, targeted mypy, per-frame field checks and saved
  frame-0 exemplar hashes/contents. See experiment 0017 and E-042.
- OPEN: first-release output persistence, payload, consumer and handoff event
  remain unselected; O-001 stays IN PROGRESS.

## 2026-09-25 - O-001 complete-output receipt proposal

- DONE: Made the in-process evaluator option concrete in the O-001 release
  brief: versioned immutable result, schema/frame checks, exact per-scan
  receipt timestamp, bounded queue, zero loss and separate viewer accounting.
  Added the persisted-writer alternative and its required durability/read
  event so the product choice can be reviewed against the same 100 ms rule.
- BASIS: current output audit E-041 and format screen E-042; the selected
  laptop replay and zero-miss 100 ms deadline are unchanged.
- OPEN: this is a DESIGN PROPOSAL, not product-owner approval or an implemented
  consumer. D-001/D-005 and the wider product contract remain draft; O-001
  stays IN PROGRESS.

## 2026-09-25 - Prepared Devin handoff for Codex usage limit

- DONE: Prepared `docs/devin-handoff-o-001.md` with the O-001 laptop replay
  selection, measured current-path failures, output-boundary limits and pending
  product decisions. Verified the local Devin CLI is installed, authenticated
  and loads the repository rules.
- UNKNOWN: Codex provides no usage-limit event trigger or direct Devin handoff
  control in this session. The handoff prompt is ready for a manual launch;
  no Devin session has been started.

## 2026-09-25 - O-001 process-return boundary reconstruction

- DONE: Reconstructed scheduled-arrival-to-process-return age from the saved
  100-frame sequence 08/00 paced reports and recorded experiment 0018/E-043.
- MEASURED RESULT: even this optimistic current-slice endpoint missed 100/100
  and 67/100 deadlines; process-only tails crossed 100 ms on both sequences.
- OPEN: no complete machine consumer or frozen release gate exists. O-001
  remains IN PROGRESS and AC-008 remains NOT VERIFIED.

## 2026-09-25 - O-001 paced in-process current-result screen

- DONE: Added a research harness that paces 100 real scans per sequence,
  checks current-result identity/alignment in process and writes audit after
  the timed loop. Saved new sequence 08/00 reports and experiment 0019/E-044.
- MEASURED RESULT: even this narrow boundary missed 2/100 and 3/100 strict
  deadlines. Point/cell counts and source metadata matched prior saved runs.
- VERIFIED: Ruff lint/format, targeted mypy, report counts and `git diff
  --check`. No complete output schema or future product stages were tested.
- OPEN: O-001 remains IN PROGRESS; the first-release consumer, publication
  event and viewer scope still need approval before a complete-path gate.

## 2026-09-25 - O-001 longer current-result replay screen

- DONE: Reused the research-only paced in-process harness for 1,000 scans on
  each of sequences 08/00 and added the reports to experiment 0019/E-044.
- MEASURED RESULT: strict current-result receipt-age misses were 28/1,000 on
  08 and 3/1,000 on 00. Sequence 08 had 26 misses after frame 1, so startup
  alone does not explain its tail failures.
- VERIFIED: both reports contain contiguous IDs and consistent miss counts;
  metadata hashes and first-100 point/cell counts match earlier runs.
- OPEN: the complete product and approved publication event remain absent.
  O-001 stays IN PROGRESS and AC-008 remains NOT VERIFIED.

## 2026-09-25 - FRNet checkpoint prerequisite screen

- DONE: Reviewed the authors' FRNet repository/LICENSE, linked weight folder,
  Autoware Foundation FRNet artifact card and Drishti class contract. Recorded
  screen 0020/E-045 and updated the model candidate register.
- FACT: Autoware's 27-class T4Dataset ONNX artifacts are not direct
  SemanticKITTI learning-ID weights for Drishti. The authors' separate
  SemanticKITTI checkpoint files, terms and hashes remain UNKNOWN here.
  Their documented Python 3.8/CUDA test stack differs from this laptop's
  Python 3.12/Intel Arc environment; `torch` is absent from the package venv.
- NOT VERIFIED: the `hf` Hub query failed on sandbox DNS; no checkpoint was
  downloaded, executed or timed. O-001's complete-path model and deadline
  evidence remain absent; D-002/D-005 still need a frozen choice.

## 2026-09-25 - O-001 CUDA frame-path direction

- DESIGN DECISION: the user selected a CUDA frame path as the path toward O-001's strict
  100 ms per-scan target. Recorded the goal, provisional implementation and proof boundary
  in `o-001-cuda-frame-path.md` and aligned the open item, plan and draft specification.
- FACT: `lspci -nn` shows Intel Arc graphics and no NVIDIA card on the selected release
  laptop; `nvidia-smi` is unavailable. CUDA cannot be validated on this machine.
- OPEN: decide whether the release gate moves to a named NVIDIA host. Complete-output
  publication, workload and resource gates remain draft. No production CUDA code was
  changed or performance result claimed.

## 2026-09-25 - Finalized the CUDA replay platform direction

- DESIGN DECISION: the user delegated the hardware choice. Decision 0002 moves the
  CUDA-backed, strict 100 ms zero-miss replay gate to an identified NVIDIA host and
  supersedes the Intel laptop as the release acceptance machine. Dataset replay remains
  first-release scope; the Intel laptop remains a CPU development/parity reference.
- DONE: Updated the goal and release briefs, hardware screen, open-item register,
  execution plan and draft PRD/design/acceptance/loop to carry the same platform choice.
- NOT VERIFIED: no specific NVIDIA host has been inventoried or benchmarked for Drishti.
  No CUDA production code or full-path 100 ms result exists. Output, workload, resources,
  model/quality gates and explicit frozen-spec approval remain open.

## 2026-09-25 - Initial CUDA frame path and Rerun deadline split

- DESIGN DECISION: The user deferred CUDA hardware selection and excluded Rerun recording
  and display from the strict 100 ms deadline. The complete machine-output consumer and
  receipt event remain open.
- DONE: Added optional CuPy projection and cell-reduction code under explicit
  `MappingEngine(device="cuda")` and CLI `--device cuda`. The CPU backend remains default.
  Missing CUDA fails before creating a run directory. The paced 100 ms checker now requires
  `--view none`; Rerun can be run and measured separately.
- VERIFIED: On this Intel laptop, the full suite had 52 passed and 3 CUDA tests skipped.
  Ruff lint/format, strict mypy on 27 source files and source/wheel build passed. The
  package contains the CUDA module. No GPU kernels or CUDA parity ran.
- OPEN: CUDA parity and throughput on an NVIDIA host are NOT VERIFIED. Preprocessing,
  Patchwork++, ownership and snapshot construction remain on CPU. The current JSONL is
  audit metadata, and learned/temporal stages are absent, so O-001 and AC-008 remain open.

## 2026-09-25 - CUDA ownership and batched reductions

- DONE: Moved adaptive cell ownership into the optional CuPy array path and grouped
  per-cell integer reductions into fewer host transfers. CPU remains the default.
- VERIFIED: A CPU NumPy array API check compared the CUDA algorithm with the reference
  on 2,000 points in square/radial and geometric/oracle combinations; range images,
  cell inverses and snapshot digests matched. Full suite: 56 passed, 3 real-CUDA tests
  skipped. Ruff, strict mypy, `git diff --check` and source/wheel build passed.
- NOT VERIFIED: This laptop did not execute CuPy kernels or establish any CUDA speedup.
  Filtering, transforms, Patchwork++ and snapshot construction remain on CPU. O-001 and
  AC-008 remain open.

## 2026-09-25 - Current-frame receipt replaces audit flush as diagnostic clock

- DONE: Added `InProcessFrameConsumer` for the implemented single-frame result. It
  synchronously checks identity, point alignment, projection accounting and immutable
  arrays, then hashes the map, observations and range image before returning a receipt.
  The paced 100 ms CLI diagnostic now gates receipt age, saves audit-flush age separately,
  and marks report schema version 2. Rerun remains outside the gate.
- VERIFIED: CLI fixture persisted receipts and separate ages; direct consumer tests
  rejected mismatched identity and incomplete point alignment. Full suite: 57 passed,
  3 real-CUDA tests skipped. Ruff, mypy on 29 source files and source/wheel build passed.
- OPEN: This is a current-slice diagnostic, not the approved complete first-release
  output or consumer. Final payload, consumer, persistence policy, product stages and
  NVIDIA complete-path evidence remain unresolved; O-001/AC-008 stay open.

## 2026-09-25 - Handoff reconciliation and partial output contract

- FACT: Rechecked the dirty `main` working tree, nested instructions, current runtime/tests,
  draft contracts and saved evidence before proceeding. The handoff predates the optional
  CuPy backend, schema-2 current-result receipt and Rerun deadline exclusion. Preserved all
  pre-existing source changes and run artifacts; this session changed documentation only.
- VERIFIED this session: `uv run --frozen --extra viz pytest -q -W error` completed with
  57 passed and 3 CUDA tests skipped. `git diff --check` passed before and after documentation edits.
  GPU execution, a fresh real-data replay and complete-product acceptance were NOT VERIFIED.
- SAVED EVIDENCE INSPECTED, not rerun: the schema-2 CPU geometric receipt runs for
  [sequence 08](../Drishti-2.5/runs/drishti-o001-receipt-seq08-100-20260925/summary.json) and
  [sequence 00](../Drishti-2.5/runs/drishti-o001-receipt-seq00-100-20260925/summary.json)
  each report 100/100 receipt-age misses. Each timing sidecar has 100 matching miss flags;
  manifests record 10 Hz, headless single-frame mode and common source digest
  `124e21695e47ce847ea6b1926205ae36bb18b8c517faab0f71d4c6aa3ccd3a81`.
  These are not experiment 0016's audit-flush endpoint or experiment 0019's minimal
  sanity-check endpoint. No new exact-output comparison or speedup is claimed.
- DESIGN DECISION by product owner: select a same-process evaluator receipt after validation
  of the complete versioned immutable product result as the 100 ms endpoint. Persist receipts
  and audit evidence; full-payload disk persistence is not part of this endpoint. Select
  evidence-only output, with no planner-facing or navigation-safe verdict. Recorded in
  [decision 0002](decisions/0002-cuda-replay-release-platform.md), PRD, design, acceptance,
  release brief, output audit and task records.
- DEFERRED by product owner: approval of the proposed full-sequence workload, window and
  130,000-point cap. Physical host selection remains deferred. Schema, model, numeric quality
  and resource gates, audit/failure behavior and full-contract implementation approval remain
  open. T-001/O-001 stay IN PROGRESS; AC-008 is NOT VERIFIED.
- FACT for the follow-up latency question: source inspection confirms full-scan input,
  sequential engine stages and a newly aggregated single-frame snapshot, not point-arrival
  streaming or a persistent incremental map. `cli.py` also completes receipt and audit before
  loading the next scan. Patchwork++ owns sequence-specific state. Parallelism and incremental
  temporal mapping are different from dynamic programming; no scheduling change was authorized.
  The historical [projection-overlap screen](research/experiments/0011-current-path-profile.md)
  showed less than 2 ms sampled gain, without full-array parity or paced deadline proof.

## 2026-09-25 - Verified installed Patchwork++ GIL behavior

- DONE: User-requested verification of pypatchworkpp 1.4.1 on CPython 3.12.14 using
  version-tagged binding source, pybind11 documentation and an installed-binary probe.
  [Experiment 0011 follow-up](research/experiments/0011-current-path-profile.md#2026-09-25-follow-up-installed-patchwork-gil-behavior)
  records protocol, provenance, E-046, source URLs and reproduction command.
- MEASURED RESULT: two runs with C/F-contiguous synthetic 130,000-point inputs showed no
  interior Python progress during all 48 `estimateGround` calls. Releasing controls progressed
  in 24/24 calls; holding controls blocked in 24/24. The installed call holds the GIL.
- VERIFIED: new research probe passed Ruff lint/format and strict mypy after a nullable-path
  check was corrected. A fresh full package suite passed: 57 tests, 3 CUDA skips.
- OPEN: Python thread pools alone cannot remove the binding's GIL blocker. Native operations
  that already released the GIL may still overlap. Binding release safety, estimator ownership,
  exact-output parity and actual threaded latency benefit remain unverified. No production,
  installed-package, dependency, source-data or prior run-artifact changes were made.
  T-008/O-001 remain IN PROGRESS; this does not satisfy AC-008.

## 2026-09-25 - CPU-first implementation hardware selected

- DESIGN DECISION: product owner clarified that NVIDIA access is not expected soon.
  Implement and run on the current laptop CPU now, retaining CUDA as an optional supported
  backend for later use. GPU access is not a blocker for approved CPU-only development.
- VERIFIED: fresh `lspci -nn` lists Intel Arc graphics and no NVIDIA device; `nvidia-smi`
  is not installed. Physical NVIDIA access and GPU validation remain deferred, not complete.
- Scope: the implementation-hardware choice is settled. No CPU or CUDA 100 ms pass, frozen
  workload, complete output schema or numeric quality/resource approval is implied.
  Records distinguish CPU implementation from future CUDA-specific release validation.
- Next action: confirm the bounded CPU implementation slice, starting with the measured
  native GIL blocker if selected. The broader product contract remains draft; O-001 is open.

## 2026-09-25 - O-001 complete-path contract proposal

- DONE: Drafted [the reviewable contract](o-001-contract-proposal.md), covering a versioned
  immutable result, evaluator validation and receipt, complete replay window accounting,
  bounded audit/drain and failure behavior, and D-005 quality/resource metric definitions.
  Linked it from the draft PRD, technical design, acceptance, task board and loop record.
- FACT: The selected deadline is 100 ms with zero misses to same-process complete-result
  receipt; the present geometric receipt is diagnostic. CPU development and later CUDA release
  evaluation are separate. The model, physical CUDA host, numeric quality/resource limits and
  workload/window/cap remain unresolved; the product contract is not frozen or approved.
- NOT VERIFIED: `hf models list --search SemanticKITTI --limit 10` could not reach the registry
  because DNS resolution failed. No checkpoint was downloaded or inspected. No runtime source
  changed and no new latency or quality result is claimed.
- VERIFIED: `git diff --check` passed. A local-link check across the proposal, task records
  and draft specification found no missing relative targets. Runtime tests were not rerun for
  these documentation-only edits.
