# Experiment 0022: local FRNet SemanticKITTI checkpoint screen

Date: 2026-09-27. RQ-001, O-002/O-007, T-003. This is a read-only artifact and
source-contract inspection, not an inference or accuracy run.

## 2026-09-27 verification follow-up

- The authors' public [checkpoint folder](https://drive.google.com/drive/folders/173ZIzO7HOSE2JQ7lz_Ikk4O85Mau68el?usp=sharing)
  visibly lists `frnet-semantickitti_seg.pth`, modified 7 December 2023, with
  displayed size 38.5 MB. The file ID exposed by the folder is
  `1Ez-fpwu2WFCBw8usjwxUz6XQruw-cGU4`. This establishes an official filename
  and plausible size match, not byte identity. Google Drive presented a virus
  scan warning before serving the file, so no upstream-byte hash comparison
  was completed. The warning response was HTML, not a checkpoint.
- Cloned the [authors' repository](https://github.com/Xiangxu-0103/FRNet) to
  `/tmp/drishti-frnet-source-20260927` at commit
  `d3749c8bcf6ef0fe2c95adea55375ac73a4b3825`. The documented inference
  stack was tested by the authors on Python 3.8, Torch 1.8.1, MMEngine 0.9.0,
  MMCV 2.1.0, MMDetection 3.2.0, MMDetection3D 1.3.0 and CUDA 10.2/11.1;
  `torch-scatter` is also required. These are upstream test conditions, not
  proof that a newer CPU runtime cannot work.
- Loaded the local file using `torch.load(path, map_location='cpu',
  weights_only=True)` with a cached Torch 2.14.0+cpu build and Python 3.12 in an
  isolated import environment. The top-level object is `state_dict`; all 421
  values are tensors, all floating tensors are finite, and parameter/buffer
  counting excluding BatchNorm running statistics gives 10,029,572 parameters.
  The primary head weight/bias are float32 with shapes `(20, 64)` and `(20,)`.
  This is a successful safe tensor load, not an FRNet model load or inference.
- Upstream source confirms inference depends on MMDetection3D/MMCV/MMEngine and
  `torch-scatter`, unavailable in the current Drishti environment. Its
  `RangeInterpolation` appends synthetic points after the originals and records
  `num_points` so prediction can truncate back to the original count. The
  checked test pipeline loads annotations for evaluation. A production adapter
  must construct a label-free path and verify original point order. No local
  per-point predictions, mIoU or latency result exists.

The later [isolated inference screen](0023-frnet-cpu-inference-screen.md)
supersedes the final sentence for a single real scan; it does not establish
official held-out quality or a Drishti runtime result.

## Artifact and method

- User placed `data/dataset/frnet-semantickitti_seg.pth` in the ignored dataset
  directory. The file is 40,327,676 bytes. SHA-256:
  `09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`.
- `file` identified a ZIP archive. `unzip -tq` found no compressed-data errors.
  It contains 423 entries, including `archive/data.pkl` and 421 tensor storage
  entries. The pickle has only a `state_dict` top-level key and 421 tensor keys.
- Inspected the pickle opcodes and tensor shape metadata with a restricted
  unpickler that allowed only `collections.OrderedDict`, two storage-type markers
  and a stub for `torch._utils._rebuild_tensor_v2`. Tensor bytes were not loaded
  as a model and the checkpoint was not executed. The primary segmentation head
  has `decode_head.conv_seg.weight` shape `(20, 64)` and bias shape `(20,)`.
  Four auxiliary heads also have 20 output channels. No checkpoint-embedded
  training revision, class map, source URL or license metadata was found.
- The current Drishti Python 3.12.14 environment has no `torch`, `mmdet3d`,
  `mmseg` or `mmengine` installed. No inference, quality or timing was measured.

## Class contract

The authors' [SemanticKITTI model configuration](https://github.com/Xiangxu-0103/FRNet/blob/master/configs/frnet/frnet-semantickitti_seg.py)
uses 20 output channels and `ignore_index=19`. Its [dataset configuration](https://github.com/Xiangxu-0103/FRNet/blob/master/configs/_base_/datasets/semantickitti_seg.py)
maps semantic raw labels to channels 0 through 18 and ignored raw labels to 19.
Channel 4 combines bus, on-rails and other-vehicle raw labels despite the
`class_names` entry being `bus`; Drishti calls this class `other-vehicle`.
Drishti's `src/drishti/semantics.py` uses 0 for unknown/ignored and 1 through
19 for semantic classes. Therefore the proposed output map
is FRNet `0..18 -> Drishti 1..19`, FRNet `19 -> Drishti 0`. This is a source-based
mapping proposal, not proof of the local file's training history or predictions.

The authors' test pipeline loads four-dimensional LiDAR points, applies
`PointSegClassMapping` and `RangeInterpolation` with H=64, W=2048, FoV +3/-25
degrees and `ignore_index=19`. It also loads annotations for evaluation; a
production adapter must exclude oracle labels and preserve accepted original
point IDs through the model's point projection and scatter.

## Conclusion and next checks at the time of this screen

FACT: a structurally plausible 20-channel FRNet checkpoint is now locally
available and pinned by hash. The former "no local checkpoint" statement is
superseded. UNKNOWN: whether the bytes match an authors' release, whether
separate weight terms permit this use, whether the model/configuration loads,
per-point alignment, held-out accuracy, CPU cost and full-path latency.

Next: retain the file as ignored input; establish download/source provenance
and applicable terms; freeze D-002/D-005 and the T-002 interfaces; reproduce
the authors' preprocessing and explicit channel remap; then run point-order
fixtures and the official held-out evaluator. Do not infer Drishti quality or
100 ms feasibility from checkpoint shape or the authors' published FPS.
