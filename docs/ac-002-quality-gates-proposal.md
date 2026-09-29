# AC-002 obstacle quality gates - approved traffic gates v0.1

Drafted 2026-09-28; traffic-participant numeric gates APPROVED 2026-09-29
by the owner's "continue" following the explicit request to approve these
values. Approval freezes the targets and protocol; it is not a quality pass.
Wider-obstacle annotation and numeric gates remain open.

## Evaluation population

Use a prospectively declared, held-out sequence set that is disjoint from
component tuning and the sequence-08 baseline in experiment 0028. Keep raw
point order and fixed SemanticKITTI learning IDs. Publish evaluator revision,
split manifest, raw scan and annotation hashes, candidate configuration,
per-class counts, and zero-support strata. Do not treat a class with no ground
truth as a pass. Sequence 08 remains a diagnostic baseline because its results
were inspected before choosing these numbers.
The independent labeled final set has not been established. The public
SemanticKITTI test labels are hidden, so local range/size and wider-obstacle
audits need a separate reviewed annotation set or an approved blind evaluator.

For traffic participants (learning IDs 1..8), use the pinned official panoptic
evaluator, including its 0.5 segment IoU and minimum-instance-point policy.
Separately report one-to-one candidate/ground-truth matching at point-support
IoU >= 0.5 for GT instances with at least 50 annotated points. A candidate
matched once is one true positive; unmatched eligible truth is false negative;
unmatched candidate is false positive. Report false positives per 100 scans,
not per annotated object. Attribute each truth to range by its annotated
point median distance and to size by point count: 50-199, 200-999, >=1000.
Unmatched predictions use their own median range. Publish denominators and
95% bootstrap intervals by sequence; an interval is descriptive, not a
substitute for the gate. Empty or underpowered strata stay NOT VERIFIED.

## Approved traffic-participant numeric gates

All gates apply to the held-out set and must pass together. These are product
targets chosen after inspecting the sequence-08 development baseline.
They are requirements, not empirical claims about the current detector.

| Measure | Approved pass limit | Minimum support |
| --- | --- | --- |
| Official mean thing PQ, classes 1..8 | >= 0.65 | Every class represented; >= 100 eligible GT instances per class for per-class recall judgment |
| Per-class eligible recall, each class 1..8 | >= 0.70 | >= 100 GT instances; otherwise NOT VERIFIED |
| Eligible recall at 0-20 m and 20-50 m | >= 0.90 and >= 0.85 | >= 100 GT instances in each bin |
| Eligible recall at 50+ m | >= 0.70 | >= 100 GT instances |
| Eligible recall for 50-199, 200-999, >=1000 points | >= 0.85, >= 0.90, >= 0.90 | >= 100 GT instances in each bin |
| Unmatched thing candidates | <= 100 per 100 scans | >= 1,000 annotated scans |

The motorcyclist class and 50+ m bin already fail or lack support in the
sequence-08 diagnostic: official motorcyclist PQ was zero and eligible far
recall was 8/30. Raising either result by changing the scoring population
after inspection is prohibited.

## Independent wider-obstacle set

AC-002 also requires independently reviewed wall, pole, curb and overhang
annotations, including thin and partial-view cases. Record visible point
support, observed bounds, class or unknown, range, occlusion, and whether a
candidate is deliberately ambiguous. A reviewer must freeze the annotation
guide, minimum visible support, matching tolerance and safety-relevant unit
before numeric recall or false-positive gates for these categories can be
approved. SemanticKITTI's panoptic thing score cannot fill this gap. Until
that set exists, wider-obstacle AC-002 is NOT VERIFIED even if the traffic
participant targets above are approved and met. No curb clearance, solid
occupancy or passability claim follows from a matched candidate.

## Decision record

Traffic-participant numeric targets: APPROVED 2026-09-29. Wider-obstacle numeric targets:
UNDEFINED pending the independent annotation protocol. Full AC-002: OPEN.
This sheet does not authorize using sequence-08 results as final held-out
acceptance evidence or lower AC-008's zero-miss 100 ms deadline.
