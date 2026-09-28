# Drishti-2.5 perception acceptance contract

Status: T-002 slice approved 2026-09-26; T-003 semantic CPU implementation
approved 2026-09-27. T-003 quality acceptance and full release remain open.
The product owner approved the O-001 checklist and staged implementation. The CUDA-backed
replay gate still requires an identified NVIDIA host, pinned checkpoint, numeric quality and
resource thresholds, and final evidence. AC-008 is NOT VERIFIED.

## Release boundaries

The first CUDA-backed release uses evidence-only dataset replay on an identified NVIDIA host; the current Intel laptop remains a CPU reference. Live input and planner-facing or navigation-safe output are deferred beyond this release. Publication is the same-process evaluator's receipt for the complete versioned immutable product result. Persist receipts and audit evidence; full-payload disk persistence is not part of the 100 ms endpoint. A release cannot claim learned perception, tracking, free space or real-time behavior because the current geometric/oracle demo passes. Every blocking criterion needs a saved command, configuration, dataset split, checkpoint hash and result artifact. Evidence-only scope does not waive false-free, unknown/stale or other evidence-quality criteria.

## Criteria

| ID | FR | Scenario and observable result | Evidence | Blocking |
| --- | --- | --- | --- | --- |
| AC-001 | 001, 009 | Replay held-out scans with labels inaccessible to the inference path. Output one aligned semantic ID/confidence per accepted original point; unknown is 0, not car. Report class IoU, mIoU by range and unknown coverage against frozen thresholds. | Point-order fixtures, label access guard, official evaluation output, manifest. | Yes |
| AC-002 | 002 | Replay wall, pole, curb, vehicle, pedestrian, overhang and partial-view fixtures. Detect instances with bounds and class/unknown; do not infer solid occupancy from a sparse vertical envelope. Meet frozen recall/false-positive limits by size and range. | Fixture traces, reviewed detections, metrics. | Yes |
| AC-003 | 003 | Revisit static cells under pose change, frame gap and repeated scan. Fuse evidence without duplicate growth, preserve nonoverlap at resolution seams, distinguish stale/unknown and reset across sequences. | State diffs, memory bounds, replay tests. | Yes |
| AC-004 | 004 | Follow multiple objects through crossing, short occlusion, disappearance and reappearance. Track IDs obey frozen lifecycle; report ID switches, fragmentation and false tracks. | Sequence traces and tracking metrics. | Yes |
| AC-005 | 005 | Ego vehicle moves past a static wall and a moving object. Wall speed remains within frozen tolerance; moving object receives velocity/uncertainty only with sufficient evidence; first frame stays unknown. | Motion fixtures, moving IoU and velocity-error report. | Yes |
| AC-006 | 006, 010 | Rays end before, at and beyond candidate cells; include no return, out-of-FOV and occluded cases. Only supported traversed cells become observed-free. No invalid case becomes free. | Ray fixtures and false-free metric on held-out scans. | Yes |
| AC-007 | 007 | Run a complete sequence and inspect manifest/frame/summary artifacts. Every frame records model, pose and evidence provenance, stage timings, drops, state age and memory; failure is reported, never silently omitted. | Schema validation and saved run artifacts. | Yes |
| AC-008 | 008 | On the identified NVIDIA CUDA release host, replay approved representative density and duration at the frozen input cadence with model, fusion and audit enabled. Rerun recording and display are outside the 100 ms gate and measured separately. Every scan, including the first, receives a same-process evaluator acknowledgement after validation of its complete versioned immutable output within 100 ms of scheduled arrival; zero scans miss in the accepted window. A digest-only JSONL record or visualization projection is insufficient. Meet frozen throughput, memory and drop thresholds without an unbounded backlog. | Reproducible paced-replay logs, per-scan arrival/complete-output handoff timing, stage/queue/transfer timing, output-age distribution, CPU/GPU resource trends and physical host inventory. | Yes |
| AC-009 | 009 | Compare geometric, learned and oracle modes using the same accepted points and map path. Oracle labels never enter learned prediction or tracking. Validation and final evaluation splits remain disjoint. | Split manifest, access tests, metric report. | Yes |
| AC-010 | 010 | Viewer and machine output distinguish occupied, observed-free, unknown, stale and ambiguous cells and show track/motion provenance. Unknown never appears drivable. | Output schema tests and real viewer recording inspection. | Yes |
| AC-011 | 011 | Deferred beyond the first release: if live input is later approved, feed timestamped scans with calibration and pose quality; invalid or missing timing degrades explicitly. Deskew status is accurate. | Live-source fixtures and target sensor run for that later scope. | Deferred |
| AC-012 | 001 to 011 | Existing tests, lint, format, type check and package build pass; a complete-path regression replay finishes from an installed wheel. | Commands, logs and wheel replay artifact. | Yes |
| AC-013 | 007, 008, 009 | T-002 CPU slice: the actual `MappingEngine.process` result becomes a version-1 immutable diagnostic `ProductFrameResult`. A same-process evaluator validates the array payload, source/pose/point alignment, provenance, cell ownership and conservative proof rules before a versioned receipt. Invalid input yields a rejection receipt without a digest or state advance. Canonical digest repeats for identical field values. CLI replay saves accepted diagnostic receipts and explicitly marks them as non-release. | Unit invalid/boundary fixtures, CLI same-path replay, receipt/artifact inspection, lint/types/build. | Yes for T-002 only |
| AC-014 | 001, 007, 009 | T-003 CPU slice: a hash-pinned FRNet worker receives accepted sensor points without oracle labels, returns one mapped class and uncalibrated score per accepted original ID, and the shared mapping path yields a schema-2 semantic-only receipt. Invalid hash, source revision, intensity, count, class and score fail explicitly. Prediction files preserve full input order and unknown rejected points. Official full sequence 08 scoring and supplemental class/range/unknown reports must meet frozen D-005 numeric gates before T-003 is DONE. | Source and installed-wheel real replay, access/alignment/error fixtures, official evaluator output, range report, runtime manifest, lint/types/build. | Yes for T-003; implementation verified, quality gate pending |

## Required threshold decisions

Freeze numeric targets for semantic classes and ranges, obstacle classes and sizes, motion/track quality, false-free rate, map freshness and capacity after the pinned baseline. The approved future release workload is complete sequences 08 and 00 at 10 Hz plus the separate sequence 10 frame 206 cold-start fixture, with explicit rejection above 130,000 points. Identify and inventory the NVIDIA release host; freeze bounded audit behavior and CPU/GPU memory and disk ceilings. Rerun is excluded from the 100 ms timing and needs a separate resource/quality check. The 100 ms per-scan deadline, zero-miss policy, same-process evaluator receipt endpoint and evidence-only output scope are selected. Passing AC-013 cannot satisfy AC-001 to AC-012 or the full release contract.

The [O-001 contract proposal](../../../../docs/o-001-contract-proposal.md) supplies the selected
window accounting and a metric/threshold worksheet. T-002 freezes version-1 schema and
validation in the technical design. Quality and host resource limits remain TBD; no complete-path
acceptance run exists. T-002 receipts are diagnostic and cannot be counted in AC-008's denominator.
T-003 schema-2 semantic-only receipts also cannot be counted as complete AC-008
results. The one-scan official evaluator check was format/metric validation.
E-051 now records the full sequence 08 semantic baseline, but D-005 numeric
gates have not been approved and the split engine does not establish AC-008.
The [D-005 semantic threshold sheet v0.1](../../../../docs/d-005-semantic-thresholds-v0.1.md)
is a draft proposal for AC-001/014 metrics, support and independent final
evaluation; it is not a frozen pass rule.
