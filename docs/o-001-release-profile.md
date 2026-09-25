# O-001 release profile decision brief

Status: DRAFT gate with CUDA platform, deadline, evaluator-receipt endpoint and evidence-only output selected, 2026-09-25. Workload approval is explicitly deferred. The original
current-laptop release-machine choice was superseded by [decision 0002](decisions/0002-cuda-replay-release-platform.md):
the CUDA-backed replay gate will run on an identified NVIDIA host. The 100 ms per-scan deadline
and zero-miss policy remain selected. This does not freeze the remaining D-001/D-005 fields,
approve the full product contract, or
establish a real-time guarantee. See [the open-item register](open-items.md),
[draft PRD](../Drishti-2.5/docs/spec-driven/drishti-perception/PRD.md) and
[draft acceptance contract](../Drishti-2.5/docs/spec-driven/drishti-perception/ACCEPTANCE.md).

## Established evidence

- DESIGN DECISION for development: current Core Ultra 9 185H laptop, 10 Hz replay, up to 130,000
  points per scan, and an unmet 100 ms capture-to-published-output engineering goal. This is
  not a release profile. See [hardware screen](research/hardware-targets.md).
- MEASURED RESULT: two 100-frame headless geometric CLI replays took 310.3/326.9 ms p50
  including audit and missed the configured 100 ms budget on all 200 frames. They omitted the
  model, temporal state, durable ingress and live source. The measured replay duration is not
  capture-to-output age. See [experiment 0001](research/experiments/0001-replay-baseline-protocol.md).
- MEASURED RESULT: isolated packed grouping matched sampled geometric outputs and reduced
  `process` p50 to 143.19/150.54 ms on sequences 00/08; it was not integrated into the CLI.
  See [experiment 0003](research/experiments/0003-lossless-10hz-design.md).
- MEASURED RESULT: short local durable-ingress prototypes reverified paced raw scans. The
  500-scan LMDB writer/read/replay run still had 100/100 processing deadline misses. The
  recorder did not establish sensor capture, live output age or a complete-path gate. See
  [experiment 0009](research/experiments/0009-storage-backend-comparison.md).

## First decision: release use and hardware - superseded laptop selection

| Option | Hardware and scope to name | Consequence for O-001 |
| --- | --- | --- |
| Replay-first, earlier laptop selection, now superseded for the CUDA gate | Current Core Ultra 9 185H laptop was the release test machine; dataset replay remains the input contract. Name whether the viewer is enabled in the gate. | The laptop remains the CPU reference. The CUDA release gate moves to an identified NVIDIA host. |
| Live vehicle | Name the actual compute unit, sensor, point density, scan timestamps, pose/calibration feed, output consumer and safe response to stale output. | Sensor-to-output age, source ack/retry, overload and vehicle fault behavior become release-blocking. A laptop replay cannot certify this branch. |
| Keep undecided | Continue development measurements only. | FR-008/AC-008 and the release gate remain blocked. |

HISTORICAL DESIGN DECISION, 2026-09-25: the product owner initially selected replay on the
current laptop. The later CUDA platform decision supersedes the hardware portion only. Live
sensor input and vehicle hardware remain deferred beyond this release. The later handoff
review selected evidence-only output and deferred planner-facing use under D-003/D-004.
Rerun was also excluded from the 100 ms deadline.

DESIGN DECISION, 2026-09-25: each scheduled scan must publish its complete first-release
output within 100 ms on the selected release host. This is a per-scan deadline, so the allowed
deadline-miss count is zero across the accepted measurement window, including its first scan.
Warmup may occur before the first scheduled arrival. It cannot remove slow scans from the
accepted window. Run length remains deferred; the later handoff review selected the evaluator
receipt endpoint below, with the complete payload schema still to be frozen.

DESIGN DECISION, 2026-09-25: the CUDA-backed 100 ms replay gate will run on an identified
NVIDIA CUDA host. This Intel Arc laptop remains the CPU development and parity reference.
The exact host inventory and access are acceptance prerequisites, not a reopening of the
platform-family choice. Historical vrgrid results are reference evidence only.

DESIGN DECISION, 2026-09-25: Rerun recording and display are outside the strict
100 ms deadline. Their cost and resource use are measured separately.

## Selected output boundary and remaining gate fields

DESIGN DECISION, 2026-09-25 handoff review: use a same-process evaluator as the first-release
machine consumer. It validates and acknowledges the complete versioned immutable product
result. Timestamp receipt return on the same monotonic clock as scheduled arrival; every
selected scan must receive that acknowledgement within 100 ms. Persist receipts and audit
evidence. Full-payload disk persistence is not part of this endpoint. Output is evidence-only
for evaluation and visualization, not planner-facing or a navigation-safe verdict. See
[decision 0002](decisions/0002-cuda-replay-release-platform.md).

A receipt for a digest-only report, visualization projection or partially populated payload
is insufficient. The current geometric receipt is a diagnostic, not the complete future
payload. Schema fields and exact validation checks still need a frozen technical contract.
Rerun recording and display remain outside the deadline and are measured separately.

| Field | Measurement contract or proposal | Decision still needed |
| --- | --- | --- |
| Workload | Record sequences/splits, cadence, scan count/density, poses, calibration, mode, checkpoint and code/config hashes. | Workload/window/cap approval explicitly deferred; quality-evaluation splits and model also open. |
| Throughput | Count arrivals, receipts, drops, backlog and queue age over the accepted window. | Window, headroom, queue limits and overload behavior. |
| Output age | Scheduled arrival to complete-product evaluator receipt on one monotonic clock; report p50/p95/p99/max and every miss. Strict 100 ms and zero misses are selected. | Complete payload schema and validation checks; measurement window. |
| Audit | Persist receipts and audit evidence without silently losing records or hiding their effect on later scan ages. | Bounded audit scheduling, drain/failure behavior and retention. |
| Resources | Measure process-tree RSS, GPU memory, queue depth and artifact/disk use, not just snapshot bytes. | Physical host inventory, numeric ceilings, reserve and stop thresholds. |
| Evidence quality | Preserve explicit unknown/stale states and validate learned, object, motion, temporal and free-space evidence without a navigation-safe claim. | D-002 model and D-005 numeric quality/recovery gates. |

DESIGN CONSTRAINT: a finite queue cannot keep output fresh when arrival rate sustainably
exceeds service rate. Parallel throughput alone is not a per-scan latency guarantee.
AC-008 remains BLOCKED by the incomplete product path and remaining acceptance contract.

## Replay-workload proposal, approval explicitly deferred

The product owner deferred this proposal during the handoff review. The following is retained
for later review, not adopted as a release workload, quality split or configured capacity.

| Gate field | Proposed rule | Basis and open decision |
| --- | --- | --- |
| Release replay | All 4,071 scans of SemanticKITTI sequence 08 and all 4,541 scans of sequence 00 as separate ordered 10 Hz replays, with a new engine per sequence and complete product mode. | Counts are in local manifests. Performance workload approval is deferred; these are not designated held-out quality splits. |
| Density boundary | Sequence 10 frame 206, the extracted dataset's 129,392-point maximum, as a cold-start first-scan check; explicitly reject scans above a proposed 130,000-point cap. | The historical one-frame check missed at 129.13 ms. Cap approval is deferred; current saved default configs allow 150,000 points. |
| Accepted window | Count every selected scan including the first. Initialize/load the checkpoint before arrival without processing or discarding selected scans during warmup. | The no-excluded-slow-scans rule follows the selected zero-miss policy; sequence/window approval is deferred. |
| Integrity and service | One ordered complete output per arrival with zero drops/duplicates/skips. After timing misses, continue valid processing for diagnostics but fail the gate and expose stale results. | This proposal does not yet freeze fault/overload behavior. Zero deadline misses remains selected. |
| Resources | Set RSS, VRAM and artifact ceilings from the host; require no run-induced swap growth. | Former Intel-laptop 8 GiB RSS/32 GiB artifact candidates are not adopted for NVIDIA; numeric limits remain open. |

The original receipt proposal also suggested bounded post-receipt label scoring, one saved
receipt per arrival and queues that drain by sequence end. Those technical details, audit
scheduling and failure behavior still need review alongside the payload schema. Selecting the
receipt endpoint does not approve the whole prior proposal or broader implementation.

NOT SELECTED: durable full-payload writer or external-process acknowledgement as the 100 ms
endpoint. Either would require a revised contract. The
[current-snapshot format screen](research/experiments/0017-snapshot-output-screen.md)
remains useful evidence of persistence cost, not a required release output format.

The current code cannot pass the full product gate: learned inference, detection, tracking,
temporal mapping and complete product publication are absent, and current-slice replay has
missed the strict deadline. D-001/D-002/D-005 and explicit full-contract approval remain open.

A [ten-frame current-snapshot format screen](research/experiments/0017-snapshot-output-screen.md)
adds a resource constraint to this proposal. Its median uncompressed archive
was 15.64 MB per scan; linear extrapolation across the proposed 8,612 scans
is about 125.5 GiB, above the former Intel-laptop 32 GiB artifact candidate, which is not
adopted for NVIDIA. Deflate level 6 reduced the sampled archive to 0.765 MB median but took
261.96 ms median just to encode. These are not full-sequence or full-product results.
The selected evaluator receipt does not require full-payload disk persistence in its endpoint.

## Current-path measurement implementation

`drishti replay --check-100ms` schedules scans at 10 Hz and checks synchronous receipt
of the current in-memory `FrameResult` against 100 ms from scheduled arrival. The
diagnostic consumer checks identity, point alignment and immutable current arrays,
then hashes the map, observations and range image before returning a receipt. The CLI
saves per-frame receipt age, lag and separate JSONL report-flush age in
`replay-timing.jsonl`, records a check result in `summary.json`, and exits with code 2
when any receipt misses. Report schema version 2 identifies this changed endpoint.
The check requires `--view none`; Rerun recording and display are measured separately.
Earlier paced report-flush and recorded-view runs are historical diagnostics from their
saved source digests, not invocations supported by the current checker. This is a
current geometric-path check, not AC-008 release certification: there is no model,
temporal fusion, frozen complete first-release output schema or implemented product evaluator. The frame
JSONL contains digests and audit metrics, not map arrays, and the
Rerun recording omits several `MapSnapshot` fields. See the
[output-boundary audit](o-001-output-boundary-audit.md). Sequential loading after
a missed schedule does not simulate an independent live source. The regular
`frame_budget_ms` configuration remains a separate diagnostic threshold.

MEASURED RESULT: the [100-frame sequence 08 check](../Drishti-2.5/runs/drishti-o001-paced-seq08-100-20260925/summary.json)
missed 100/100 deadlines; scheduled-arrival-to-frame-report-flush age was 11,371.8 ms p50
and 22,129.9 ms maximum as lag accumulated. Input and map digests, cell counts and accounting
matched the prior 100-frame baseline exactly. The run was headless and geometric; the
complete-path deadline remains NOT VERIFIED.

Subsequent exact-output optimizations lowered audit-inclusive current-path work p50 to
193.4 ms with packed cell grouping, then 177.2 ms with minimum-at range projection.
That stage's [100-frame paced run](../Drishti-2.5/runs/drishti-o001-packed-scatter-paced-seq08-100-20260925/summary.json)
still missed 100/100 deadlines; output age reached 7,985.2 ms. See
[experiment 0010](research/experiments/0010-paced-replay-deadline.md) for the sequential
run conditions and exact-output comparisons.

An ordered point-ID validation path then lowered sequence 08 frame-load p50 from 26.5
to 1.7 ms. New [sequence 08](../Drishti-2.5/runs/drishti-o001-ordered-ids-paced-seq08-100-20260925/summary.json)
and [sequence 00](../Drishti-2.5/runs/drishti-o001-ordered-ids-paced-seq00-100-20260925/summary.json)
100-frame runs matched their original headless outputs exactly. Audited work p50 was
149.0/138.9 ms, and both missed 100/100 deadlines. A snapshot-digest memoryview trial
did not improve the full run and was reverted; see experiment 0010.

After pairwise maximum and finite-coordinate preprocessing changes, fresh
[sequence 08](../Drishti-2.5/runs/drishti-o001-current-laptop-seq08-100-20260925/summary.json)
and [sequence 00](../Drishti-2.5/runs/drishti-o001-current-laptop-seq00-100-20260925/summary.json)
current-laptop 100-frame replays matched the original frame outputs and missed all 200
deadlines. Audited work p50 was 137.0/125.1 ms; scheduled-arrival-to-report-flush age
reached 3891.6/2587.9 ms. The future complete-path release gate remains NOT VERIFIED.
See experiment 0010 for provenance, tails and limits.

Further exact-output distance and semantic-histogram changes yielded new
[sequence 08](../Drishti-2.5/runs/drishti-o001-reductions-histogram-paced-seq08-100-20260925/summary.json)
and [sequence 00](../Drishti-2.5/runs/drishti-o001-reductions-histogram-paced-seq00-100-20260925/summary.json)
100-frame runs. Audited work p50 was 122.3/108.3 ms, with 200/200 deadline misses.
A 50-frame oracle replay matched its prior output. O-001 and the full-path gate remain open.

Passing float32 points directly to the installed Patchwork++ binding preserved all sampled
outputs and gave new [sequence 08](../Drishti-2.5/runs/drishti-o001-native-float32-final-seq08-100-20260925/summary.json)
and [sequence 00](../Drishti-2.5/runs/drishti-o001-native-float32-paced-seq00-100-20260925/summary.json)
audited work p50 values of 120.3/108.4 ms. Every scheduled deadline still missed.

A same-source [100-frame sequence 08 Rerun recording](../Drishti-2.5/runs/drishti-o001-record-view-paced-seq08-100-20260925/summary.json)
had 132.2 ms audited work p50 and 100/100 misses. Median Rerun submission time was
9.93 ms; the verified `.rrd` file was 270.6 MB. That earlier per-scan check included
submission but not a per-frame SDK flush or rendered display. See
[experiment 0012](research/experiments/0012-recorded-view-replay-cost.md). This supplies
cost evidence for the viewer-scope decision without settling that decision.

The diagnostic now supports per-frame Rerun SDK flush in record mode. A fresh
[100-frame run](../Drishti-2.5/runs/drishti-o001-record-flush-paced-seq08-100-20260925/summary.json)
had 142.0 ms audited work p50 and 100/100 misses; median SDK flush was 10.01 ms.
The `.rrd` verified with 100 cell, raw-point and semantic-cell chunks each. This still
does not measure disk `fsync` or displayed output. See experiment 0012.

The extracted dataset's largest scan by file size, sequence 10 frame 206 with 129,392
points, also missed its cold-start headless deadline at
[129.13 ms](../Drishti-2.5/runs/drishti-o001-high-density-seq10-frame206-20260925/summary.json).
It should be retained as a candidate near-130,000-point boundary case; one scan is not
a sustained release test.

A research-only [independent scheduled producer](research/experiments/0013-independent-producer-replay.md)
fed the current geometric worker through a two-frame queue. Its 100-frame sequence 08 run
matched prior outputs, but the queue filled 93 times and all 100 report ages missed the
100 ms deadline. Median output age was 1312.4 ms and median producer load-start lag was
844.3 ms. The producer blocked when full, so it could not keep a 10 Hz source schedule;
the queue is neither live capture nor durable storage. This strengthens the measured
current-path failure without changing the unapproved release proposal.

An exact all-unknown semantic/motion aggregation path then reduced audited work
p50 to [110.71 ms on sequence 08](../Drishti-2.5/runs/drishti-o001-unknown-fastpath-seq08-100-20260925/summary.json)
and [100.04 ms on sequence 00](../Drishti-2.5/runs/drishti-o001-unknown-fastpath-seq00-100-20260925/summary.json).
All 200 paced deadlines still missed, although frame outputs matched prior baselines.
A same-source [separate-producer rerun](../Drishti-2.5/runs/drishti-o001-unknown-fastpath-independent-seq08-100-20260925/summary.json)
missed 100/100 and recorded 89 queue-full events. See
[experiment 0014](research/experiments/0014-unknown-evidence-fastpath.md). No complete
product stage or publication decision is implied by this local optimization.

A same-source [optimized Rerun recording](../Drishti-2.5/runs/drishti-o001-unknown-fastpath-record-flush-seq08-100-20260925/summary.json)
with per-frame SDK flush matched all headless frame outputs, but missed 100/100
deadlines. Audited work p50 was 131.34 ms, including 20.40 ms p50 Rerun
submission plus SDK flush. The RRD verified with 100 geometry, raw-point and
semantic-cell chunks each; it does not prove disk `fsync` or display. See
[experiment 0015](research/experiments/0015-recorded-view-after-fastpath.md).

Reusing a frame's already immutable point and ID arrays when all points are accepted
then lowered headless audited work p50 to
[108.35 ms on sequence 08](../Drishti-2.5/runs/drishti-o001-reuse-frame-arrays-seq08-100-20260925/summary.json)
and [98.93 ms on sequence 00](../Drishti-2.5/runs/drishti-o001-reuse-frame-arrays-seq00-100-20260925/summary.json).
All frame outputs matched their saved baselines, but the strict deadline still
missed 100/100 on 08 and 82/100 on 00. See
[experiment 0016](research/experiments/0016-reuse-accepted-frame-arrays.md).

Reconstructing the earlier process-return boundary from those same paced
reports still yields 100/100 missed 100 ms deadlines on 08 and 67/100 on 00.
This optimistic boundary is only the current geometric result becoming
available in the CLI, not a consumer receipt. See
[experiment 0018](research/experiments/0018-process-return-boundary.md).

A new research-only 10 Hz screen buffered audit writes until after each
100-frame run and measured an immediate current-result sanity check instead.
It still missed [2/100 on sequence 08](../Drishti-2.5/runs/drishti-o001-inprocess-screen-seq08-100-20260925/summary.json)
and [3/100 on sequence 00](../Drishti-2.5/runs/drishti-o001-inprocess-screen-seq00-100-20260925/summary.json).
This narrow check has no versioned complete payload or approved evaluator;
it cannot replace the proposed release receipt. See
[experiment 0019](research/experiments/0019-paced-inprocess-screen.md).
The same diagnostic over 1,000 scans missed
[28/1,000 on 08](../Drishti-2.5/runs/drishti-o001-inprocess-screen-seq08-1000-20260925/summary.json)
and [3/1,000 on 00](../Drishti-2.5/runs/drishti-o001-inprocess-screen-seq00-1000-20260925/summary.json),
including later tails on 08. It still lacks complete output and a real
consumer receipt.

## Immediate next answer

The evaluator-receipt endpoint and evidence-only scope are selected; Rerun remains outside
the deadline. Workload/window/cap approval is explicitly deferred. Next resolve the complete
payload schema, model and evidence-quality gates, bounded audit/failure behavior and host-based
resource limits before requesting full-contract implementation approval. O-001 remains open.
