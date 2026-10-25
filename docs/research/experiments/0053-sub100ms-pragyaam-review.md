# Experiment 0053: a concrete route toward sub-100 ms frames

Date: 2026-10-22. RQ-004 / R-SYSTEM, with RQ-001 and RQ-003;
T-003/T-006/T-008. Source review and experiment proposal, not a new benchmark.
The user requested research, including Pragyaam-SIH26053. Runtime is unchanged.

## Conclusion and starting point

HYPOTHESIS: a device-resident pipeline with fused mapping/visibility/temporal
kernels, optimized online semantics and a compiled result evaluator is the
strongest route. Another isolated Python optimization cannot close the gap.
Feasibility on the RTX 4050 remains UNKNOWN; no measured speedup is assigned
to this proposed architecture.

MEASURED RESULT from [0051](0051-exact-path-screen.md): six current-path source
frames, RTX 4050 Laptop, driver 561.00, learned CUDA FP32, tracking,
visibility and diagnostic temporal enabled, no viewer. All six receipts were
accepted and all six deadlines missed. Warm load-through-receipt p50 was
1,383.73 ms. That is roughly a 14-fold gap even before requiring tail margin.
The installed-wheel run was much slower under uncontrolled load/power; it is
not evidence of a packaging penalty. Independent stage medians below must not
be added to reconstruct a total.

| Stage | Warm p50, ms | Source hotspot / implication |
| --- | ---: | --- |
| Visibility | 314.27 | `visibility.py:_corridor_pairs/compute`: sampled corridors, temporary arrays, sort/reduce, chunk downloads and host conflict/proof work |
| Temporal fusion and view | 295.77 | `temporal.py:_fuse_points/_view`: CPU arrays and rebuilding derived output over observed owned cells |
| Receipt after processing | 210.39 | `frames.jsonl:receipt_ms`: construction, evaluator and accepted handoff; includes work beyond hashing |
| FRNet | 190.18 | `frnet_model.py:predict`: interpolation, dynamic grouping, network, class/confidence host readback |
| Candidate detection | 90.28 | Requires its own optimization; cannot disappear behind a mapping-only number |
| Mapping | 84.97 | `cuda_backend.py` still downloads intermediates and finishes several reductions on CPU |
| Ground | 58.96 | CPU Patchwork++; state and GIL behavior constrain overlap |
| Projection / preprocessing / association | 13.06 / 17.55 / 4.61 | Remaining costs also need budget |

Receipt p50 was recomputed from frames 1-5 in the saved JSONL. The summary's
1,431.11 ms audit-inclusive p50 uses all six frames, including cold frame zero;
it is a different metric. No new inference run was made for this review.

## What the reference actually supports

Pinned source: [Pragyaam commit f3a59c23](https://github.com/Stxtics03/Pragyaam-SIH26053/tree/f3a59c23c4dc1d0f19b9389e34cbff4815467935).
GitHub web/search caches returned different README generations. The GitHub
API supplied the commit and exact files, saved read-only for this review at
`artifacts/research-pragyaam-20261022/`; `source-manifest.json` records hashes.
The source was inspected, not executed. External instructions were treated
as reference content. The downloaded MIT license is retained; no code was copied
into Drishti.

SOURCE-REPORTED RESULT: the [GPU frame-loop report](https://github.com/Stxtics03/Pragyaam-SIH26053/blob/f3a59c23c4dc1d0f19b9389e34cbff4815467935/docs/gpu-lane/08-GPU-FRAME-LOOP.md)
reports 22.3 ms p50 / 26.7 ms p99 for its mapping path, which uses dataset
semantic/motion labels in that experiment. The newer
[19 September research entry](https://github.com/Stxtics03/Pragyaam-SIH26053/blob/f3a59c23c4dc1d0f19b9389e34cbff4815467935/docs/research-log.md#2026-09-19-evening--shrestha)
reports 71.8 ms p50 / 79.5 ms p99 with CUDA mapping and online FP16 FRNet.
The pinned `iter_pipeline(..., semantic_source="frnet", semantic_precision="fp16")`
and `DevicePerception.launch(..., semantic_pred=...)` implement that online
path. It would be wrong to describe every current Pragyaam run as oracle semantics.

Limits of transferring those figures:

- The reference host reports identify an RTX 5050 Laptop with about 8 GB,
  Linux and a different driver/runtime. Drishti uses an RTX 4050/6 GB on Windows.
- The 79.5 ms figure is a source-reported result; a matching full per-frame raw
  timing series, exact command and zero-miss maximum were not established in
  the reviewed files. Do not transfer it as a reproduced benchmark.
- `scripts/timing_table.py` currently calls the default semantic source and
  discards its first frame. That command alone does not reproduce online FP16
  inference or Drishti's paced first-scan-inclusive receipt boundary.
- `src/gpu/device.py` retains motion from the dataset label word even with
  learned semantics. Its lazy host map mirror is paid only when read. This
  is different from producing and validating Drishti's complete immutable result.
- Its occupied-cell range-image cleanup is not the same computation as
  Drishti's ground-terminated beam proofs, support counts and free-cell output.
- The research log corrects a nondeterministic interpolation write and notes
  that earlier semantic/FP16 scores were measured with it. Its 65.2% mIoU uses
  a short-run present-class denominator, not Drishti's official full 19-class
  full-sequence score. Neither accuracy nor exact parity transfers automatically.
- Earlier contention data reports 130.30 ms p99 for map plus FP32 inference,
  and map-only maximum 198.02 ms despite 27.80 ms p99. A p99 below 100 ms does
  not prove every scheduled frame meets 100 ms.

The useful implementation ideas are in
[`device.py`](https://github.com/Stxtics03/Pragyaam-SIH26053/blob/f3a59c23c4dc1d0f19b9389e34cbff4815467935/src/gpu/device.py),
[`cuda_kernels.py`](https://github.com/Stxtics03/Pragyaam-SIH26053/blob/f3a59c23c4dc1d0f19b9389e34cbff4815467935/src/gpu/cuda_kernels.py)
and [`allocators.py`](https://github.com/Stxtics03/Pragyaam-SIH26053/blob/f3a59c23c4dc1d0f19b9389e34cbff4815467935/src/gpu/allocators.py):
persistent structure-of-arrays storage, bounded scratch, fused ownership and
fusion kernels, strip-clearing of rolling windows and explicit synchronization.
Drishti already has bounded temporal windows and native tensor scatter
reductions. Recreating those features alone provides no new saving.

## Implementation sequence and falsifiable experiments

### 1. Establish the actual critical path

Record the current source revision, AC-power mode, thermal/throttle state,
CPU/GPU clocks, driver, RAM pressure, GPU used/reserved memory and WDDM mode.
Use NVTX ranges and Nsight Systems for model, copies, visibility substeps,
temporal view and evaluator. CUDA event timing explains device work; a host
monotonic clock through accepted receipt decides latency. Do a 200-frame
controlled baseline and dense/cold screens, then retain the complete release
windows for acceptance. Profile and final timing runs must be separate.
[NVIDIA benchmarking guidance](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/benchmarking.html)
supports this measurement method, not a speed prediction.

Exit evidence: matched inputs, an explained critical path and stable repeated
measurements. Resolve the source/wheel slowdown before attributing improvements
to code. No driver/power/system settings were changed by this research.

### 2. Make GPU residency the shared execution path

Introduce an internal bounded frame workspace carrying points, original IDs,
semantics, owner keys, reductions and proofs across stages. Preserve public
contracts initially. Keep intermediates on-device; download complete required
columns in a bounded final handoff, not between each stage. Preallocate scratch
from explicit point/cell/proof capacities, with classified overflow errors.

Share PyTorch/CuPy device arrays through DLPack with stream events and owned
lifetimes. [CuPy's official interoperability guide](https://docs.cupy.dev/en/stable/user_guide/interoperability.html)
documents this mechanism. It avoids a copy, not the need for synchronization
or immutable ownership. Retain two output buffers or an explicit lease until
the consumer releases each result; a mutable view overwritten next frame is
not equivalent to the current output.

Fuse cell ownership, integer sufficient-statistic accumulation and derived
flags where the dependency graph permits. Preserve int64 overflow bounds,
rounding/ties, class IDs and all projection-losing points. Native/CUDA kernels
can stay behind Python orchestration; a full C++ application rewrite is not
the first requirement. [CUDA best practices](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html)
supports minimizing transfers and allocation, without promising a local factor.

Exit evidence: unchanged geometry/evidence arrays and rejection behavior on
adversarial fixtures and ordered real scans, bounded memory, copy/launch count
and critical-path improvement. This is a larger internal change, not `np` to
`cp` replacement alone.

### 3. Replace visibility and temporal hot loops

First visibility candidate: a fused CUDA sampler preserving the existing
sampling phase, strict interior epsilon, ownership and conservative conflict
rules. Emit bounded `(cell, beam)` keys and reduce distinct beam support/minimum
proof ID on-device; avoid repeated per-chunk host merge/re-upload. Profile the
remaining host conflict and proof construction too. Keeping the same samples
gives an exact-output route. DDA cell traversal or Pragyaam's range-image-only
cleanup changes the proof set and belongs in a separately versioned experiment.

Temporal candidate: port fusion and view construction to persistent device
arrays. Dirty-cell work includes changed cells AND their neighbours, expired
timestamps, moved ownership boundaries and reused slots. Otherwise unchanged
cells can retain stale curb/free/terrain flags. Keep a bounded full-grid GPU
scan as a simpler baseline; incremental bookkeeping is not automatically faster.
Full required output still has to be materialized/validated by receipt time.

Exit evidence: exact support counts/IDs/conflicts for visibility, complete
temporal array parity over turns and long sequences, correct expiry/slot reuse,
and measured tails. These two measured stages together are roughly 610 ms in
stage-median scale, so they warrant priority alongside the model.

### 4. Optimize the complete FRNet adapter

Run a controlled 2x2 screen using existing flags: FP32/FP16 and reference/GPU
interpolation, through the same complete path. Drishti already uses
`scatter_reduce`, `index_add_` and autocast; Pragyaam's large loop-to-scatter
speedup is not available again. Experiment 0052 rejected a GPU packed-grouping
candidate, so do not simply reinstate it. FP16/GPU interpolation are candidates
whose class/range/confidence quality must be measured, not exact-byte upgrades.

The next substantial candidate is an exported FRNet network plus explicit
native/CUDA preprocessing. [Autoware's FRNet implementation](https://github.com/autowarefoundation/autoware_universe/blob/main/perception/autoware_lidar_frnet/lib/lidar_frnet.cpp)
is a concrete reference: it computes interpolation/unique coordinates/inverse
mapping before TensorRT and supplies `points`, `coors`, `voxel_coors` and
`inverse_map`, with checked dynamic profiles. Its
[documentation](https://autowarefoundation.github.io/autoware_universe/main/perception/autoware_lidar_frnet/)
describes FP16/FP32 and separate preprocessing/inference/postprocessing metrics.
This is evidence that the integration pattern exists, not that its weights,
sensor defaults or class map can replace our pinned adapter.

Profile limits must cover interpolated points as well as the 130,000 raw-point
cap. Verify all operator/plugin support, checkpoint coverage, exact projection
rules and output alignment; report all compilation/fallbacks. Check installed
driver/CUDA/TensorRT compatibility before selecting a version. No unverified
claim that the latest TensorRT runs on driver 561.00 is made.

Try CUDA Graphs only for stable, capturable regions after tracing launch
overhead; data-dependent unique counts and host reads complicate full capture.
[NVIDIA's optimization guide](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/optimization.html)
explains capture constraints. Batch size stays one. If the optimized adapter
cannot meet its budget, evaluate a smaller model with the original-point
alignment and independent quality gates; do not silently infer fewer frames.

### 5. Budget the ground stage and evaluator explicitly

Ground is still about 59 ms locally. Check native release build, input copies,
thread/power behavior and matching Patchwork++ configuration before algorithm
changes. Preserve one stateful segmenter per sequence. Once dependencies allow,
enqueue model/device work before CPU ground work and join only at consumption.
The installed binding's GIL behavior is known to block naive Python threading;
use an audited GIL-releasing native call or measure shared-memory process costs.
Overlap must reduce same-frame receipt age; pipelines/queues alone cannot do it.

Compile/vectorize exhaustive evaluator checks and the existing canonical
digest stream before changing the schema. The isolated optimized digest still
cost 56.16 ms p50 in 0051. Avoid per-beam Python object construction where an
internal native representation can preserve exact public bytes. If that fails
the budget, propose a versioned contiguous proof/result schema with documented
binary digest encoding. That schema change needs a concrete reviewed contract;
hashing only a summary, skipping validation or deferring required fields does
not meet the existing deadline. Deep-audit frames must also meet the gate.

## Proposed engineering budget, not predicted performance

This is a deliberately demanding feasibility target, to be replaced by
measurements. It is not a sum of measured medians or proof of a tail bound.

| Serial budget component | Proposed limit |
| --- | ---: |
| Input, validation, transfer and projection | 5 ms |
| FRNet including its preprocessing/output | 40 ms |
| Ground | 15 ms |
| Map aggregation, candidates and association | 8 ms |
| Visibility evidence | 10 ms |
| Temporal update and required fused output | 7 ms |
| Final handoff, validation and digest | 5 ms |
| Total work / remaining scheduling margin | 90 ms / 10 ms |

Same-frame CPU/GPU overlap may create further margin but is not assumed in
this sum. Any future required motion/foveation work must fit within the ledger
or force its revision. If controlled stage measurements cannot fit, revisit
the model, exact algorithm/layout or target hardware; more queues do not close
the budget. A 6 GB GPU allocation/pool/scratch bound must be measured with all
stages resident, not inferred from the map's logical bytes.

## What not to use as the shortcut

- Inferring every N frames: the reference's own
  [rate experiment](https://github.com/Stxtics03/Pragyaam-SIH26053/blob/f3a59c23c4dc1d0f19b9389e34cbff4815467935/docs/gpu-lane/laptop/semantics-rate.json)
  reports lower median for N=3/5 but p99 still around 146 ms and lower accuracy.
  Its script times perception, not `MapEngine.step`; it is not a full-map result.
- Swapping ground-truth semantics/motion, dropping points, hiding host readback,
  removing temporal/visibility, or quoting model FPS as complete-frame latency.
- Treating FP16, foveation or a faster GPU as an automatic solution. Each has
  quality, implementation or bottleneck constraints to measure.
- Calling p99 <100 ms a zero-miss pass. Use scheduled arrival through complete
  receipt; preserve every scan and report first-frame, max, misses and backlog.

## Acceptance and task impact

Research and current-contract exact-output screens can proceed now. Precision,
model, proof-rule or public-schema changes require their specific reviewed
acceptance contract before adoption, not before researching their feasibility.
The selected complete release test is full sequences 08/00 plus sequence 10
frame 206, immutable complete receipts, zero dropped/late/rejected valid scans,
and final quality/resource evidence. Disjoint warmup must reset sequence state;
the first selected scan still counts. Record p50/p95/p99/max, RSS/VRAM and flags.

Recommended first implementation slice: controlled baseline plus shared GPU
workspace and exact fused visibility/temporal prototype; run the existing FP16
screen alongside that work, then use the TensorRT adapter if model cost still
dominates. Keep the evaluator reduction in the same performance plan.
T-008/O-001/O-006 remain IN PROGRESS; AC-008 is not met.
