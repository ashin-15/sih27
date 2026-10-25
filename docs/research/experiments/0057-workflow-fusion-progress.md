# 0057: continued feature-preserving workflow

2026-10-23; RQ-004, T-008. MEASURED RESULT unless labelled otherwise.

## Exact internal changes

CUDA corridor sampling now fuses interpolation, whole-block ownership, interior
tests and cell packing, preserving non-fused float64 operation order. Conflict
queries use sorted packed keys and exact row-range searches for Chebyshev
neighbours. Occupied-key exclusion uses GPU membership lookup. CPU remains the
reference. Temporal ownership uses the existing fixed workspace; no extra
retained device bytes were added. Receipt array validation reuses cached field
metadata and skips only immutable plain scalar recursion.

Visibility fixtures: 39 passed, including real CUDA, radial/square seams,
negative coordinates, duplicate conflicts and beam chunk boundaries. Temporal:
17 passed, including ownership equivalence and immutable full-view parity.
Before motion/envelope additions, the full suite passed 189 tests with four
optional skips; Ruff and strict mypy passed.

`0057-visibility-fusion-screen.py` compared all visibility arrays and summaries
on six real sequence-08 scans with the preserved pre-change CUDA source in
`artifacts/workflow-reference-20261022/`. All matched exactly. Artifact:
`artifacts/visibility-fusion-parity-20261023/`. The subsequent occupied-key
membership optimization has fixture coverage and the 200-frame baseline below;
the first six-frame comparison predates that final membership addition.
`0056-temporal-real-parity.py` also compared every fused output byte on six
real scans with CUDA ownership enabled; all matched CPU. Artifact:
`artifacts/temporal-ownership-parity-20261023/`. These duplicate-work harnesses
are not full-path performance measurements.

## AC-power 200-frame baseline (0059)

User confirmed plugging in power. Windows power status was AC at both run
boundaries (96% to 97% battery). `0059-ac-baseline.py` used the unchanged FP32
model/interpolation, CUDA mapping/candidates/visibility, tracking, temporal
terrain, audit-every 100, view none and the paced receipt checker. Sequence 08,
first 200 frames, pinned checkpoint from 0054. Artifacts:
`artifacts/workflow-ac-baseline-20261023/`, including source snapshot, command,
power/GPU observations, frames, receipts and report. No motion/envelope stage
was enabled in this baseline; they were implemented afterward.

All **200 receipts accepted, 200 deadlines missed**. Cold service 3668.73 ms;
warm load-through-receipt p50/p95/p99/max =
**1555.87 / 1712.02 / 2018.71 / 3527.37 ms**. Maximum scheduled receipt age
299332.41 ms. Warm stage p50: model 201.65, ground 84.85, mapping 105.71,
candidates 179.32, association 8.47, visibility 243.55, temporal 338.83,
receipt 309.40 ms. Independent medians must not be summed.

AC was verified at boundaries; sustained clock/thermal stability and full
process-tree memory are NOT VERIFIED. This is evidence of a failing current
path, not a causal comparison with battery-powered runs or a release pass.

## TensorRT feasibility (0058)

An isolated environment in `artifacts/frnet-engine-env-20261023` contains
ONNX 1.17.0 and TensorRT CUDA-12 10.6.0 plus matching bindings/libraries.
It shares the existing PyTorch 2.14.0+cu126 installation by a local `.pth` file;
production dependencies/defaults were not changed. Native TensorRT parser
initialization works on this host. Source checkpoint hash is verified first.

`0058-frnet-export-screen.py` used synthetic geometry and the pinned weights.
Full legacy ONNX export failed on indexed accumulation with duplicate indices
in `_scatter_mean`. The convolutional stem exported, passed ONNX checking, and
parsed in TensorRT with no parser errors. No engine execution, dynamic-shape
agreement or full-model speedup was established. Reports and failed export log:
`artifacts/frnet-export-screen-20261023/` and adjacent `.log`.

LITERATURE-BACKED CLAIM: [Autoware's plugin documentation](https://autowarefoundation.github.io/autoware_universe/main/perception/autoware_tensorrt_plugins/)
describes custom unique and scatter support, confirming that its integration
cannot be assumed to be a direct export of this runtime. The
[model card](https://huggingface.co/AutowareFoundation/lidar_frnet/blob/main/README.md)
describes 27 Autoware classes; its weights are not a replacement for the pinned
SemanticKITTI model. [TensorRT's compatibility matrix](https://docs.nvidia.com/deeplearning/tensorrt/10.x.x/getting-started/support-matrix.html)
also makes engine portability conditional on platform/version/hardware.

Next: exported subgraph/custom reduction adapter, bounded GPU fusion and
validation; keep original-point mapping and quality gates. Under 100 ms is
still not met. W0 has a measured AC baseline; W1/W2/W3/W4 remain IN PROGRESS.
