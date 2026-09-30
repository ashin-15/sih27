# Experiment 0032: CUDA backend on an RTX 4050 and CUDA learned-stage parity

Date: 2026-09-29. Questions: RQ-004 (feasibility) and the O-001/T-008 CUDA path.
Scope: first execution of the optional CUDA backend on real NVIDIA hardware, and
CPU-reference parity for the new CUDA candidate and visibility stages. No
SemanticKITTI data, FRNet model or voxel labels were available; nothing here is
a real-data, release or AC-008 result.

## Host and environment

FACT: Windows 11 laptop, NVIDIA GeForce RTX 4050 Laptop GPU (6,141 MiB, driver
561.00, `nvidia-smi` CUDA 12.6), Intel graphics also present. `uv` 0.12.20,
CPython 3.12.14. New optional extra `cuda = ["cupy-cuda12x[ctk]>=14,<15"]`
resolved CuPy 14.2.0 with pip-packaged CUDA 12.9 runtime libraries (no system
CUDA Toolkit). Smart App Control is On; it blocked several native modules on first
load and allowed them on later loads. No security setting was changed.

## Defects found by the first GPU run

The GPU-free array-API test (NumPy standing in for CuPy) had passed; all three
real-device tests failed until these were fixed:

1. `cp.lexsort` requires one stacked key array; it rejected a tuple.
2. CuPy comparisons rejected Python `IntEnum` scalars (`GroundClass`, `Motion`).
3. MEASURED RESULT: `cp.minimum.at` on float64 returned values rounded to about
   float32 precision (for example 5.30029267 stored as 5.30029249). The exact
   nearest-range test then matched no point, so every occupied range-image
   pixel lost its owner. Projection now selects winners by an exact lexsort on
   (pixel, range, point ID), the CPU tie rule. Int64 `minimum.at` was exact.
4. `-W error` turned CuPy's advisory "CUDA path could not be detected" warning
   (expected with pip-packaged libraries) into an error; only that warning is
   now suppressed at import.

After the fixes, `tests/test_cuda_backend.py` passed 7/7 on the GPU, including
the synthetic CLI replay digest comparison.

## CUDA learned stages (owner request: CUDA option, CPU reference)

- Candidate detector: `ConnectedComponentDetector(device="cuda")` computes the
  same 26-connected, same-group voxel components by sparse min-label propagation
  with pointer jumping, then orders members exactly as the CPU union-find.
- Visibility: `CurrentScanVisibility(device="cuda")` samples corridors and
  resolves ownership on the device and reduces each chunk to (cell, beam count,
  lowest beam ID); exclusions, margin and capacity are shared host code.
- Tracker and FRNet stay on the host/CPU worker. The CLI accepts `--device cuda`
  in learned mode and records `inference_device: cpu` for FRNet.
- Parity: `tests/test_cuda_stages.py` compares CUDA and CPU schema-5 payloads
  (instances, tracks, beams, summary and every cell array) on two randomized
  learned scenes: exact on the GPU. The device code path also matches CPU with
  NumPy standing in for CuPy.

## Synthetic stage timing (diagnostic only)

Reproduce from `Drishti-2.5/`:
`uv run --frozen --extra viz --extra cuda python ../docs/research/experiments/0032-cuda-stage-timing.py`.
Scene: 120,000 synthetic points (70,000 road returns uniform in area from 3 to
70 m, 50,000 object returns in 250 clusters), authored semantics/ground, no
FRNet, no Patchwork++. Five timed runs after one warmup; medians:

| Stage | CPU p50 | CUDA p50 | Candidates | Free cells |
| --- | --- | --- | --- | --- |
| Detector | 417.9 ms | 212.2 ms | 4,283 both | - |
| Visibility | 3,689.9 ms | 568.1 ms | - | 65,536 both (capacity) |

Before two exact host optimizations (per-chunk device reduction and a
summed-area-table margin check), the same scene took 5,851.9/2,882.1 ms for
CPU/CUDA visibility. Detector medians varied between runs (CUDA 145.5 to
218.1 ms). This scene hits the free-cell cap and has many long low-elevation
corridors; real-scan cost is UNKNOWN. Both paths remain far above the 100 ms
per-scan gate, before FRNet (CPU p50 7,177 ms in E-052).

## Limitations

Synthetic scenes only; no real-data CPU/CUDA parity, no sequence replay, no
FRNet on GPU, laptop GPU under default power management, and one host. Exact
parity on real scans is expected but NOT VERIFIED; samples within 1e-6 m of a
cell edge are excluded on both devices, which limits but does not prove away
device rounding differences.
