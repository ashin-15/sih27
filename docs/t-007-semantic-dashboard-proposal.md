# T-007 semantic dashboard class visibility proposal

Status: IMPLEMENTED and ACCEPTED for the bounded semantic dashboard slice on 2026-09-29.
Owner: product owner for behavior; engineering for implementation details.
Related task: T-007 viewer, audit and machine contract.

## Problem

FACT: the dashboard opened for the 200-frame replay used `--mode geometric`.
Geometric mode deliberately assigns every accepted point semantic learning ID 0
(`unknown`), so its Semantics tab cannot show inferred classes.

FACT: the current `RerunView` already publishes a `world/semantics/cells`
layer. It attaches semantic IDs 0 through 19 and a static `AnnotationContext`
containing the canonical SemanticKITTI names and colors. This colors each cell
by its dominant point class. The current dashboard does not make the legend,
class populations, per-cell conflict meaning, or distinction from raw-point
classes prominent in the visible evidence panel.

## Proposed bounded product scope

DESIGN DECISION PROPOSAL: make the existing label-free learned semantic evidence
discoverable in the dashboard without adding a new model, changing class IDs,
or using oracle labels.

| ID | Requirement | Status |
| --- | --- | --- |
| SD-FR-001 | In learned mode, the Semantics view shows the existing dominant cell class using canonical IDs 0 through 19, class names and colors. | Draft |
| SD-FR-002 | The evidence panel shows a readable legend and deterministic accepted-point and cell counts for classes present in the frame. | Draft |
| SD-FR-003 | Unknown ID 0, tied cells and cells containing multiple known classes stay explicit. A dominant cell label is never represented as a uniform point-level label. | Draft |
| SD-FR-004 | Geometric mode remains all unknown. Oracle labels remain evaluation-only and are not required for the learned dashboard. | Draft |

In scope: existing Rerun semantic-cell rendering, class legend, per-frame
counts and evidence wording.

Out of scope: changing FRNet, adding labels to geometric mode, point-level
semantic rendering, per-class filtering controls, candidate/track UI, temporal
map state, motion, occupancy/free-space claims and changing the machine-output
contract.

## Decision frontier

### SD-D-001 - visual granularity

Which evidence should the dashboard render as the primary class visualization?

| Option | Outcome | Cost and risk |
| --- | --- | --- |
| A | Dominant semantic class per existing map cell, plus accepted-point and cell count summary. | Recommended. Reuses the immutable snapshot, makes aggregation and conflicts visible, and avoids recording another full point cloud. |
| B | Add class-colored accepted raw points in addition to cell classes. | More literal point evidence, but adds up to every accepted point per frame to the viewer recording and needs a separate performance/resource check. |
| C | Add interactive per-class filtering and statistics controls. | Requires Rerun UI/blueprint capability validation and a larger UX contract. |

Recommendation: **A**. It matches the single-frame map dashboard's existing
cell view, has no new semantic data contract, and preserves clear aggregation
limits. Point counts still disclose the underlying predicted evidence.

### Resolved scope decision

PRODUCT DECISION: the product owner selected **Option A - dominant cell classes
with a legend and counts** on 2026-09-29. This approves the proposed bounded
scope for specification. It does not approve runtime or test implementation.

## Technical plan after scope approval

1. **Freeze UX and acceptance.** Add the selected SD-FR requirements and
   acceptance criteria to the current T-007 records. Keep all unknown,
   conflict and aggregation wording literal. No full-release or real-time
   claim follows from this viewer-only change.
2. **Implement one semantic summary path.** In `visualization.py`, derive
   accepted-point counts from `FrameResult.observations.semantic` and cell
   counts from `MapSnapshot.semantic`; include only nonzero counts. Use
   `CLASS_NAMES` and the existing `_semantic_palette()` as the single canonical
   class registry. Show the full legend and present classes in the evidence
   document; mark `semantic_conflict` and tied/unknown cells separately.
3. **Preserve current class rendering.** Keep `world/semantics/cells`,
   `class_ids=snapshot.semantic`, and the Rerun `AnnotationContext`. Do not
   modify `MapSnapshot`, `MappingEngine.process`, prediction files or the
   evaluator schema.
4. **Regression coverage.** Add deterministic learned-mode fixture coverage
   for class name/color/ID alignment, absent-class omission, unknown, tie and
   multi-known-class conflict wording. Keep the existing `.rrd` verification
   test. Do not test Rerun internals or hard-code viewer text layout.
5. **End-to-end proof.** Run a fresh learned, label-free replay with a supplied
   pinned FRNet environment/checkpoint, spawn or record Rerun, inspect the
   semantic tab and evidence panel at a frame with known classes, and save the
   run artifact. Measure viewer recording size and publication/flush time
   separately from the 100 ms evaluator gate.
6. **Durable records.** Update `docs/interfaces.md`, T-007 status, open-item
   register, work log and the existing product specification only with observed
   evidence. If the design expands to raw points or interactive filtering,
   revise this proposal and obtain renewed approval first.

## Bounded acceptance criteria

| ID | Scenario | Required observable evidence |
| --- | --- | --- |
| SD-AC-001 | Publish a learned fixture with known, unknown, tied and mixed-class cells. | The semantic view uses canonical annotation labels/colors; the evidence panel reports correct point and cell counts and explicitly reports unknown/tied/conflict states. |
| SD-AC-002 | Publish geometric and oracle fixtures. | Geometric mode reports all unknown. The learned dashboard does not depend on oracle annotations. |
| SD-AC-003 | Record a fresh learned replay. | `rerun rrd verify` passes; manual viewer inspection confirms a known class in the Semantics view and panel; manifest records learned model provenance. |
| SD-AC-004 | Inspect the timing report from SD-AC-003. | Viewer publication/flush evidence is recorded separately; no result claims it meets the 100 ms release deadline. |

## Verification and judgment

- SD-AC-001: PASS. `tests/test_visualization.py` builds a learned fixture with
  known, unknown, tied and mixed-known-class cells. It verifies canonical
  legend name/color/ID alignment, accepted-point and dominant-cell counts,
  conflict count and tied-to-unknown wording.
- SD-AC-002: PASS. The same fixture confirms geometric mode reports only
  unknown while learned and oracle display equivalent canonical class evidence.
  Existing learned tests retain the no-oracle-access invariant.
- SD-AC-003: PASS. A fresh one-frame learned label-free sequence 08 recording
  at `/tmp/drishti-dashboard-classes-20260929` completed; `rerun rrd verify`
  accepted `map.rrd`. Its manifest records the FRNet checkpoint/export hashes
  and pinned source revision. Manual Rerun inspection showed the added Semantic
  class legend tab and Semantic evidence panel.
- SD-AC-004: PASS. The recording summary reports 10.140105 ms final viewer
  flush and 7,957.294079 ms single-frame CPU processing. Its release gate is
  false; this is viewer evidence, not a 100 ms claim.

Judgment: **ACCEPTED** for SD-AC-001 through SD-AC-004 only. Full T-007 and
AC-007/010 remain blocked by their independent contracts and evidence.

## Approval boundary

The product owner approved implementation of this selected scope on 2026-09-29.
Any extension to raw class-colored points, interactive filters, model behavior,
or the machine-output contract requires a revised specification and approval.
