# Experiment 0024: T-003 FRNet integration verification

Date: 2026-09-27. Status: CPU implementation verification, not T-003 quality
acceptance or AC-008 release evidence.

## Pinned inputs

- Local checkpoint `data/dataset/frnet-semantickitti_seg.pth`, SHA-256
  `09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`.
  It remains ignored. Exact public-byte match and separate weight terms are
  UNKNOWN.
- Safe tensor-only NPZ from experiment 0023, SHA-256
  `4653623169f8f745907a8d7ea6a8561fed896f55dbdf421a3cd1bf86a0fe99fb`.
  The exporter verified the original checkpoint hash before safe loading.
- Authors' FRNet source commit `d3749c8bcf6ef0fe2c95adea55375ac73a4b3825`;
  clean tracked checkout required by the adapter. Isolated worker: Python
  3.8.20, Torch 1.8.1+cpu, MMCV 2.1.0, MMEngine 0.9.0,
  MMDetection3D 1.3.0. Torch 1.8 SyncBatchNorm evaluation uses its stored
  statistics through `torch.nn.functional.batch_norm` on CPU. This is a
  development adaptation, without CUDA parity proof.
- Official SemanticKITTI API commit `a9c749e8124b2243b6eef1b8bcf971a9f1173a2d`.

## Real-data replay

The source-tree CLI replay of sequence 08 frame 000000 completed with
123,389/123,389 accepted points, no invalid intensity, 69,004 projection
collisions retained in mapping, and one accepted schema-2 `semantic` receipt.
The model stage took 7,160.6 ms and the whole engine took 7,317.2 ms;
receipt validation took 361.1 ms. These are one-run CPU observations, not a
benchmark distribution. `realtime_release_gate_met` stayed false. The run
is `/tmp/drishti-t003-e2e-20260927-01`.

A second source-tree run with `--write-predictions` wrote 123,389 raw-ID labels
under `/tmp/drishti-t003-e2e-20260927-02/predictions`, outside the source
dataset. Decoding them to Drishti learning IDs exactly matched the
per-channel prediction counts from the isolated authors' probe. A freshly
built wheel was installed into `/tmp/drishti-t003-wheel-env-20260927` with
NumPy 2.5.3 and pypatchworkpp 1.4.1. Its real sequence 08 replay from `/tmp`
accepted one semantic receipt and wrote a byte-identical prediction file:
SHA-256 `66cd44a7bb33b75c85c5b237606d086e212b11447017454d7420c008f40b0bf4`.
The wheel run is `/tmp/drishti-t003-wheel-e2e-20260927-01`.

After the final schema-1 digest regression test and viewer badge edit, an
offline source/wheel build succeeded using the cached pinned build backend.
The final wheel was reinstalled into the same isolated wheel environment and
replayed the same scan from `/tmp` at
`/tmp/drishti-t003-wheel-final-20260927-01`. Its schema-2 semantic receipt
was accepted, the release gate was false, and the raw-ID prediction file
again had SHA-256
`66cd44a7bb33b75c85c5b237606d086e212b11447017454d7420c008f40b0bf4`.

## Evaluator check

The official API's `evaluate_semantics.py` was run on a temporary one-scan
view of sequence 08 labels and the source-tree prediction. It reported
0.439 mIoU over all 19 classes and 0.916 labeled-point accuracy. The earlier
0.6423 figure averages only 13 classes present in that scan, so these are
different denominators. This is NOT an official full validation-sequence
score. The supplemental `python -m drishti.evaluation` report at
`/tmp/drishti-t003-range-one-scan-20260927.json` reproduced 0.439459 mIoU,
0.916267 accuracy and zero unknown predictions; its 50 m+ band had zero
labeled ground-truth points and cannot support a range score.

## Package checks

Focused tests: 30 passed before the final regression test. Final broader
suite: 71 passed, 3 skipped (CUDA device unavailable), with warnings as
errors. Ruff check/format, strict mypy on 36 source/test files, and final
offline source/wheel builds passed. The initial build attempt
with a new empty uv cache could not reach PyPI; a permission-enabled retry
fetched the pinned `setuptools==80.9.0` and built both artifacts. No source
dataset or checkpoint bytes were changed.

## Limits and next evidence

These runs demonstrate a label-free, point-aligned CPU path and the output
format on one held-out scan. T-003 still needs complete sequence 08 official
metrics, per-class/by-range review, numeric D-005 thresholds and weight terms
before closure. The roughly 7-second model stage on this CPU does not meet a
100 ms frame deadline; CUDA and complete-path release timing are NOT VERIFIED.
