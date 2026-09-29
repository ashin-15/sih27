# Decision 0005: bounded CPU obstacle candidates

Status: Accepted for T-004 implementation, not full AC-002 acceptance.
Date: 2026-09-28.

## Context

FRNet supplies point-aligned semantic evidence through the shared engine. Cell
height envelopes are not objects. The product owner asked to compare three
T-004 approaches; [screen 0027](../research/experiments/0027-t004-option-comparison.md)
found no measured quality winner.

## Decision

The product owner said, "yes i approve the proposed bounded CPU candidate and
complete t-004". Implement the [bounded candidate proposal](../t-004-obstacle-candidate-proposal.md)
using a replaceable semantic/geometry detector on accepted points. Emit
frame-local observations with original support IDs, observed 3D bounds,
class/unknown, explicit ambiguity and no calibrated uncertainty claim.
Version the result as schema 3 `stage=candidate`; preserve schema 1 and 2.
Keep motion, tracks, free-space and planner claims absent. Score panoptic thing
instances separately from wider thin/curb/overhang fixtures.

## Reasoning and alternatives

DESIGN DECISION: this gives a local CPU baseline that can represent the wider
obstacle vocabulary using existing inputs. Thing-only clustering omits parts
of FR-002; a learned panoptic model has a locally pinned checkpoint but its
published inference path is CUDA-specific and has not been run here. No
accuracy or latency superiority is inferred.

## Consequences and gates

AC-015 governs the bounded implementation and measurement slice. AC-002
remains open until numeric size/range recall and false-positive gates and an
independent labeled obstacle set are approved and met. AC-008 remains NOT
VERIFIED. Detector candidate bounds describe observed returns, never a
filled collision volume, clearance, free-space or navigation-safe output.

## Evidence

RQ-006, E-053/E-054, [comparison 0027](../research/experiments/0027-t004-option-comparison.md),
the source/wheel and held-out measurements in experiment 0028, and focused
candidate/evaluator tests. The measurement record is updated after execution.
