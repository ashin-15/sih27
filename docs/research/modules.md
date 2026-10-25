# Research modules tied to development

2026-10-22 R-SYSTEM/RQ-004 research follow-up: [review 0053](experiments/0053-sub100ms-pragyaam-review.md)
pins Pragyaam source and distinguishes its mapping/online-model reports from
Drishti's receipt gate. Priorities are shared GPU residency, fused exact
visibility/temporal work, controlled FP16 then a TensorRT adapter, and compiled
receipt checks. A proposed 90 ms work budget is a hypothesis, not a benchmark.

2026-10-22 R-SYSTEM/RQ-004: [experiment 0051](experiments/0051-exact-path-screen.md)
adds exact receipt/visibility improvements, learned pacing and source/wheel
evidence; [experiment 0052](experiments/0052-frnet-repeatability-screen.md)
retains CPU grouping and rejects GPU grouping. All twelve paced scan deadlines
failed. The complete-result, final-quality and controlled resource gates remain
open; next work must address the dominant stage costs without dropping evidence.

Each module produces a short decision memo: question, primary sources, candidate options,
evidence with conditions, contradictions, conclusion (or UNKNOWN), and the concrete task affected.
Log new topics and failed candidates in `research-log.md`. A module does not approve a product
choice; the frozen product contract and accepted ADRs control implementation.

| Module | Questions and task link | Current state | Required output |
| --- | --- | --- | --- |
| R-MODEL: learned semantics and object evidence | RQ-001/RQ-006; T-002 to T-004 | The approved semantic-only FRNet CPU adapter and reproducible inference workflow run in Drishti. E-050 verifies source/wheel one-scan compatibility; E-051 measures all 4,071 held-out sequence 08 scans at 0.675469 official mIoU with range metrics; E-052 confirms fresh prediction parity and CPU cost. Decision 0005 approves a bounded CPU obstacle candidate detector; E-055 measures source/wheel parity, the 4,071-scan official panoptic baseline and separate class/range/size diagnostic. AC-015 is accepted with caveats. Exact public-byte identity, separate FRNet weight terms, independent final semantic/range evidence and independent wider-obstacle labels remain unverified; `deeplearningpipeline.md` remains a broader proposal. | Apply the frozen D-005 semantic/traffic gates without tuning on final data, resolve weight provenance, measure release-path cost and obtain independent thin/curb/overhang detection evidence before full AC-002 acceptance. |
| R-TIME: tracks, motion, and visibility | RQ-002/RQ-003; T-004 to T-006 | Snapshots are single-frame. Approved bounded association emits schema-4 receipts; experiment 0030 records 69 ID switches and 39 fragmentations in a 200-frame development baseline. Current-scan schema-5 visibility is implemented, with 0.549% static false-free in the sequence-08 SSC report (experiment 0035). A diagnostic fused layer adds stale/free state under decision 0011, and schema-6 fused payload requirements are frozen under decision 0013. Metric velocity, independent tracking/terrain evidence and numeric false-free acceptance remain open as blocking `not-verified` rows. | Use independent final association, motion, terrain and false-free scoring under the frozen D-005 policy; keep evidence-only output distinct from navigation-safe proof. |
| R-SYSTEM: evaluation and deadline | RQ-004; T-007/T-008 | The RTX 4050 laptop is the selected host. Experiments 0041/0042 measure a short current learned CUDA path far above 100 ms, including visibility and current evaluator bottlenecks. Experiment 0043 ranks source-backed feasibility screens. Experiment 0044 measures rising diagnostic temporal full-view cost on 30 synthetic frames; a small exact neighbour candidate was rejected. Decision 0013 freezes the complete result, D-005/resource bundle and paced replay protocol; complete-producer integration and release evidence remain open. | Trace the critical path, screen exact-output model/visibility/map/temporal/evaluator candidates, then run the frozen paced full-path p50/p95/p99/max, deadline misses, drops, RSS/VRAM, map allocation, audit and release judgment. |
| R-INGRESS: durable acquisition and scheduling | RQ-005; T-014/T-008 | Short SQLite/MCAP recorders passed 10 Hz replay. A new LMDB/SQLite/custom-log comparison and LMDB injected faults are in experiment 0009; current processing still falls behind and no live source or scheduler exists. | Source ack/retry and failure contract, sustained durable writes and reader/map limits, bounded ordered scheduler, backlog/disk and output-age gates, recovery evidence. See experiments 0008 and 0009. |

For each candidate, write whether the evidence changes a decision, confirms it, or is irrelevant
to it. Record metric conditions such as hardware, sequence, point count, warmup, and class map.
Never copy a benchmark number from the supplied reference archive into a Drishti claim.
