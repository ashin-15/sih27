# Experiment 0026: CPU semantic implementation check and measurement

Date: 2026-09-28. RQ-001 / T-003. Status: verification completed; numeric
D-005 acceptance remains open.

## Scope and method

The checked tree was clean before this work. The approved implementation is
the current Python 3.12 source package plus an isolated Python 3.8 FRNet CPU
worker. This check inspected `learned.py`, `frnet_worker.py`, `pipeline.py`,
`cli.py` and their contract tests. It ran focused and full package checks,
then a fresh three-scan headless learned replay on SemanticKITTI sequence 08.
The local host reports an Intel Core Ultra 9 185H, 22 logical CPUs and 30 GiB
RAM. The default replay config uses a 150,000-point input cap, radial
5/10/50 cm cells and no viewer; no pacing or 100 ms checker was enabled.
The replay used the existing source environment directly because `uv run`
could not create a temporary file in the read-only default uv cache. The
failed `uv` attempt processed no scans; no saved result was overwritten.

Fresh ignored evidence:
`artifacts/t003-cpu-check-20260928T130505Z/` contains `manifest.json`,
`frames.jsonl`, `summary.json`, three raw-ID prediction files,
`cpu-check-monitor.json` and `verification.json`. The process log is its
adjacent `.log` file. The verified checkpoint SHA-256 is
`09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`;
the safe tensor export SHA-256 is
`4653623169f8f745907a8d7ea6a8561fed896f55dbdf421a3cd1bf86a0fe99fb`.
The clean FRNet source checkout is revision
`d3749c8bcf6ef0fe2c95adea55375ac73a4b3825`. The newly built wheel SHA-256
is `a1c6b7c11045a1e7d9c689d3ef9f2f6cd958b329a9c05fc11ef790dc813084c6`;
the fresh replay used the editable source environment, not that wheel.

The exact argument vector is saved in `cpu-check-monitor.json`. To repeat the
three-scan check from the repository root, choose a new output directory and
run:

```bash
Drishti-2.5/.venv/bin/drishti replay \
  --dataset data/dataset --sequence 08 --mode learned --view none \
  --max-frames 3 --output artifacts/NEW-t003-cpu-check --write-predictions \
  --frnet-python artifacts/t003-frnet-env/bin/python \
  --frnet-source artifacts/t003-frnet-source \
  --frnet-checkpoint data/dataset/frnet-semantickitti_seg.pth \
  --frnet-checkpoint-sha256 09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e \
  --frnet-weights-npz artifacts/t003-frnet-safe-tensors-20260928.npz \
  --frnet-weights-sha256 4653623169f8f745907a8d7ea6a8561fed896f55dbdf421a3cd1bf86a0fe99fb
```

## What this CPU slice does

`DatasetSource` reads a scan and pose. `MappingEngine.process` validates
ordering and point capacity, filters invalid/out-of-region points while
preserving original IDs, then sends accepted float32 XYZ and intensity to the
persistent worker. The worker strictly loads 421 checkpoint tensors into the
authors' FRNet model, uses the pinned range interpolation and returns one
20-channel semantic decision and maximum softmax score per accepted original
point. A CPU evaluation adaptation makes the model's SyncBatchNorm use its
stored statistics. The score is **uncalibrated**.

The adapter maps FRNet channels 0..18 to Drishti learning IDs 1..19 and its
ignore channel 19 to unknown 0. Point predictions feed the existing
Patchwork++ ground, projection and single-frame cell aggregation path. The
semantic-only product result and same-process evaluator reject invalid
alignment, classes, scores or unsupported claims. The CLI writes ordered
schema-2 accepted receipts and raw SemanticKITTI prediction files; excluded
input points remain unknown in those files. Dataset labels enter only the
offline evaluation, never the worker. The slice has no object instances,
tracking, measured motion, temporal map or free-space proof.

## Checks run now

From `Drishti-2.5/`:

| Check | Result |
| --- | --- |
| Focused learned, CLI, evaluation and product-result tests with `-W error` | 22 passed |
| Full `uv run --frozen --extra viz pytest -q -W error` | 71 passed, 3 skipped (CUDA unavailable) |
| `uv run --frozen ruff check .` and `ruff format --check .` | Passed; 50 files formatted |
| `uv run --frozen --extra viz mypy` | Passed; 36 source files |
| `uv build --no-sources` | Source distribution and wheel built |
| Fresh three-scan real learned replay | 3/3 accepted schema-2 semantic receipts and prediction files; all three prediction files byte-identical to the saved full-run prefix |

The three prediction SHA-256 values are recorded in `verification.json`.
This new run also matched the saved input digests on frames 0..2. All three
frames had their original points accepted, with 123,389, 123,433 and 123,159
predictions respectively. The three-scan processing p50 was 7,503 ms; the
model stage took 7,640, 7,355 and 7,184 ms respectively. Fresh replay
wall time was 28.89 s, including startup and reporting.

## Complete sequence measurements reviewed

The existing [experiment 0025](0025-t003-full-sequence08.md) supplies the
4,071-scan held-out point-semantic result. This check independently confirmed
ordered frame IDs 0..4070, 4,071 accepted schema-2 semantic receipts, 4,071
predictions, 499,079,562 input and accepted points, and exact official versus
supplemental overall score agreement. The combined predictions cross a new
mapping engine at frame 793, so they do not prove continuous map state.

| Metric across 4,071 scans | p50 | p95 | p99 | Maximum |
| --- | ---: | ---: | ---: | ---: |
| FRNet model stage, ms | 7,177 | 7,564 | 7,689 | 71,466 |
| Whole `MappingEngine.process`, ms | 7,283 | 7,672 | 7,798 | 71,571 |
| Ground stage, ms | 26 | 48 | 52 | 59 |
| Projection stage, ms | 13 | 18 | 26 | 32 |
| Cell mapping stage, ms | 43 | 51 | 64 | 78 |

Every model and whole-process duration exceeded 100 ms. This is an unpaced
CPU service-time measurement, not the selected complete-product scheduled
arrival-to-receipt gate. The three-scan process-tree RSS sampled every 0.2 s
peaked at 2,440,826,880 bytes (about 2.27 GiB), including a sampled FRNet
worker peak of 2,272,108,544 bytes (about 2.12 GiB). Sampling can miss a
shorter peak, and summing process RSS can count shared pages more than once.
The CLI's host-process RSS alone excludes the isolated worker.

The official 19-class sequence 08 mIoU was **0.675469** and labeled-point
accuracy **0.922835**; the supplemental evaluator matched exactly overall.
Range mIoU was 0.690760 at 0-20 m, 0.543065 at 20-50 m and 0.157163 at 50 m
and farther. The far band has only 198,638 labeled points. Motorcyclist IoU
was 0.001920 and other-ground IoU 0.090273. There were zero unknown
predictions, which is coverage rather than evidence of calibrated certainty.

## Limits and conclusion

MEASURED RESULT: the current CPU semantic slice executes from source, repeats
the pinned predictions on a fresh real replay, passes its contract checks and
has a complete held-out point-semantic baseline. It is far slower than the
selected 100 ms frame deadline on this CPU. The 71-second maximum is recorded
without an established cause. The 3-scan sampled RSS is not a full-sequence
memory bound. Separate checkpoint weight terms, exact public-byte identity
and D-005 numeric semantic gates remain open. No continuous map-state,
complete-product AC-008, CUDA timing or release suitability is established.
