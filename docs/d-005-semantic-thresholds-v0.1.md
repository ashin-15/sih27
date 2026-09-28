# D-005 semantic threshold sheet v0.1

Date: 2026-09-28. Status: DRAFT FOR PRODUCT-OWNER REVIEW. Scope: the T-003
semantic-only CPU milestone (AC-001/AC-009/AC-014), not complete-product
release acceptance. All numeric limits below are **proposed product choices**,
not approved limits or measured passes. A change to a number, split, metric or
support rule requires a new version before final scoring.

## Evidence and decision boundary

MEASURED RESULT: [E-051](research/experiments/0025-t003-full-sequence08.md)
provides complete sequence 08 validation predictions for 4,071 scans and an
official 19-class mIoU of 0.675469. Supplemental all-point mIoU agrees;
0-20/20-50/50+ m fixed-19-class mIoU is 0.690760/0.543065/0.157163.
Motorcyclist and other-ground IoU are 0.001920 and 0.090273. There were zero
unknown predictions. The far stratum has 198,638 labeled points and absent
classes score zero in the current report. These observations inform the draft
but cannot be a prospective pass after the thresholds are selected from them.

FACT: the [official SemanticKITTI configuration](https://github.com/PRBonn/semantic-kitti-api/blob/master/config/semantic-kitti.yaml)
assigns sequence 08 to validation and sequences 11-21 to test. The
[official evaluator](https://github.com/PRBonn/semantic-kitti-api/blob/master/evaluate_semantics.py)
scores learning IDs 1-19 and ignores ground-truth learning ID 0. The
[dataset owner](https://www.semantic-kitti.org/dataset.html) withholds test
labels and scores test submissions through its evaluation service. The
[official distance script](https://github.com/PRBonn/semantic-kitti-api/blob/master/evaluate_semantics_by_distance.py)
uses different bins from Drishti's supplemental evaluator. Do not mix its
distance numbers with the bins below.

## Metric contract

Count each original scan point once, in scan order, including a raw unknown
prediction for a rejected point. Require one matching prediction file per scan
and exact scan/label/prediction point counts. The inference path must have no
label access. No `--allow-partial` report may pass. All metrics pool point
confusion counts over the set before division; do not average per-scan scores.

For class `c` in learning IDs 1-19, `IoU_c = TP_c / (TP_c + FP_c + FN_c)`.
Overall `mIoU_19` is the unweighted mean of those 19 IoUs, using the pinned
official SemanticKITTI evaluator and inverse-mapped raw-ID prediction files.
Ground-truth ID 0 contributes to neither metric. Predicted ID 0 on a labeled
point is a false negative for its true class. A class with zero union scores
zero in the official 19-class mean. Labeled-point accuracy is reported, with
no independent pass floor.

The supplemental range evaluator uses Euclidean sensor-frame distance and
half-open bins `[0,20)`, `[20,50)`, `[50,infinity)` metres, with exactly 20 m
in the middle bin and 50 m in the far bin. For each bin, report all-19 mIoU,
all 19 class IoUs, ground-truth positives and unions. The **blocking range
metric** is supported-class mIoU: the unweighted mean over classes that meet
both the ground-truth-positive and union minimum for that bin. Unsupported
classes stay in the published table with `INSUFFICIENT_SUPPORT`; they are not
silently counted as successful. Minimums are:

| Bin | Labeled points | Ground-truth positives and union per supported class | Supported classes |
| --- | ---: | ---: | ---: |
| 0-20 m | 1,000,000 | 1,000 each | 10 |
| 20-50 m | 250,000 | 1,000 each | 10 |
| 50 m+ | 100,000 | 100 each | 5 |

The far thresholds recognize sparse returns; they require reporting the
support counts and do not make far-range reliability a safety claim. A bin
below any minimum is `NOT EVALUABLE`, which blocks final acceptance.

Unknown coverage is `count(predicted learning ID 0) / count(all original scan
points)` across the evaluated set, reported overall and in each range. Also
report unknown rate among accepted points and rejected-point count/reasons so
ROI filtering cannot hide missing predictions. The ceiling below applies to
the all-original-point rate. Zero unknowns is not a substitute for IoU.

## Proposed numeric pass rules

All comparisons use unrounded values. Equality passes. Every blocking row
must pass; no weighted aggregate may compensate for a failed row.

| Metric | Proposed blocking rule | Reason for this draft value |
| --- | --- | --- |
| Official overall mIoU, 19 classes | `>= 0.65` | A rounded floor below the observed 0.675469 development baseline; confirms broadly comparable quality, not the authors' published score. |
| Official per-class IoU, each of 19 classes | `>= 0.10` for **every** class | Prevents a high mean from masking a near-zero class. The current motorcyclist and other-ground values would fail; improving or explicitly revising this rule is a product decision. |
| Supported-class mIoU, 0-20 m | `>= 0.60` | Proposed near-range floor; cannot be compared directly with the saved fixed-19 mean until supported-class scores are computed. |
| Supported-class mIoU, 20-50 m | `>= 0.45` | Proposed middle-range floor; same support caveat. |
| Supported-class mIoU, 50 m+ | `>= 0.20` | Proposed far-range floor, conditional on the support rule. The saved fixed-19 mean does not establish this supported-class score or its class counts. |
| Unknown coverage, all original points | `<= 0.01` overall and `<= 0.02` in each range | Bounds abstention while preserving explicit unknowns for rejected or unsupported points. The current zero rate does not validate these ceilings on an independent set. |

These are engineering proposals anchored to E-051 and conservative class
coverage, not empirically calibrated release or safety limits. In particular,
the per-class rule is intentionally stronger than this checkpoint's observed
motorcyclist/other-ground performance. Do not lower it to make E-051 pass
without an explicit product-owner decision and a new sheet version.

## Separate final evaluation set and execution

**F-001, official blind test:** SemanticKITTI sequences 11-21, using the
official semantic segmentation evaluation service. This is separate from
sequence 08 and the training sequences 00-07/09-10. Freeze the model weights,
source revision, class map, preprocessing, code/wheel, output options and this
sheet before generating predictions or submitting. Make one submission for
the frozen candidate; archive its submission ID and official overall and
per-class scores. F-001 decides the overall and per-class rules. Its local
prediction files can also establish unknown coverage and alignment, but hidden
labels prevent local range IoU scoring.

**F-002, independent labeled range audit:** acquire and lock a separate set
of complete LiDAR scans that was not used for training, checkpoint selection,
threshold setting or E-051. It must use a documented sensor, calibration,
point/label alignment and a reviewed mapping to the same 19 learning classes.
Before inference, publish a scan-ID manifest and content hashes; have an
annotation reviewer verify labeling quality and all three range support
minimums above. Use the pinned supplemental evaluator for range metrics and
unknown coverage. F-002 supplies the blocking range result and a second
unknown-coverage result. Its data source, scan IDs, labels, license, reviewer
and hashes are **TBD**; no such final set is established in this repository.

F-001 and F-002 must both pass their applicable rules. The unknown ceiling
applies independently to both sets, overall and in each range. If F-002 cannot be
materialized or a range lacks support, record `NOT VERIFIED`; do not substitute
the already inspected sequence 08 or a training sequence. If official F-001
feedback lacks a needed per-class score, record that rule `NOT VERIFIED` until
the evaluation service provides it or another independent labeled set is
approved. No repeated test submissions or post-result tuning may be called
the same frozen final evaluation.

## Approval and remaining T-003 gates

- Product owner: approve or revise the numeric rules, class/range support
  policy, and F-001/F-002 split as D-005 v1.0 before final evaluation.
- Engineering: verify F-002 availability and annotation/coverage, and archive
  the frozen run manifest, prediction coverage, evaluator outputs and hashes.
- Research/evidence owner: resolve exact public checkpoint-byte identity,
  applicable separate weight terms and the reviewed training split/recipe.

AC-014/T-003 remains IN PROGRESS until the approved semantic gate and those
checkpoint requirements have evidence. Complete-product AC-008, CUDA timing,
instances, tracking, motion and free-space require separate decisions and
validation. This sheet does not authorize release or redistribution.
