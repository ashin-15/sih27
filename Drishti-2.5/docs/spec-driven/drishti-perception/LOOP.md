# Drishti-2.5 perception delivery loop

Current state: grilling
Current loop: LOOP-001
Frozen specification: none
Current objective: Resolve product decisions and freeze the contract; research and current-path measurement preparation are under way.
Blocking issue: NVIDIA platform, same-process evaluator receipt endpoint and evidence-only output are selected. Live/planner use is deferred. Physical host inventory, complete payload schema, D-002/D-005 quality/resource gates and full-contract implementation approval remain open; D-001 workload/window/cap approval is explicitly deferred.

## O-001 contract drafting - 2026-09-25

- DONE: Wrote `docs/o-001-contract-proposal.md` with proposed complete result fields,
  evaluator checks, paced replay denominator, audit/drain behavior, and D-005 metric worksheet.
- VERIFIED: The proposal distinguishes the selected receipt deadline and evidence-only scope
  from unapproved workload, checkpoint, quality/resource limits and physical CUDA host.
- NOT VERIFIED: No product stages or complete evaluator were implemented, no learned quality
  baseline was obtained, and no CPU/CUDA complete-path deadline pass was measured. The draft
  PRD, design and acceptance contract remain unfrozen.

## Current-result receipt timing - 2026-09-25

- DONE: Added a synchronous in-process diagnostic consumer for the existing `FrameResult`.
  It checks identity, point alignment, accounting and immutable array payloads, hashes
  the current result and returns a receipt. Paced replay now checks scheduled arrival
  to receipt; audit JSONL flush age is saved separately under report schema version 2.
- VERIFIED: The full suite had 57 passed and 3 real-CUDA tests skipped; Ruff, mypy and
  source/wheel build passed. CLI and direct consumer tests cover receipt identity and
  rejection of incomplete or mismatched current results.
- NOT VERIFIED: This receipt does not settle the final complete-output consumer or
  schema. Learned/temporal stages, sustained zero-miss gate and GPU execution remain
  open. O-001 and AC-008 are not met.

## Initial CUDA frame-path implementation - 2026-09-25

- DESIGN DECISION: Rerun is outside the strict 100 ms deadline. Paced checks require
  `--view none`; recording and display are measured separately.
- DONE: Added explicit CPU/CUDA backend selection. The CUDA path uses CuPy for range
  projection and cell grouping/reductions, then returns the existing immutable host
  contracts. CLI reports include the selected device. Missing CUDA fails before output
  creation. CPU tests and unavailable-device behavior pass on this laptop.
- NOT VERIFIED: CUDA kernels, parity and latency on a real NVIDIA device. Filtering,
  Patchwork++, ownership, snapshot construction, the model and temporal stages are not
  device-resident. The complete output consumer remains undecided, so AC-008 is open.

## CUDA ownership and reduction-transfer loop - 2026-09-25

- DONE: Moved adaptive cell ownership into the CuPy array path and batched per-cell
  integer reductions before returning immutable NumPy snapshots. Filtering, transforms,
  Patchwork++ and snapshot construction still run on CPU.
- VERIFIED: A 2,000-point NumPy array API check matched reference range images,
  cell inverses and snapshot digests across square/radial and geometric/oracle cases.
  The full suite had 56 passed and 3 real-CUDA tests skipped; Ruff, mypy and build passed.
- NOT VERIFIED: real CUDA execution or transfer/latency benefit. O-001 and AC-008 remain
  open pending complete-output contract, product stages and eventual NVIDIA measurements.
Next action: Respect deferred host/workload approval; resolve complete payload schema, model and quality/resource/audit gates, then freeze PRD, technical design and acceptance and request full-contract approval.
Last updated: 2026-09-25

## Current loop - LOOP-001

- Related FRs/ACs: all draft IDs.
- Assignments: main agent only.
- Outputs: current-state audit, draft specification, standalone README and tooling cleanup; root agent operating manual and research/execution scaffold.
- Baseline checks: 42 tests passed; three-frame synthetic headless demo completed with release gate false; Ruff lint/format, mypy and source/wheel build passed. Dataset and full-path performance were not verified.
- Main-agent judgment: the current package is a valid single-frame mapping prototype. Requested perception and real-time capabilities are absent from the active path.
- Risks: model architecture, target hardware, deployment scope, safety use and numeric gates are not decided. Real dataset access was not used in this audit.
- Next state: awaiting-spec-approval after open decisions and frozen acceptance are resolved.

## CUDA frame-path direction - 2026-09-25

- Related FRs/ACs: FR-008/AC-008 and AC-012, still draft.
- DESIGN DECISION: the user selected CUDA as the O-001 implementation direction.
- FACT: the selected Core Ultra 9 185H laptop exposes Intel Arc graphics and no NVIDIA
  CUDA device. The goal brief records the proposed backend and parity/latency proof.
- Judgment: no CUDA production code or target-hardware measurement exists in Drishti.
  The earlier current-laptop release choice cannot serve as a CUDA acceptance host.
- Next action: decide the release machine, complete the output/workload/resource contract,
  freeze the specification and obtain explicit implementation approval.

## CUDA release-platform decision - 2026-09-25

- Related FRs/ACs: FR-008/011 and AC-008/012, still draft.
- DESIGN DECISION: the user delegated and finalized a NVIDIA CUDA host as the release-gate
  platform. The earlier Intel laptop release-host selection is superseded for this gate; that
  laptop remains the CPU development and parity reference. Dataset replay, 100 ms from
  scheduled arrival to complete output and zero misses remain selected.
- Evidence: `docs/decisions/0002-cuda-replay-release-platform.md` and the local hardware
  inventory. Historical vrgrid timing is rationale, not Drishti performance evidence.
- Judgment: the platform family is decided; a specific physical host, full product contract,
  implementation and target-hardware measurements are still missing.
- Next action: inventory the NVIDIA host and freeze the remaining product and acceptance
  decisions before production CUDA work.

## Replay-first release decision - 2026-09-25

- Related FRs/ACs: FR-008/011 and AC-008/011, all still draft.
- DESIGN DECISION: the product owner selected dataset replay on the current Core Ultra 9 185H
  laptop for the first release. Live sensor input is deferred beyond this release.
- Evidence: user decision and `docs/o-001-release-profile.md`; earlier geometric replay and
  recorder measurements remain bounded by their documented workloads.
- Judgment: D-001 hardware/replay branch and D-004 live-input branch are resolved. The 100 ms
  development goal is not a release deadline. Miss policy, sample window, viewer costs,
  memory/disk limits and planner-facing output scope remain open; no product code changed.

## Per-scan deadline and current-path check - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008, both still draft overall.
- DESIGN DECISION: the product owner selected 100 ms from scheduled scan arrival to complete
  publication, with zero allowed misses in the accepted window.
- Implementation: `drishti replay --check-100ms` paces the current geometric path at 10 Hz,
  writes per-frame schedule lag and JSONL report age, and returns code 2 for any miss. It
  leaves `realtime_release_gate_met` false because the complete product path is absent.
- MEASURED RESULT: the saved 100-frame sequence 08 check missed 100/100 deadlines. Output
  age was 11,371.8 ms p50 and 22,129.9 ms maximum after backlog growth. All 100 frame IDs,
  input/map digests, cells and accounting matched the prior headless baseline.
- Judgment: a current-path measurement and failing check are implemented. AC-008 remains
  blocked by missing model/fusion, complete publication boundary, sustained window, viewer
  scope and resource limits. No real-time release claim is made.

## Exact grouping integration under the paced check - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008, still draft overall.
- Implementation: packed int64 grouping with overflow fallback now replaces row-wise
  `np.unique` in active cell aggregation. Edge cases and exact-output CLI comparison pass.
- MEASURED RESULT: 100-frame paced sequence 08 work p50 fell from 319.7 to 193.4 ms;
  all 100 scan-report ages still missed 100 ms. The optimized run matched every prior
  frame ID, input/map digest, cell count and accounting record.
- Judgment: O-010 enters validation; O-001 remains open. The current geometric path
  is still too slow and the complete future stages remain absent.

## Nearest-return projection under the paced check - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008, still draft overall.
- Implementation: per-pixel minimum range plus minimum original ID on ties replaces a
  full eligible-point sort in the auxiliary range projection.
- MEASURED RESULT: 100-frame paced sequence 08 projection p50 fell from 32.7 to 15.7 ms;
  audit-inclusive work p50 fell from 193.4 to 177.2 ms. Exact sampled CLI outputs matched,
  but all 100 scan-report ages still exceeded 100 ms.
- Judgment: O-001 remains open. Model, temporal state, complete publication, resource
  limits and sustained release window still lack implementation or evidence.

## Ordered point-ID validation under the paced check - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008, still draft overall.
- Implementation: strictly increasing IDs use a linear uniqueness check; unordered IDs
  retain the full uniqueness check. Direct ID contract tests cover both paths.
- MEASURED RESULT: 100-frame sequence 08 and 00 replays matched all earlier frame IDs,
  input/map digests, cells and accounting. Load p50 on sequence 08 fell to 1.7 ms, but
  audited work p50 was 149.0/138.9 ms and both runs missed every 100 ms deadline.
- Rejected candidate: a memoryview digest trial preserved outputs but did not improve
  full-run p50, so it was reverted. Evidence is retained in experiment 0010.
- Judgment: O-001 remains open. Exact sampled outputs are preserved across two sequences;
  complete product stages and sustained/resource gates remain absent.

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

## Current-laptop O-001 replay - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: two fresh 100-frame geometric 10 Hz replays on the selected laptop
  matched earlier sequence 08/00 frame digests and accounting, but missed all 200 strict
  100 ms deadlines. Audited work p50 was 137.0/125.1 ms.
- Evidence: experiment 0010, E-031 and both saved run directories. Full pytest, Ruff,
  mypy and build passed on the active source.
- Judgment: current-path deadline fails; future complete-path release gate remains NOT
  VERIFIED. O-001 stays IN PROGRESS pending the remaining contract and complete-path work.

## O-001 distance and histogram loop - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: exact sampled output across 200 geometric and 50 oracle frames after
  distance and semantic-histogram changes. Audited work p50 was 122.3/108.3 ms on
  sequences 08/00; all 200 paced geometric deadlines still missed.
- Evidence: experiment 0010 and E-032; 50 tests, Ruff, mypy and build passed.
- Judgment: preserve the optimizations, keep O-001 open, and measure the complete path
  against a frozen release workload before any 100 ms claim.

## O-001 native ground dtype loop - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: float32 Nx4 native ground input preserved sampled geometric and oracle
  frame output. On final-source 100-frame sequence 08/00 paced runs, audited work p50 was
  120.3/108.4 ms and every scan missed the 100 ms deadline.
- Evidence: experiment 0010 and E-033; 50 tests, Ruff, mypy and build passed.
- Judgment: O-001 remains open and the future complete-path gate is NOT VERIFIED.

## O-001 recorded-view timing loop - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: the 100-frame record-mode sequence 08 run matched headless outputs,
  missed all deadlines, and had 132.2 ms audited work p50. Rerun submission p50 was
  9.93 ms and the verified recording used 270.6 MB.
- Evidence: experiment 0012 and E-034.
- Judgment: the current per-scan check does not measure final recording flush or actual
  display. Viewer participation and publication boundary remain open product decisions.

## O-001 high-density boundary loop - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: the 129,392-point sequence 10 frame 206 cold replay completed but
  missed its one 100 ms deadline at 129.13 ms report age.
- Evidence: experiment 0010 and E-035.
- Judgment: include a near-130,000-point boundary case when freezing the workload; this
  isolated failure does not replace a sustained complete-path gate.

## O-001 release-gate proposal - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- DESIGN PROPOSAL: full sequence 08 and 00 replays at 10 Hz, a maximum-density cold scan,
  all-frame zero-miss acceptance, zero drops, and provisional process/disk ceilings are
  written in `docs/o-001-release-profile.md` for product review.
- Evidence and limits: experiments 0010/0012, E-034/E-035 and the structure-only report.
  The resource numbers are assumptions; publication boundary and viewer scope are open.
- Judgment: this is not a frozen contract or a release pass. O-001 remains IN PROGRESS.

## O-001 per-frame Rerun flush loop - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: record-mode paced replay now flushes through the Rerun SDK before each
  frame report. A 100-frame sequence 08 run matched prior map outputs and missed every
  deadline; audited work p50 was 142.0 ms and SDK flush p50 was 10.01 ms.
- Evidence: experiment 0012, E-036, 51 tests, Ruff, mypy and build.
- Judgment: diagnostic SDK flush is measurable, but disk `fsync`, rendered display and
  complete-path publication decisions remain open. O-001 stays IN PROGRESS.

## O-001 independent-arrival diagnostic - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: a separate 10 Hz sequence 08 producer feeding a bounded two-frame
  queue preserved all 100 sampled outputs, but the queue filled 93 times and every
  output age missed 100 ms. Output age p50 was 1312.4 ms; producer load-start lag
  p50 was 844.3 ms.
- Evidence: experiment 0013, E-037 and saved per-frame reports.
- Judgment: the current geometric worker cannot keep up with this producer. Its
  blocking volatile queue does not establish lossless live ingestion. O-001 remains
  IN PROGRESS and the complete-path release gate remains NOT VERIFIED.

## O-001 all-unknown evidence optimization - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: direct construction of exact all-unknown semantic and motion cell
  arrays preserved 200 geometric and 50 oracle frame outputs. Audited work p50 was
  110.71/100.04 ms on sequence 08/00, down from 120.31/108.41 ms; both paced
  runs still missed all 100 deadlines. A separate producer still missed 100/100.
- Evidence: experiment 0014, E-038, 51 tests, Ruff, mypy and build.
- Judgment: keep the exact-output change, but O-001 remains IN PROGRESS. The current
  geometric path and future complete path have no 100 ms release pass.

## O-001 recorded-view follow-up after optimization - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: a same-source 100-frame Rerun recording matched the optimized
  headless outputs. Audited work p50 was 131.34 ms, Rerun submission plus SDK
  flush p50 was 20.40 ms, and all 100 scheduled deadlines missed.
- Evidence: experiment 0015, E-039 and verified RRD with 100 geometry/raw/semantic
  cell chunks each.
- Judgment: the optimized recorded diagnostic still fails 100 ms. D-001/D-005
  must select viewer participation and complete output; O-001 remains IN PROGRESS.

## O-001 immutable input-array reuse - 2026-09-25

- Related FRs/ACs: FR-008 and AC-008/012, still draft.
- MEASURED RESULT: reusing already immutable frame points and IDs when all points
  pass preprocessing preserved 200 geometric and 50 oracle sampled outputs.
  Sequence 08/00 audited work p50 was 108.35/98.93 ms; the strict deadline
  still missed 100/100 and 82/100 scans.
- Evidence: experiment 0016, E-040, 51 tests, Ruff, mypy and build.
- Judgment: preserve the exact-output change. O-001 remains IN PROGRESS and
  full-path AC-008 is NOT VERIFIED.

## O-001 output-boundary audit - 2026-09-25

- Related FRs/ACs: FR-007/008 and AC-007/008/010, still draft.
- FACT: the CLI's `frames.jsonl` is audit metadata and digests, not a full map
  payload. Rerun publishes selected visual layers but not every `MapSnapshot`
  field. The current clock ends at report flush and cannot certify complete
  first-release machine-output publication.
- Evidence: `docs/o-001-output-boundary-audit.md`, E-041, current source and
  saved headless/recorded artifacts.
- Judgment: freeze a versioned payload, consumer and handoff event under
  D-001/D-005. The current check remains diagnostic; O-001 stays IN PROGRESS.

## O-001 snapshot serialization screen - 2026-09-25

- Related FRs/ACs: FR-007/008 and AC-007/008/010, still draft.
- MEASURED RESULT: ten current snapshots round-tripped bit-exact through stored
  and deflated ZIP/NPY archives. Stored median size/encode was 15.64 MB/13.59 ms;
  deflate level 6 was 0.765 MB/261.96 ms. This was an unpaced two-format screen.
- Evidence: experiment 0017, E-042 and saved exemplar files.
- Judgment: persisted output cost is material and its format/consumer remains
  a D-001/D-005 decision. The screen is not AC-008; O-001 stays IN PROGRESS.

## O-001 proposed complete-output receipt - 2026-09-25

- Related FRs/ACs: FR-007/008 and AC-007/008/010, still draft.
- DESIGN PROPOSAL: the O-001 release brief defines a versioned immutable
  result accepted by a same-process evaluator. A receipt after schema and
  frame checks would be the proposed 100 ms publication event; queued but
  unacknowledged output would not count. A persisted writer needs a separate
  lossless write/read event and disk-failure contract.
- Evidence and limits: E-041/E-042 show why current JSONL, Rerun and simple
  serialization cannot silently stand in for this event.
- Judgment: product-owner selection and full contract approval remain open.
  No runtime consumer or AC-008 pass has been claimed. O-001 stays IN PROGRESS.

## Handoff reconciliation and output selection - 2026-09-25

- Related FRs/ACs: FR-006/007/008/010/011 and AC-006/007/008/010; full contract still draft.
- DESIGN DECISION: product owner selected same-process complete-product evaluator receipt
  as publication, persisted receipts/audit without full-payload disk persistence in the
  endpoint, and evidence-only output. Live/planner-facing use is deferred. Rerun remains
  outside the 100 ms deadline. See decision 0002 and the updated PRD decision log.
- DEFERRED: approval of the proposed workload/window and density cap; physical host selection
  remains deferred. Complete payload, model, numeric quality/resources and audit/failure gates
  remain open. No full-contract implementation approval or scheduling change was given.
- VERIFIED: fresh `uv run --frozen --extra viz pytest -q -W error`: 57 passed, 3 CUDA skips.
  Inspected saved schema-2 CPU receipt manifests/summaries/timing flags, not a fresh replay:
  100/100 misses on each of 08/00. Evidence and limitations are in `docs/work-log.md` under
  "Handoff reconciliation and partial output contract". No runtime or run artifact was edited.
- Judgment: partial product decisions recorded; O-001/T-001 remain IN PROGRESS and AC-008
  remains NOT VERIFIED. Current state stays grilling until remaining gates can be frozen.

## Installed native GIL verification - 2026-09-25

- User requested verification only. E-046 / probe 0021 confirms installed pypatchworkpp 1.4.1
  retains the GIL: no interior Python progress in 48 native calls, with positive/negative
  controls passing across two runs. Version-tagged source has no explicit release guard.
- Probe Ruff lint/format and strict mypy passed; full package suite: 57 passed, 3 CUDA skips.
  Evidence, limitations and reproduction are in the experiment 0011 GIL follow-up.
- Judgment: Python thread pools alone do not remove this blocker. No binding, runtime or
  dependency change was made, and no threaded speedup or AC-008 pass is claimed. T-008/O-001
  remain IN PROGRESS; full product contract stays draft.

## CPU-first implementation hardware - 2026-09-25

- DESIGN DECISION: use the current laptop CPU for implementation and execution now, with
  optional CUDA support for later NVIDIA access. GPU-specific validation is deferred and
  must not block approved CPU-only development. See decision 0002 and the PRD decision log.
- Fresh hardware check: Intel Arc, no NVIDIA device listed, `nvidia-smi` unavailable.
- Judgment: implementation hardware is settled; full output/workload/quality/resource gates
  and a demonstrated deadline remain open. Confirm a bounded CPU slice before changing its
  native dependency or starting the still-draft product stages.

## Approved CPU GIL-release slice - 2026-09-25

- Approval: product owner explicitly selected "Approve CPU GIL slice". This authorizes
  safe native GIL release, preserved outputs/estimator ownership, regression verification
  and measured overlap. It does not approve the broader product contract or a 100 ms claim.
- Frozen slice requirements: use unchanged Patchwork++ 1.4.1 computation; release the GIL
  only around Python-free native work; retain ordered exclusive sequence ownership and
  immutable aligned outputs; keep CUDA optional and unchanged.
- Implementation: a packaged private native adapter built from checksum-pinned upstream
  source, atomic estimate-and-copy of both index arrays, and explicit concurrent-use guards.
  Do not patch an installed binary in place. Preserve the old binding as a development
  parity reference. Package/build changes are limited to shipping this adapter reproducibly.
- Acceptance: a previously failing native heartbeat test passes; positive/negative controls
  remain valid; exact labels and snapshot digests match the reference on declared synthetic
  sequences/configurations; concurrent ownership is enforced; full tests/lint/format/types
  and installed-wheel smoke pass. Measure sequential/overlap performance without requiring
  or fabricating a speedup; do not adopt a runtime scheduler without demonstrated benefit.
- Allowed scope: native adapter/build configuration, `ground.py`, engine ownership guard,
  native provenance in CLI reports, focused tests and experiment/documentation evidence.
  Forbidden scope: learned/temporal features, CUDA changes, source dataset or old run edits.
- Slice state: implementing. Full-product state remains grilling; NVIDIA tests and real-data
  acceptance remain separate, deferred evidence.
