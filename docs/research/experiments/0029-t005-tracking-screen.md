# Experiment 0029: T-005 tracking contract screen

Date: 2026-09-28. Question: RQ-002. Scope: research and contract preparation
only. No tracker was implemented or evaluated.

## Primary sources and current inputs

- The [SemanticKITTI dataset definition](https://semantic-kitti.org/dataset.html)
  says the upper 16 label bits carry instance IDs that are consistent over a
  sequence. The [4D panoptic task](https://semantic-kitti.org/tasks.html)
  requires IDs to stay unique in space and time and scores semantic and
  association quality with LSTQ. Its moving-object task uses a separate
  moving/static point label and IoU. Neither score validates metric world
  velocity or covariance.
- The [4D-PLS authors' implementation](https://github.com/MehmetAygun/4D-PLS)
  provides a 4D panoptic evaluator route; the locally pinned
  `semantic-kitti-api` checkout used for T-004 has only the per-scan
  `evaluate_panoptic.py`. The 4D evaluator has not been pinned, run or
  compared against Drishti outputs.
- Current `MappingEngine.process` owns one ordered sequence, has a map pose and
  emits frame-local T-004 candidate IDs, centers and bounds. It has no track
  state. `ProductFrameResult.TrackEvidence` has tentative, confirmed,
  occluded and expired states, but schema-3 candidate receipts forbid tracks.
  The pose source is declared, while pose quality is unverified in current
  product results. Candidate scores and geometric uncertainty are not
  calibrated.

## Decision frontier

1. **First T-005 slice:** sequence-owned association with stable IDs and
   unknown velocity, or association plus quantitative velocity. The former
   is recommended because a covariance calibration and pose-quality gate do
   not exist. AC-004 can be developed separately from full AC-005.
2. **Candidate scope:** associate only class-known thing candidates 1..8
   initially, or also ambiguous thin/unknown geometry. The former is
   recommended for a bounded first CPU slice; T-004 currently emits about
   2 million total candidate components over sequence 08, many ambiguous.
   Thin/unknown tracking needs an explicit false-track and capacity policy.
3. **Result boundary:** a schema-4 `stage=tracking` immutable receipt should
   extend schema 3 and validate ID lifetime, one-to-one instance assignment,
   track capacity and unknown motion. This is a proposal, not an approved
   interface. Schema 1 to 3 remain supported.

## Required evidence before full T-005 acceptance

Crossing, short occlusion, disappearance/reappearance, static wall under ego
motion, sequence reset, invalid timestamp and capacity fixtures; source and
installed-wheel multi-frame replay; 4D panoptic association metric or a
documented equivalent; ID switches, fragmentation, false tracks and lifecycle
counts; separate motion velocity error and covariance calibration against
timed world-frame ground truth. The current SemanticKITTI annotation format
supports sequence ID comparison for thing classes, but the evaluator and
Drishti tracking export are not implemented. Curated fixtures alone cannot
establish held-out tracking quality.

Conclusion: T-004 provides the input interface needed to **draft** a bounded
T-005 association stage. Full T-004/AC-002 obstacle quality is open; it does
not prevent research or a separately approved development slice. T-005
production implementation is blocked by its unfrozen PRD, design, acceptance
and schema-4 contract. No track or velocity claim follows from this screen.
