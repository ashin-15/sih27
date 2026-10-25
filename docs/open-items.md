# Open items

2026-10-24 G0 freeze update: decision 0013 freezes schema 6 `stage=complete`,
its current-scan proof and immutable fused-cell payload, schemas 1 through 5
compatibility, stable failure/rejection codes, D-005 v0.2 gate policy, resource
ceilings and the complete replay protocol. Focused evaluator, threshold and
fused-cell tests pass for the implemented candidate. The CLI still emits
diagnostic schema-5 temporal results, independent final labels and controlled
full-path resource samples are absent, and AC-008 remains open.
See [decision 0013](decisions/0013-g0-complete-result-quality-resource-release-freeze.md),
[decision 0012](decisions/0012-g0-complete-result-and-d005-contract.md) and the
[G0 threshold bundle](d-005-g0-thresholds-v0.2.md).

2026-10-24 approval update: the product owner approved D-005 v0.2, the
unresolved-row `not-verified` policy, all listed resource ceilings and the
release-run handling policy. This freezes the contract boundary only.
Independent final labels, complete-producer integration, controlled target-host
evidence and AC-008 remain open.

The O-001 table row below retains older wording about owner acceptance for
historical continuity; the current approval boundary is the one recorded above
and in decisions 0012 and 0013.

2026-10-22 workflow implementation: [0054](research/experiments/0054-feature-preserving-screen.md)
records 60 accepted but late configuration-screen frames; FP16 changes terrain
summaries, so model defaults remain unchanged. [0055](research/experiments/0055-temporal-cuda-screen.md)
integrates exact CUDA temporal neighbours, with six real full-fused-array parity
checks and fixed device buffers. T-008/O-006 and T-017 remain IN PROGRESS.
The [workflow](sub100ms-workflow.md) preserves drivable/non-drivable/unknown/stale
states and all remaining planned features. Full GPU residency, fused receipts,
quality gates and under-100 ms acceptance remain open.

2026-10-22 research follow-up: [review 0053](research/experiments/0053-sub100ms-pragyaam-review.md)
provides an actionable experiment sequence using pinned Pragyaam kernels and
official Autoware/CUDA integration references. Research and current-contract
exact-output screens can continue; altered semantics, proof rules or public
schema need their specific acceptance review. Under-100 ms on the RTX 4050
remains UNKNOWN for a future complete implementation and failed for the current
path. O-001/O-006 and T-008 remain IN PROGRESS; no new benchmark was run.

2026-10-22 T-008/O-006 update: [experiment 0051](research/experiments/0051-exact-path-screen.md)
records retained exact receipt/visibility optimizations, six-frame source/wheel
schema-5 replay and new paced learned timing. Both runs accepted every receipt
but missed all six deadlines; warm service through receipt was 1,383.73 ms
(source) and 4,285.68 ms (wheel) in uncontrolled conditions. T-006 wheel evidence
is resolved for this slice, while the complete fused schema, independent final
labels, D-005 quality/resource gates and 100 ms acceptance remain unresolved.
[Experiment 0052](research/experiments/0052-frnet-repeatability-screen.md)
retains exact CPU grouping but rejects the GPU candidate; repeated reference
GPU confidences also differ slightly. O-001/O-002/O-005/O-006 stay IN PROGRESS;
O-003 remains BLOCKED. No draft feature or numeric gate was silently approved.

2026-10-15 T-008/O-006 visibility update: [experiment 0050](research/experiments/0050-visibility-chunk-screen.md)
retains a 16,384-beam CUDA batch after two six-frame order pairs and exact
large-boundary evidence parity. All 24 receipts were accepted but every frame
missed 100 ms; controlled tails and peak memory remain unverified. Statuses
are unchanged.

2026-10-15 T-008/O-006 diagnostic update: [experiment 0047](research/experiments/0047-temporal-neighbor-integration.md)
retains an exact toroidal-neighbour lookup optimization. A same-state isolated
screen reduced three-level step calculation from 149.005 to 117.044 ms and
all 30 saved fused summaries matched. This does not change the IN PROGRESS
status or establish the complete 100 ms deadline.

Updated 2026-10-22. This register records blockers and next evidence, not promises of delivery.
Close an item only with a linked decision, implementation, and validation record.

2026-10-15 G0 audit: the staged contract and acceptance text already select the
complete 08/00 windows, sequence 10 frame 206 cold start and 130,000-point
cap. Active T-001/O-001 and release-profile wording was reconciled to that
approval. G0 remained IN PROGRESS because complete fused schema, D-005 numeric
gates, independent final labels and resource limits had no implementation or
frozen acceptance record. The 2026-10-24 implementation pass added the schema
and executable values; the later approval update freezes D-005/resource policy,
but not final evidence. See the dated [work log](work-log.md).

2026-10-14 audit: the [execution plan](execution-plan.md#2026-10-14-submission-readiness-audit)
still has ten IN PROGRESS tasks, one BLOCKED task and three TODO tasks. The
current tree passes 147 tests with four skipped, Ruff, mypy and source/wheel
build, but those checks do not close O-001/O-002/O-003/O-005/O-006/O-009 or
O-013. A temporal regression exposed old free evidence reappearing after a
newer hit; the corrected ordering has a focused fixture and full-suite pass.
O-003 still needs an approved numeric false-free and recovery gate on the
final workload. The complete schema, independent labels and 100 ms zero-miss
evidence remain the submission blockers.
Decision 0009 identifies the RTX 4050 laptop as the release host, and
experiment 0035 reports a sequence-08 learned GPU replay and 30-frame real
CPU/CUDA payload parity. Neither establishes complete-path 100 ms acceptance.

2026-10-14 follow-up: O-009 moves to IN PROGRESS for a new pinned-action
Windows/Linux package-quality workflow. The lock, full model-enabled tests,
Ruff, mypy and build pass locally, but no
hosted workflow result exists yet; CI enforcement, deployment, release,
security-review and ownership policy remain open. [Experiment 0044](research/experiments/0044-temporal-cost-and-neighbour-screen.md)
shows the diagnostic temporal stage's compute cost rising with published cells
on a 30-frame synthetic run. Its small exact neighbour candidate was not
integrated. T-008/O-006 remain open.

2026-10-13 planning update: the [production readiness roadmap](production-roadmap.md)
links open work to each SIH26053 requirement and defines contract, quality,
map/output, 100 ms feasibility and release checkpoints. O-001/O-006 and the
full AC-008 gate remain open. The O-003 row below predates the sequence-08
false-free result (0.549% static false-free in experiment 0035); its remaining
blocker is approval of the numeric gate and recovery policy. O-013's recall
cause is now investigated in experiment 0040; threshold and model decisions
remain open. A fresh complete-current-path three-frame diagnostic in
[experiment 0041](research/experiments/0041-production-path-short-baseline.md)
measured 1,452 ms steady processing p50 with accepted current receipts; it was
not a paced AC-008 run. These updates do not change the statuses in the table.

2026-10-13 T-008 follow-up: [experiment 0042](research/experiments/0042-visibility-chunk-screen.md)
retains an exact-output 8,192-beam visibility chunk after a six-frame screen;
warm visibility p50 was 449.2 ms versus 501.7 ms at 4,096. Complete-path
100 ms feasibility, controlled tails and peak VRAM remain open (O-001/O-006).

2026-10-13 RQ-004 research update: [experiment 0043](research/experiments/0043-100ms-feasibility-options.md)
ranks controlled tracing, FRNet engine screening, device-resident visibility and
map/temporal work, and exhaustive evaluator optimization. These are hypotheses,
not measured speedups. O-001/O-006 remain open; the complete result schema and
D-005 numeric gates are still prerequisites to AC-008 acceptance.

Update 2026-09-30: O-001 now has an identified release host, the RTX 4050 laptop
([decision 0009](decisions/0009-release-host-and-torch-frnet.md)); the 100 ms zero-miss gate is
unchanged and not met. O-002/O-007: an in-process PyTorch FRNet runtime reproduces the
authors' scan-000000 prediction byte for byte on CPU and runs on the GPU; its
sequence-08 score on GPU is 0.675473 mIoU (reference 0.675469). O-003: the first false-free report gives 0.549% static false-free cells over 815 voxel frames (experiment 0035); the grid layout is
verified and a false-free scorer exists; the numeric false-free gate is still undecided.
The per-frame receipt is now light with a sampled deep audit
([decision 0010](decisions/0010-light-receipt-sampled-audit.md)).

T-003 update: [experiment 0025](research/experiments/0025-t003-full-sequence08.md)
now verifies all 4,071 sequence 08 point-semantic predictions, accepted receipts
and official scoring: 0.675469 mIoU and 0.922835 labeled accuracy. The run
combines a 793-frame saved prefix and a new-engine continuation, so continuous
map state is not verified. O-002/O-007 remain IN PROGRESS pending execution of
the approved D-005 gates, exact public checkpoint-byte identity and separate
weight terms.
E-052 adds a fresh three-scan prediction-parity check, current package checks
and CPU timing/memory measurements; the T-003 status is unchanged.
The [D-005 semantic threshold sheet v0.1](d-005-semantic-thresholds-v0.1.md)
proposes exact gates and separate final sets. It is draft, not approved; the
independent labeled range set is not yet available.

| ID | Status | Owner or decision | Open item | Next evidence |
| --- | --- | --- | --- | --- |
| O-001 | IN PROGRESS | Product owner and engineering, D-001/D-005 | [Decision 0009](decisions/0009-release-host-and-torch-frnet.md) identifies the RTX 4050 laptop as the strict 100 ms, zero-miss replay release host; CPU work remains the development reference. An optional CuPy projection, ownership and reduction path is integrated. Synthetic CPU/CUDA parity was established in E-060; experiment 0035 later recorded sequence-08 learned GPU replay and 30-frame real CPU/CUDA payload parity. Short complete-current-path diagnostics in experiment 0041 still miss the budget. The paced checker now uses a synchronous receipt for the complete *current single-frame* in-memory result, with report flush age separate; this is diagnostic, not the approved first-release output. Rerun is outside the 100 ms check. Earlier geometric replay still missed the deadline: the minimal in-process 1,000-frame screen missed 28/1,000 scans on 08 and 3/1,000 on 00 (E-044), before model, temporal stages and complete machine output exist. The JSONL is audit only. E-046 verified that installed Patchwork++ holds the GIL, so a Python thread pool alone does not enable its Python-driven stage overlap; safe GIL release or process isolation and speedup remain unverified. The [CUDA goal](o-001-cuda-frame-path.md) and [release brief](o-001-release-profile.md) capture the remaining proof contract. | Consumer selected: same-process evaluator receipt for the complete versioned immutable result; persist receipts/audit, with full-payload disk persistence outside this endpoint. G0 now has a schema-6 complete-result adapter, executable D-005 candidate checks and resource ceilings, while the CLI temporal path remains diagnostic schema 5. Evidence-only output, complete sequences 08/00, sequence 10 frame 206 cold start and 130,000-point cap are selected for future release validation. Obtain owner acceptance, independent final labels, controlled resource samples and complete-path timing on the RTX 4050; prove AC-008. See [decision 0012](decisions/0012-g0-complete-result-and-d005-contract.md). |
| O-002 | IN PROGRESS | Product owner and engineering, D-002/D-005 | D-002 selects semantic-only FRNet for local CPU development. The checkpoint, source and safe tensor export are pinned; the shared Drishti path and semantic-only receipt passed source and wheel replay (E-050). E-051 records complete sequence 08 official and range metrics; E-052 confirms fresh CPU replay prediction parity and package checks. Exact public-byte identity and separate weight terms remain unverified. D-005 v0.2 semantic gates are approved, but independent final semantic/range evidence remains open. | Establish terms/identity where possible and run the approved D-005 gates on independent final data before T-003 closure. See [decision 0004](decisions/0004-frnet-semantic-cpu-slice.md). |
| O-003 | BLOCKED | Product owner, D-003/D-005 | Evidence-only output is selected; planner/navigation-safe use is deferred. The sequence-08 SSC voxel report measured 0.549% static false-free cells over 815 voxel frames ([experiment 0035](research/experiments/0035-t006-gpu-sequence08.md)); a 2026-10-14 regression closed one old-free-after-new-hit defect. Numeric false-free, unknown/stale handling and recovery criteria remain unresolved. | Freeze the evidence-quality and recovery gates under D-005, then test them on independent final data and the complete receipt path. |
| O-004 | BLOCKED | Product owner, D-004 | Live sensor input and planner-facing output are deferred beyond the first replay release. Future sensor, calibration, deskew and navigation-safety contracts remain unresolved. | Reopen only for an explicitly approved later live/planner milestone; define its contracts before T-009. |
| O-005 | IN PROGRESS | Product owner and engineering, T-003 to T-006 | Learned semantics and bounded T-004/T-005 CPU stages run in the shared path. AC-015 candidate and AC-016 association implementation slices are accepted with caveats; [experiments 0028](research/experiments/0028-t004-saved-prediction-eval.md) and [0030](research/experiments/0030-t005-association-eval.md) record source/wheel and development baselines. Motorcyclist PQ was zero and 50+ m eligible candidate recall was 8/30 in the T-004 diagnostic. Approved [AC-002 traffic gates](ac-002-quality-gates-proposal.md) have not been tested on an independent final set, while wider-obstacle labels and gates remain absent. The 200-frame T-005 diagnostic counted 69 ID switches and 39 fragmentations; full association quality, quantitative motion, temporal map state and free-space proof remain open. | Obtain independent thin/curb/overhang annotations and freeze their metric; measure approved AC-002 gates on final data; freeze AC-004/005 quality limits and test held-out tracking/motion separately; resolve T-003 gates independently. |
| O-006 | IN PROGRESS | Engineering, T-008 | Short complete-current-path GPU diagnostics, synthetic temporal profiling and exact-output batch screens exist (experiments 0041, 0042, 0044, 0047 and 0050), but controlled representative long-run deadline, p99 and peak-memory guarantees are unmeasured. | Benchmark representative long sequences on target hardware with all enabled stages and the frozen complete-result receipt. |
| O-007 | IN PROGRESS | Research, RQ-001/RQ-004 | FRNet is the approved T-003 semantic CPU candidate. E-051 verifies 4,071 aligned predictions and accepted receipts, official 19-class mIoU 0.675469 and supplemental range results. E-052 measures CPU model p50 7,177 ms and fresh short-run process-tree RSS peak 2.44 GB. Exact upstream-byte identity, separate terms and CUDA/release latency remain unverified. | Review per-class/range weaknesses, weight terms and D-005 thresholds; measure any later CUDA complete-path release separately. |
| O-008 | DONE | Evidence owner | Earlier report files remain absent, but the proposed model document now cites two new provenance-complete 100-frame real-data reports in unique run directories. | Preserve reports and do not reinterpret them as full-path or safety evidence. |
| O-009 | IN PROGRESS | Project owner and engineering | `.github/workflows/package-quality.yml` now proposes pinned-action Windows/Linux lock, test, lint, type and build checks. Local lock and package checks pass; a hosted CI run is NOT VERIFIED. Deployment, release, security review, branch protection and ownership policy remain unapproved. | Inspect the first hosted run and repair any platform failures; define required checks, reviewer/owner, release and security policy before declaring production readiness. |
| O-010 | VALIDATION | Engineering, RQ-004 | Packed int64 grouping with overflow fallback is integrated. Edge tests pass; fresh 100-frame CLI replays on sequences 08 and 00 matched all prior input/map digests, cell counts and accounting. The grouping-only run cut audited work p50 to 193.4 ms but still missed 100 ms; later exact-output changes reduced it further. Longer sequence and cross-configuration validation remain. | Validate exact outputs and resource/latency behavior over longer and varied real sequences; profile the remaining preprocessing and mapping costs. |
| O-011 | IN PROGRESS | Product owner and engineering, T-014 | Continuous 10 Hz arrival exceeds the current-path service rate. Experiment 0009 compared SQLite, LMDB and a custom log; LMDB showed lower commit tails than SQLite in short runs and a matched 1,000-scan pair, and passed injected process-kill/map-limit checks. Both long runs reverified all payloads, but source-read variation made LMDB's long-run acquisition p95 slower. A 500-scan LMDB writer with reader/current replay also passed, while replay missed 100/100 processing deadlines. A separate scheduled producer with a two-frame volatile queue preserved 100 frames in one diagnostic run but blocked on 93 queue-full events and fell behind its 10 Hz schedule. No runtime ingress, live-sensor retry contract, disk budget, stale-output policy or measured parallel scheduler exists. | Freeze source ack/retry and overload/freshness behavior; test longer concurrent workers/readers, map growth and retention, physical disk/power faults and complete-path output age. |
| O-012 | DONE | Product owner and engineering, T-007 / SD-D-001 | The bounded semantic cell-class view with legend/count/conflict evidence is accepted under [SD-AC-001 through SD-AC-004](t-007-semantic-dashboard-proposal.md). A fresh learned Rerun recording verified its presentation path. This does not complete full T-007 or AC-007/010. | Preserve the bounded evidence; reopen only for a separately approved raw-point or interactive-filter scope. |
| O-013 | OPEN | Product owner and engineering, T-006 / T-017 / D-005 | Decision 0013 freezes the diagnostic stale TTL at 2.0 s, the unknown/stale-not-drivable rule and the schema-6 fused-map field boundary. Independent terrain/drivability, curb, drop, pothole and overhang labels and numeric quality rows remain blocking `not-verified`. Experiment 0038 drivable recall fell to 0.79 in frames 2000-2249; experiment 0040 attributes the gap mainly to FRNet predicting parking as sidewalk and false interior curb flags. A 2026-10-14 regression fixed older FREE evidence reappearing after a newer obstacle hit. | Obtain the independent feature-labelled final set, run the frozen terrain/evidence gates, and integrate the complete producer without promoting diagnostic fusion or synthetic results to release evidence. |

See `execution-plan.md` for task sequence and `research/modules.md` for research paired to tasks.
The [O-001 contract proposal](o-001-contract-proposal.md) and [decision 0013](decisions/0013-g0-complete-result-quality-resource-release-freeze.md)
now give D-001/D-005 a frozen payload, evaluator, replay, audit, threshold and resource
contract. They do not constitute full-release approval or measured acceptance.
The first reproducible current-path measurements and remaining limits are in
`research/experiments/0001-replay-baseline-protocol.md`.
