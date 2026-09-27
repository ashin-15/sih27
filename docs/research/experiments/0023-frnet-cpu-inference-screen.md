# Experiment 0023: isolated FRNet CPU inference screen

Date: 2026-09-27. RQ-001, T-003. This is an isolated research run using the
authors' model source and the user-supplied checkpoint. It does not modify
Drishti's runtime, prove held-out semantic quality, or satisfy AC-001/007/009.

## Provenance and environment

- Authors' FRNet source commit:
  `d3749c8bcf6ef0fe2c95adea55375ac73a4b3825`, cloned under `/tmp`.
- Checkpoint: ignored `data/dataset/frnet-semantickitti_seg.pth`, SHA-256
  `09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`.
  Upstream-byte equality and separate weight terms remain unverified; see
  [experiment 0022](0022-local-frnet-checkpoint-screen.md).
- Host: Intel Core Ultra 9 185H, x86_64, 22 reported logical CPUs; CPU run with
  `OMP_NUM_THREADS=4`. Temporary Python 3.8.20 environment: Torch 1.8.1+cpu,
  NumPy 1.24.4, MMCV 2.1.0 CPU wheel, MMEngine 0.9.0, MMDetection 3.2.0,
  MMDetection3D 1.3.0 and torch-scatter 2.0.8 CPU wheel.
- A separate Python 3.12 / Torch 2.14.0+cpu process loaded the local checkpoint
  with `weights_only=True`, verified its hash and exported tensor-only NPZ.
  The Python 3.8 process loaded the NPZ with `allow_pickle=False`, then loaded
  all model weights with `strict=True`. Expected and supplied state dicts had
  421 keys each, with zero missing/extra keys or shape mismatches.
- Torch 1.8.1 rejects `SyncBatchNorm` forward on CPU. The probe replaces only
  its evaluation forward call with `torch.nn.functional.batch_norm` using the
  same stored parameters and running statistics. This is a diagnostic CPU
  adaptation, not an approved Drishti backend or proven parity with CUDA.

## Method

The probe uses the authors' `RangeInterpolation` at H=64, W=2048, FoV +3/-25
degrees, then the FRNet data preprocessor at H=64, W=512. It creates an empty
`PointData` ground-truth container because the upstream preprocessor assumes
the attribute exists; it supplies no annotation values. Labels are read only
after prediction for the diagnostic score. The model truncates interpolated
points back to the original count using `num_points`.

The input is sequence 08 scan `000000`: 123,389 original points from
`data/dataset/sequences/08/velodyne/000000.bin`. A fixed-seed permutation of
all original points was separately inferred, then restored to input order for
an exact label comparison. The evaluation label file is the matching
`000000.label`. The reported mean IoU averages only the 13 classes present in
this one scan; it is not the official sequence or test-set metric.

| Observation | Result |
| --- | ---: |
| Original / interpolated / returned points | 123,389 / 126,968 / 123,389 |
| Reorder mismatches after restoring original positions | 0 / 123,389 |
| Checkpoint/model key and shape mismatches | 0 |
| Valid labeled / ignored points in diagnostic scoring | 116,465 / 6,924 |
| Single-scan present-class mean IoU | 0.6423 |
| Single-scan labeled-point accuracy | 0.9163 |
| Model construction/weight load, preprocessing, prediction | 0.464 / 0.090 / 6.417 s |
| Process peak RSS | 2,238,196 KiB |

The [JSON report](0023-frnet-cpu-seq08-frame000000.json) preserves counts,
class distribution, timings and the exact diagnostic score. A separate
4,096-point prefix run also returned 4,096 predictions and zero reorder
mismatches. Full-scan CPU prediction alone greatly exceeds 100 ms, but the
release gate is a later complete-path CUDA measurement on identified hardware.

A second full scan, sequence 00 frame 000000, returned 124,668 predictions for
124,668 original points, with zero mismatches after a full input permutation.
Prediction took 6.344 s. Its one-scan observed-class mean IoU was 0.8975 over
12 present classes. Sequence 00 belongs to the authors' training split, so
this score is a compatibility diagnostic only and must not be treated as a
held-out quality estimate. The [second JSON report](0023-frnet-cpu-seq00-frame000000.json)
preserves its counts and timings.

## Reproduction outline

1. Clone the authors' repository and checkout the commit above. Make a
   temporary Python 3.8 environment with the listed dependencies. The CPU
   MMCV wheel came from the official `torch1.8` CPU wheel index and
   torch-scatter from the PyG `torch-1.8.1+cpu` index.
2. In an isolated modern PyTorch environment, run
   [the safe exporter](0023-safe-weights-export.py) with `--checkpoint`,
   `--sha256` and a new `--output /tmp/frnet-weights.npz`.
3. In the Python 3.8 environment, run [the CPU probe](0023-frnet-cpu-probe.py)
   with `--source-root`, `--weights-npz`, `--scan`, `--labels` and
   `--check-shuffle`. Omit `--labels` for a label-free-only run. Source scans
   and checkpoint are read-only; outputs stay outside `data/`.

## Judgment

MEASURED RESULT: the checkpoint loads into the authors' model with exact key
and shape agreement, and the isolated label-free CPU path returns one aligned
prediction per original point on a full real scan. This validates a useful
candidate and identifies a CPU runtime adaptation need. UNKNOWN: official
held-out metrics, class/range gates, confidence calibration, Drishti adapter
behavior, complete result provenance, exact upstream checkpoint identity,
license terms and CUDA/full-path latency. T-003 remains BLOCKED pending its
frozen and approved acceptance slice, integrated T-002 interface, production
adapter and held-out evidence.
