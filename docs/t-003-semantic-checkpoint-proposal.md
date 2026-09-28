# T-003 semantic checkpoint slice

Status: Approved for bounded CPU implementation on 2026-09-27. The product
owner explicitly approved T-003 implementation. [Decision 0004](decisions/0004-frnet-semantic-cpu-slice.md)
freezes this semantic-only development scope. Numeric D-005 quality thresholds
and full release acceptance remain open; T-003 is IN PROGRESS.

## Verified starting point

- [Experiment 0022](research/experiments/0022-local-frnet-checkpoint-screen.md)
  pins the user-supplied `frnet-semantickitti_seg.pth` at SHA-256
  `09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`.
  A CPU `weights_only=True` load found 421 finite tensors and 10,029,572
  parameters. The authors' public folder contains the same filename and
  displayed size; exact upstream-byte equality was not established.
- [Upstream source](https://github.com/Xiangxu-0103/FRNet) was inspected at
  `d3749c8bcf6ef0fe2c95adea55375ac73a4b3825`. The authors' inference
  stack requires MMDetection3D/MMCV/MMEngine and `torch-scatter`. Drishti's
  current Python 3.12 environment has none of these model packages.
- [Experiment 0023](research/experiments/0023-frnet-cpu-inference-screen.md)
  built an isolated Python 3.8 CPU environment and loaded all 421 model keys
  with exact shape match. Label-free inference returned 123,389/123,389
  original-point predictions on sequence 08 and 124,668/124,668 on training
  sequence 00; both full-scan reorder checks had zero restored-label
  mismatches. Prediction took 6.417 and 6.344 seconds respectively. Both
  one-scan scores are diagnostic, not official held-out or product results.
- The approved T-002 version-1 diagnostic product result and evaluator are
  integrated in this checkout. T-003 adds a separate schema-2 semantic-only
  result without promoting it to a complete release result.

## Approved T-003 scope

1. Select a semantic-only, versioned FRNet checkpoint milestone. Treat motion,
   instances and free-space as separate later tasks. Keep raw scans/labels and
   the checkpoint outside source control.
2. Implement a replaceable CPU predictor at the shared `MappingEngine.process`
   boundary after point acceptance and before cell aggregation. Feed only
   sensor-frame x/y/z/intensity and accepted original point IDs. Geometric and
   oracle paths remain explicit and label access is excluded from prediction.
3. Reproduce the authors' inference preprocessing and original-point recovery.
   Their `RangeInterpolation` appends synthetic points; the predictor must return
   exactly one prediction for each accepted original point in accepted order.
   Validate geometry, intensity and size failures explicitly.
4. Convert FRNet semantic channels 0..18 to Drishti IDs 1..19 and FRNet ignore
   channel 19 to unknown ID 0. The source's channel 4 groups bus, on-rails and
   other-vehicle raw labels. Publish softmax confidence as a model score, not a
   calibrated probability or safety uncertainty. Unknown points need a reason.
5. Include checkpoint hash, upstream revision, preprocessing/class-map revision,
   runtime versions and stage timing in versioned result provenance. Provide
   reproducible offline inference/evaluation commands. Training remains an
   offline workflow with an explicit train/validation split and no training on
   held-out labels.

## T-003 acceptance evidence

| Gate | Required evidence |
| --- | --- |
| Checkpoint | SHA-256 verified before loading; exact source/terms recorded; wrong hash, incompatible keys and invalid output rejected. |
| Point contract | Reorder, projection collision, first point, appended interpolation, rejected ROI, invalid intensity, class 19 and empty/oversize fixtures preserve accepted IDs and unknown behavior. |
| Oracle isolation | A real replay with labels unavailable to the predictor produces the same point count/order as the shared engine path; label access traps fail if touched. |
| Quality | Official SemanticKITTI evaluator on a frozen held-out split records per-class and by-range IoU, mIoU and unknown coverage. Pass/fail uses approved numeric D-005 thresholds. |
| Reproducibility | Pinned runtime, config, checkpoint and split; saved command/manifests; fresh installed-wheel CPU replay; lint, format, types and relevant suite pass. |
| Performance | Preprocess, inference, postprocess, mapping, result receipt and RSS measured together. This is a CPU development result; AC-008 remains a later complete-path CUDA release judgment. |

## Decisions and evidence needed before closure

- **D-002 model milestone:** semantic-only local CPU development is approved.
  Redistribution or release use of the separately hosted weights awaits their
  applicable terms and exact upstream-byte identity.
- **D-005 semantic gates:** approve the held-out split, minimum total and
  per-class/by-range quality, maximum unknown coverage, and whether the
  target is to reproduce the authors' validation score or to meet a separate
  product threshold. A one-scan observed-class mean IoU of 0.6423 is available,
  but it cannot establish a defensible held-out numeric target. E-051 now
  provides the full sequence 08 baseline: 0.675469 official 19-class mIoU,
  0.922835 labeled accuracy and a saved range report. Numeric gates still
  require an explicit decision.
- **T-002 handoff:** integrated in this checkout. Schema-1 diagnostic receipts
  remain separate from schema-2 semantic-only receipts; neither is an AC-008
  complete-path release receipt.

The approved adapter and evaluation workflow are implemented and verified in
[experiment 0024](research/experiments/0024-t003-frnet-drishti-integration.md).
Full-sequence held-out quality is recorded in
[experiment 0025](research/experiments/0025-t003-full-sequence08.md). Approved
numeric gates and the remaining checkpoint terms/identity evidence are required
before T-003 can move from IN PROGRESS to DONE.
