# FRNet semantic CPU workflow

T-003 is a local development slice. Use a new output directory for each run.
The source dataset and pretrained checkpoint stay read-only and outside Git.
The checkpoint's separate terms and exact public-byte identity remain UNKNOWN;
do not redistribute it. The full sequence 08 quality gate and CUDA release
gate have not passed.

## Prepare the isolated model runtime

1. Clone the [authors' FRNet repository](https://github.com/Xiangxu-0103/FRNet)
   into a scratch location and checkout
   `d3749c8bcf6ef0fe2c95adea55375ac73a4b3825`. The adapter requires a
   clean tracked checkout at that revision.
2. Create a Python 3.8 CPU environment. The tested direct packages were
   Torch 1.8.1+cpu, NumPy 1.24.4, MMCV 2.1.0, MMEngine 0.9.0,
   MMDetection 3.2.0, MMDetection3D 1.3.0 and torch-scatter 2.0.8. The
   [139-package environment freeze](../../docs/research/experiments/0024-frnet-worker-freeze.txt)
   records the complete tested environment. Torch and MMCV CPU wheels came
   from their official wheel indexes; torch-scatter came from PyG's wheel
   index for Torch 1.8.1+cpu. A fresh environment rebuild from that freeze
   has not yet been independently verified.
3. In a separate Python 3.12 environment with modern PyTorch supporting
   `weights_only=True`, run the [safe exporter](../../docs/research/experiments/0023-safe-weights-export.py).
   It verifies the original checkpoint SHA-256, checks all tensor values and
   emits a tensor-only NPZ. The tested NPZ SHA-256 was
   `4653623169f8f745907a8d7ea6a8561fed896f55dbdf421a3cd1bf86a0fe99fb`.

Example export from the repository root, using an already prepared modern
PyTorch interpreter:

```bash
MODERN_TORCH_PYTHON=/path/to/python3.12-with-torch
"$MODERN_TORCH_PYTHON" docs/research/experiments/0023-safe-weights-export.py \
  --checkpoint data/dataset/frnet-semantickitti_seg.pth \
  --sha256 09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e \
  --output /tmp/frnet-weights-new.npz
sha256sum /tmp/frnet-weights-new.npz
```

NPZ bytes may differ between exporters even if tensors match; pass the hash
of the newly exported file to the replay command. The model worker strictly
loads every weight key into the pinned upstream architecture.

## Replay and write predictions

Run from `Drishti-2.5/`. Replace the scratch paths and the NPZ digest with
your prepared artifacts:

```bash
FRNET_PYTHON=/tmp/drishti-frnet-env/bin/python
FRNET_SOURCE=/tmp/drishti-frnet-source-20260927
FRNET_WEIGHTS=/tmp/drishti-frnet-safe-tensors-20260927.npz
FRNET_WEIGHTS_SHA256=4653623169f8f745907a8d7ea6a8561fed896f55dbdf421a3cd1bf86a0fe99fb
uv run --frozen drishti replay \
  --dataset ../data/dataset --sequence 08 --mode learned --view none \
  --output /tmp/drishti-frnet-seq08-new --write-predictions \
  --frnet-python "$FRNET_PYTHON" --frnet-source "$FRNET_SOURCE" \
  --frnet-checkpoint ../data/dataset/frnet-semantickitti_seg.pth \
  --frnet-checkpoint-sha256 09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e \
  --frnet-weights-npz "$FRNET_WEIGHTS" \
  --frnet-weights-sha256 "$FRNET_WEIGHTS_SHA256"
```

Omit `--max-frames` for the full sequence. `manifest.json` pins hashes,
source/class-map revisions, worker versions and score meaning. `frames.jsonl`
contains accepted semantic-only receipt digests and stage timings. Raw-ID
prediction files go under `predictions/sequences/08/predictions/`. The worker
does not read labels; it receives accepted sensor points only. An invalid
checkpoint hash, export hash, source revision, point count or output fails
explicitly. CPU model inference took about 7 seconds on the sampled full scan,
so this workflow is not a 100 ms release path.

## Evaluate offline

Use the [official SemanticKITTI API](https://github.com/PRBonn/semantic-kitti-api)
at pinned commit `a9c749e8124b2243b6eef1b8bcf971a9f1173a2d` for canonical
validation mIoU and per-class IoU. Run it from its repository after a full
sequence 08 replay:

```bash
python evaluate_semantics.py \
  --dataset /home/ashin/Hackathon/SIH/data/dataset \
  --predictions /tmp/drishti-frnet-seq08-new/predictions \
  --split valid --backend numpy
```

The official script requires a prediction for every validation label file.
For supplemental by-range IoU and unknown coverage, run from `Drishti-2.5/`:

```bash
uv run --frozen python -m drishti.evaluation \
  --dataset ../data/dataset \
  --predictions /tmp/drishti-frnet-seq08-new/predictions \
  --sequence 08 --output /tmp/drishti-frnet-seq08-metrics.json
```

`--allow-partial` is available for a diagnostic subset and marks the report
as incomplete. It cannot satisfy the held-out acceptance gate. Sequence 00
is training data; do not use its high one-scan score as validation. Numeric
D-005 minimum mIoU, per-class/range and maximum unknown thresholds remain to
be approved after the complete baseline.

## Offline training boundary

The pinned authors' configuration uses `semantickitti_infos_train.pkl` for
training and `semantickitti_infos_val.pkl` for validation. Its
`docs/DATA_PREPARE.md` describes `tools/create_semantickitti.py`; its
`docs/GET_STARTED.md` describes `python train.py
configs/frnet/frnet-semantickitti_seg.py`. Run preparation against a scratch
dataset root that links to read-only source scans, so generated info files and
training outputs never enter the source dataset. Keep sequence 08 out of
training and tuning. Local retraining has NOT BEEN RUN on this CPU host; any
new checkpoint needs its own hash, split manifest and full evaluation.
