# Experiment 0043: 100 ms feasibility research and experiment order

Date: 2026-10-13. Question: RQ-004; module: R-SYSTEM; tasks: T-008, T-001.
Type: source and local-evidence review. No new runtime benchmark was run.

## Boundary and measured starting point

The selected first-release target is evidence-only SemanticKITTI replay on the
RTX 4050 laptop: a complete immutable versioned result accepted by the
same-process evaluator within 100 ms of each scheduled 10 Hz arrival, with zero
misses. The first selected scan counts. Rerun display and full-payload disk
persistence have separate measurements. The complete fused result schema and
D-005 numeric quality/resource gates remain draft. Thus no current receipt is
an AC-008 pass.

MEASURED RESULT: [experiment 0042](0042-visibility-chunk-screen.md) records six
unpaced real sequence-08 learned CUDA scans with current schema-5 receipts and
diagnostic CPU temporal fusion. For warm frames 1-5, processing p50 was
1,278.6 ms; visibility p50 449.2 ms, model 201.5 ms, temporal 308.4 ms,
detector 91.2 ms, mapping 83.8 ms and ground 64.7 ms. Current evaluator
validation was 547-703 ms per warm frame (about 625 ms median). These are
stage distributions, not additive per-frame medians. The current typical
processing-plus-validation scale is around 1.9 s, roughly 19 times the 100 ms
target, but the run was short, unpaced and lacked the frozen complete result.
Every measured current frame missed its configured audit-inclusive budget.
Several serial stages individually exceed 100 ms; overlap or queueing alone
cannot rescue their per-frame receipt age.

An instrumented two-frame cProfile is ranking evidence only: Python cell and
visibility validation plus canonical digest dominate the current evaluator;
visibility repeatedly samples corridors, allocates/merges chunks and crosses
the device boundary; temporal builds a full host view. The profile is not a
release timing result. Peak VRAM, memory demotion and controlled tails remain
UNKNOWN.

## Primary-source findings and candidate experiments

The sources below were inspected 2026-10-13. They describe mechanisms and
measurement methods, not speedups for Drishti.

| Candidate, priority | Mechanism and source | Falsifiable next experiment and exit evidence |
| --- | --- | --- |
| P0: controlled critical-path trace | [NVIDIA TensorRT best practices](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/best-practices.html) recommends stable host/GPU measurement and Nsight profiling. | Record AC power, driver, clocks/throttle, WDDM queue, VRAM/RSS, scan density, synchronized CPU/GPU stage and transfer times, evaluator time, arrival-to-receipt age, p50/p95/p99/max and misses on a representative window. Warm on disjoint input, reset sequence state, then count first selected scan. Profile output must explain the large visibility/evaluator costs before redesign. |
| P1: FRNet inference | [TensorRT optimization](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/best-practices.html) can fuse supported operations; [dynamic-shape profiles](https://docs.nvidia.com/deeplearning/tensorrt/latest/inference-library/work-with-dynamic-shapes.html) cover variable point/image sizes. [ONNX Runtime I/O binding](https://onnxruntime.ai/docs/performance/tune-performance/iobinding.html) avoids implicit CPU/device copies. | First screen existing fp16 and GPU interpolation, then export pinned FRNet to ONNX and test TensorRT or ORT only if operators/driver support it. Report end-to-end model latency including preprocessing and output alignment, profile coverage, peak memory and held-out per-class/range quality. Reject any engine that changes IDs/order, unknown handling or approved quality. The local fp16 sequence-08 screen lost 0.00055 mIoU while reducing model time 18%; this does not establish D-005 acceptance. |
| P1: visibility proof | [CUDA transfer guidance](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html) recommends device-resident intermediates and batching transfers. | Profile corridor sampling, key packing, allocation, reduction and D2H/H2D by scan. Prototype a fused/device-resident traversal and compact proof aggregation with one bounded handoff. Compare exact output arrays against CPU/reference fixtures across beam/chunk boundaries, then score false-free and occlusion on held-out data. Changing ray discretization or fewer beams is a changed proof rule and needs an explicit contract/quality review. |
| P1: temporal/map and candidates | Same CUDA transfer guidance; current local profile ranks full-view construction and per-level fusion. | Prototype dirty-cell updates and contiguous bounded result columns, then native/device aggregation and candidate grouping. Preserve every accepted point, ownership, deterministic eviction, unknown/stale state and all complete-output fields. Compare full sequence digests, candidate/terrain quality, memory and tails. Reducing published cells is not an implicit optimization. |
| P1: evaluator and handoff | Local cProfile ranks Python row recursion, checks and digest. | Freeze the complete result layout first. Compare vectorized/compiled exhaustive column checks and a single canonical digest pass against the reference validator, including injected corruptions and deep audits. Measure validation and acceptance separately from audit persistence. Never weaken safety-critical checks merely to fit time. |
| P2: launch overhead and overlap | [CUDA Graphs](https://docs.nvidia.com/deeplearning/tensorrt-rtx/latest/inference-library/work-with-cuda-graphs.html) can reduce repeated launch overhead for capturable work; [CUDA transfer guidance](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html) describes pinned asynchronous copies. | Attempt capture only after tracing shows launch-bound GPU kernels and shape/state constraints fit. Test graph breaks, memory and exact parity. Test independent CPU/GPU overlap only after dependency and GIL analysis; installed Patchwork++ held the GIL in E-046. Re-measure arrival-to-receipt, because throughput gains do not prove latency. |

Before an engine screen, check the installed Windows driver, CUDA and TensorRT
version compatibility and whether the FRNet export covers every operator.
NVIDIA's current documentation describes options, not a verified compatible
binary for this pinned environment. CUDA Graph capture also skips at least
its first inference in the cited RTX implementation, so first-selected-scan
latency requires explicit treatment within the warmup/reset protocol.

DESIGN HYPOTHESIS: the model, visibility, map/candidate, temporal and evaluator
need coordinated large reductions to leave scheduling headroom below 100 ms.
No source supplies a credible Drishti speedup factor. Published FRNet model FPS,
`trtexec` engine time, CUDA event time or a single-stage microbenchmark is not
the same as this receipt gate. Any lower-compute model, precision change, ray
rule or output compaction must pass D-005 quality and complete-schema checks.

## Go/no-go sequence and SIH26053 cross-check

1. Freeze the result/workload and D-005 gates, then establish a controlled trace
   and a stage-tail ledger. Reject a plan that only reduces mean time or drops
   scheduled scans. Record power and VRAM demotion before attributing stalls.
2. Run isolated model, visibility and evaluator prototypes against the current
   reference with exact input/output accounting. Run temporal/map candidates
   with long ordered state and fault/eviction fixtures. Keep rejected variants.
3. Integrate only variants whose combined measured critical path has margin;
   run increasing paced 10 Hz windows, both complete sequences 08/00 and the
   sequence-10 frame-206 density boundary. Count first-frame and maximum age,
   misses, drops, invalid receipts, backlog, RSS and VRAM. Reopen D-001 if the
   selected hardware demonstrably cannot meet the frozen gate.

SIH26053 requires low latency and accuracy across distance, variable-resolution
2.5D terrain and obstacle evidence, high-detail near field, dashboard and a
measured memory comparison. The above candidates must preserve point alignment,
near-field resolution, thin/overhang obstacle evidence, conservative free cells,
terrain/track semantics and the independent quality scores. A faster semantic
engine or compact proof alone does not satisfy these other requirements. Rerun
display FPS and fair process/device memory comparison remain separate release
evidence. See the [roadmap cross-check](../../production-roadmap.md).

Conclusion: feasibility on the RTX 4050 remains UNKNOWN for the frozen complete
result; the current implementation is far above the budget. T-008 stays IN
PROGRESS, O-001/O-006 stay open. This memo authorizes measurement and candidate
screens only; it does not approve a schema, model or proof-rule change.
