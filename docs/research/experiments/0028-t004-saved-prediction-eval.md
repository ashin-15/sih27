# Experiment 0028: T-004 CPU obstacle candidate baseline

Date: 2026-09-28. Question: RQ-006. Decision: 0005. Scope: approved
bounded CPU implementation, not full AC-002 or AC-008 acceptance.

## Inputs and provenance

The source and installed-wheel one-scan replays use the hash-pinned FRNet
worker described in [experiment 0026](0026-t003-cpu-semantic-verification.md),
SemanticKITTI sequence 08, `--mode learned --detect-obstacles
--write-panoptic-predictions --view none --max-frames 1`, and the same
`MappingEngine.process` path. New output directories are
`artifacts/t004-candidate-panoptic-20260928/` and
`artifacts/t004-candidate-wheel-final-20260928/`. The final built wheel was unpacked to
`/tmp/drishti-t004-wheel-final` and imported from there with `PYTHONPATH`; it was
not imported from the editable source checkout. Both manifests record
checkpoint, export, source revision, config and dependencies. The prediction
file is full original point order, SemanticKITTI uint32 raw class in the low
16 bits and frame-local thing instance ID in the high 16 bits.

DESIGN DECISION: the 0.45 m voxel width, 26-neighbor voxel connectivity,
three-point observed-status rule and 8,192-component cap are fixed development
settings from the approved candidate implementation and curated fixtures.
They were not tuned against sequence 08. Adjacent vehicles may merge; this
baseline reports that failure mode rather than asserting a separated object.

The full offline baseline is reproduced from the repository root with:

```bash
PYTHONPATH=Drishti-2.5/src Drishti-2.5/.venv/bin/python \
  docs/research/experiments/0028-t004-saved-prediction-eval.py \
  --dataset data/dataset \
  --saved-run artifacts/t003-seq08-restart-20260928 \
  --official-api artifacts/t003-semantic-kitti-api \
  --output artifacts/NEW-t004-saved-prediction-eval.json \
  --max-frames 4071
```

The official API checkout is revision
`a9c749e8124b2243b6eef1b8bcf971a9f1173a2d`. The offline adapter uses
all 4,071 prior FRNet class predictions from experiment 0025. Scores in those
files were not retained, so it supplies 1 for a known class and 0 for
unknown. Scores do not change the geometric grouping. It builds fresh
ground/map observations with the shared engine and presents annotations only
to the evaluator after inference. Oracle labels are not passed to the
predictor or detector. The sequence-08 saved predictions crossed a new
engine at frame 793 in their original T-003 run; this screen makes a fresh
continuous engine for candidate grouping, without repeating FRNet inference.

## Measured results

The source and wheel one-scan runs each produced one accepted sealed schema-3
candidate receipt, 983 frame-local candidates and 123,389 point-aligned
panoptic labels. Their panoptic prediction SHA-256 was identical:
`98f83554b7936a19edc076ed76b96353a825d8c71c8d0dba9f6438773a5331df`.
This checks the prediction bytes, not byte equality of run-specific receipts.
Source detector time was 139.43 ms and whole process time 7,303.20 ms;
final-wheel detector time was 139.54 ms and whole process time 7,755.83 ms
while a separate saved-class evaluator was running. The
worker's model dominates the CPU path. The CLI-reported parent process peak
RSS was about 190 MB, which excludes the isolated FRNet worker.

A further one-scan learned replay sampled parent plus child processes every
0.1 s. Its paths are `artifacts/t004-candidate-memory-run-20260928/` and
`artifacts/t004-candidate-memory-20260928.json`. It completed with an accepted
schema-3 receipt; sampled process-tree RSS peaked at 2,434,707,456 bytes and
PSS at 2,355,697,664 bytes. The largest child RSS sample was 2,331,049,984
bytes. A separate saved-class evaluator was running concurrently, so these
figures describe this local run, not an isolated hardware ceiling. Sampling
can miss a shorter peak, and summed RSS can double-count shared pages.

The first full offline pass saved
`artifacts/t004-saved-prediction-eval-full-20260928.json`:

| Sequence 08, 4,071 scans | Result |
| --- | ---: |
| Total candidate components | 2,021,045 |
| Official mean panoptic PQ, 19 included classes | 0.586892 |
| Mean PQ, thing classes 1 to 8 | 0.601801 |
| Detector p50 / p95 / p99 / max, ms | 145.53 / 173.40 / 185.09 / 216.60 |
| Engine process p50 / p95 / p99 / max, ms | 242.99 / 272.47 / 286.36 / 321.78 |
| Offline evaluator process peak RSS | 293,203,968 bytes |

| Thing class | Official PQ | TP | FP | FN |
| --- | ---: | ---: | ---: | ---: |
| Car | 0.9000 | 42,110 | 840 | 1,032 |
| Bicycle | 0.5125 | 916 | 292 | 586 |
| Motorcycle | 0.5194 | 440 | 230 | 354 |
| Truck | 0.6434 | 218 | 137 | 39 |
| Other vehicle | 0.5790 | 1,237 | 399 | 970 |
| Person | 0.7631 | 2,122 | 187 | 441 |
| Bicyclist | 0.8971 | 1,197 | 58 | 56 |
| Motorcyclist | 0.0000 | 0 | 19 | 78 |

The official result is a panoptic instance/semantic baseline, not a 3D box,
curb, overhang, clearance or false-free metric. The 2,021,045 total includes
unknown and thin-feature ambiguous components; it is not a count of verified
physical objects. The offline CPU cost excludes FRNet inference and receipt
construction; the one-scan real replay includes both. This unpaced CPU
measurement cannot satisfy a 100 ms zero-miss release gate.

Final package gates after the detector input validation change: 77 passed,
3 CUDA tests skipped; Ruff lint and format passed, strict mypy passed on 38
source files, and `uv build --no-sources` produced both distributions.

The second full pass saved the [stratified result](0028-t004-saved-prediction-eval-stratified.json)
and reproduced exactly the first pass's frame/candidate totals, official PQ
and all per-class official TP/FP/FN counters. Its detector p50/max was
148.42/258.70 ms and offline engine p50/max was 244.66/384.64 ms. The
second pass ran amid other local verification, so these are separate local
timing observations rather than a controlled speed comparison.

The supplemental thing counts below match only nonzero instance IDs with at
least 50 points on both GT and prediction sides, per class at greater than
0.5 raw-mask IoU. GT range is median horizontal sensor range; GT size is
point count. False positives use predicted range and size bins. This protocol
is a deliberately narrower diagnostic than the official evaluator, which
adds one to instance IDs, applies its ignore mask and can count matches below
50 points. The supplemental counts therefore must not be compared directly
with the official TP/FP/FN values above. They have no approved pass threshold.

| GT range | TP | FP in predicted range | FN | GT recall |
| --- | ---: | ---: | ---: | ---: |
| 0-20 m | 20,353 | 2,644 | 2,878 | 0.8761 |
| 20-50 m | 11,498 | 1,175 | 1,790 | 0.8653 |
| 50+ m | 8 | 117 | 22 | 0.2667 |

| GT point count | TP | FP in predicted size | FN | GT recall |
| --- | ---: | ---: | ---: | ---: |
| 50-199 | 11,845 | 2,692 | 3,071 | 0.7941 |
| 200-999 | 11,904 | 747 | 960 | 0.9254 |
| 1,000+ | 8,110 | 497 | 659 | 0.9248 |

Only 30 eligible GT segments fall in the 50+ m range bin, so its recall is
sensitive to a small number of segments. The far false positives use predicted
range and have no one-to-one range-bin denominator.

As a separate thin-feature semantic point proxy, pole (learning ID 18) had
1,238,154 TP, 539,482 FP and 428,273 FN points, for precision 0.6965 and
recall 0.7430. Traffic sign (ID 19) had 201,749 TP, 151,798 FP and 179,693
FN points, for precision 0.5706 and recall 0.5289. These point counts do not
score thin-object instances, bounds, curbs or overhangs. The metadata wording
in the saved JSON was clarified in the script after the pass; the numerical
counters and matching implementation were not changed.

## Wider obstacle review and limits

The frozen tests cover two separated cars, inseparable touching cars, sparse
person/pole, near and far returns, raised curb, overhang, nearby unknown wall,
empty input, invalid geometry, deterministic support and rejection of false
class/bounds claims. Curb, overhang and wall evidence stays class-unknown and
ambiguous. The tests establish contract behavior on authored fixtures, not
held-out obstacle recall. SemanticKITTI has no independent panoptic instance
annotations for those wider categories in this evaluation. Their held-out
false positives and recall, AC-002 numeric gates and calibrated geometric
uncertainty remain NOT VERIFIED. A separate reviewed obstacle annotation set
is needed for full AC-002 acceptance. No tracking, temporal state, solid
occupancy, clearance, passability or free-space claim follows from this slice.
