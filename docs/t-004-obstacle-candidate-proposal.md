# T-004 obstacle candidate slice - approved contract

Date: 2026-09-28. Status: APPROVED for bounded CPU implementation under decision 0005;
full AC-002 quality acceptance remains open.
Owner: product owner for behavior; engineering for implementation details.
The product owner requested comparison of all three scope options in the
Lavish review. [Screen 0027](research/experiments/0027-t004-option-comparison.md)
compares them on the same target and recommends this candidate slice only as
the immediate development fit; no detector-quality winner is measured.

## Current boundary

FACT at approval: `MappingEngine.process` returned accepted point coordinates,
original IDs, ground classifications and FRNet learning IDs/scores, without an
instance producer. The schema-2 semantic stage required its instance tuple
to be empty. T-003's held-out
semantic score measures point classes, not instance detection. T-003 quality and
checkpoint redistribution gates remain open.

The [SemanticKITTI panoptic task](https://www.semantic-kitti.org/tasks.html)
requires a semantic and instance label for each point of a scan, and scores
panoptic quality with a 0.5 segment-IoU match. Its [official panoptic evaluator](https://github.com/PRBonn/semantic-kitti-api/blob/master/evaluate_panoptic.py)
reads full-size raw-format prediction files and applies a minimum instance
point count. These are useful for traffic-participant instance evaluation.
They do not directly score 3D boxes, poles, curbs, overhang clearance or
collision safety. The [official class map](https://github.com/PRBonn/semantic-kitti-api/blob/master/config/semantic-kitti.yaml)
maps point semantics 1..19, including pole 18 and traffic sign 19.

## Proposed first CPU slice

**Approved bounded product choice:** Produce per-scan, evidence-only obstacle
candidates from the existing learned point semantics plus original accepted 3D
points and ground classifications. Include traffic participants, thin upright
structures and ambiguous nonground geometry. Output `unknown` when class
support is inadequate. A candidate is an observed point set with bounded
geometry, not a solid volume, free-space proof, tracked object or navigation
verdict. Keep the existing geometric and semantic-only modes stable; add an
explicit candidate stage and a new result schema version.

Technical implementation: use deterministic
spatial connected components with class-aware separation, then fit observed
axis-aligned bounds and keep original support IDs. Set component distance,
minimum support and ambiguity rules using training data and curated fixtures;
do not tune on sequence 08. Keep a replaceable detector interface so a learned
instance model can supersede the baseline. Reject malformed point alignment,
nonfinite geometry and overlapping support. Preserve label-free inference and
the one-engine-per-sequence path.

Proposed interface: `ObstacleDetector.detect(PointObservations, timestamp_ns)
-> tuple[InstanceEvidence, ...]`. A version-3 `stage=candidate` product result
would carry those observations while retaining the schema-2 semantic point/cell
rules and unknown motion, tracks and occupancy. Candidate IDs are frame-local
and deterministic, ordered by the smallest supporting original point ID.
`uncertainty_m=None` means no calibrated geometric uncertainty is available;
the status must be `ambiguous` for weak or mixed evidence. Empty input yields
an empty tuple. Existing schema-1/2 bytes and evaluators stay supported. A
rejected detector result cannot advance the product evaluator.

## Bounded acceptance (AC-015)

1. Source and installed-wheel CLI replay use `MappingEngine.process` and
   publish sealed, versioned candidate instances with support IDs drawn only
   from accepted original points. Repeated input yields the same support,
   geometry and digest. No oracle instance or motion label is read.
2. Curated fixtures cover separated vehicles (two candidates), touching
   vehicles (no false assertion of two objects if inseparable), a sparse person
   and pole (candidate or explicit ambiguity, never silently discarded), curb
   and overhang (ambiguous observed geometry only), nearby wall (never
   classified as a car from height alone), partial occlusion (bounded observed
   support only), unknown semantics (unknown class), projection losers (support
   retained), invalid coordinates (rejected before detection) and empty input
   (zero candidates). Exact fixture coordinates and expected support IDs are
   frozen before code; source-point accounting must hold in each case.
3. Saved held-out sequence 08 predictions are evaluated against independent
   instance labels with class/range/size recall and false positives; the
   official panoptic evaluator is run for its supported classes using full
   point-order predictions. Record latency and peak memory on the CPU reference.
4. The slice is marked implemented only after tests, lint, types, build and
   same-path replay pass. Full AC-002 quality acceptance requires separate
   reviewed numeric gates and obstacle annotations for the categories outside
   SemanticKITTI's panoptic instance benchmark. AC-008 remains NOT VERIFIED.

## Resolved staged decisions

| ID | Choice | Recommendation | Effect |
| --- | --- | --- | --- |
| T4-D1 | First slice: geometry/semantic candidates, learned instance model, or traffic-participant instances only | Geometry/semantic candidates | Establishes the output meaning and fixtures. |
| T4-D2 | Whether AC-015 is an implementation milestone while AC-002 remains a later quality gate | Yes | Allows a measured baseline without claiming release acceptance. |
| T4-D3 | Whether pole/curb/overhang observations may be emitted as explicitly ambiguous | Yes | Avoids unsupported object or clearance claims. |

T4-D1 to T4-D3 are approved for the bounded CPU slice. Numeric AC-002
thresholds and the held-out non-panoptic annotation set remain TBD. The
implementation fixes its local component settings and reports their measured
effect before any wider quality claim.

The implementation and baseline are recorded in
[experiment 0028](research/experiments/0028-t004-saved-prediction-eval.md).
The approved wording above remains the acceptance contract; the experiment
states which claims were verified and which require independent obstacle labels.
The bounded AC-015 implementation was accepted with caveats on 2026-09-28.
Full T-004/AC-002 quality remains in progress pending independent wider-obstacle
annotations and approved numeric gates.
