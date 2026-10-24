# Decision 0012: G0 complete result and D-005 implementation contract

Date: 2026-10-24. Status: D-005 AND RESOURCE LIMITS APPROVED; COMPLETE-SCHEMA
AND RELEASE ACCEPTANCE PENDING.

## Context

The staged T-002 through T-006 slices have separate schemas, while the
diagnostic temporal map is not part of a receipt-validated product result. G0
needs one explicit complete-result boundary, executable D-005 rows and
resource ceilings before a release replay can be judged.

## Decision for implementation

The product owner approved D-005 v0.2 and all resource ceilings listed in this
decision on 2026-10-24. The unresolved-row policy is also approved: missing
independent evidence remains `not-verified` and cannot silently pass.

Implement `drishti-g0-v1` with product-result schema version 6 and stage
`complete`. A complete result is built only from the shared path after
candidate detection, tracking, current-scan visibility and temporal fusion.
It retains the versioned current-scan cell and beam proof payload and adds
immutable fused cells containing resolution ownership, elevation, occupancy,
terrain, flags, semantic evidence, obstacle envelope evidence, timestamps and
observation counts.

The complete result carries `d005-v0.2` and the resource-limit bundle as
provenance. The evaluator validates the complete fused arrays, nonoverlap,
summary conservation, provenance, tracking/visibility evidence and any
provided resource samples. Exceeding a declared limit is a rejection; missing
required final-evaluation samples remains not verified rather than silently
passing.

## D-005 boundary

The semantic values come from the draft D-005 v0.1 sheet and the traffic
participant values come from the approved AC-002 sheet. Unsupported-free
fixture output must remain zero. Independent range, wider-obstacle, terrain,
motion and held-out false-free values remain explicitly unresolved in code and
documentation. No synthetic run or inspected sequence-08 baseline is promoted
to final evidence.

## Resource boundary

The initial ceilings are 130,000 points, 12 GiB process RSS, 5,500 MiB device
memory, zero swap growth, 262,144 fused cells, 512 tracks, queue depth 2,
100 ms queue age, 2 MiB receipts, 8 MiB audit and 10 GiB free disk reserve.
They are a host-derived implementation baseline for the inventoried RTX 4050
laptop, not a measured AC-008 pass. The product owner approved them on
2026-10-24; a controlled complete-path pilot must now validate their measured
behavior.

## Consequences

- Schemas 1 through 5 retain their existing digest and validation behavior.
- The current CLI remains diagnostic/schema-5 when temporal fusion is enabled;
  the complete producer is available as a separate shared-path adapter until
  the release producer and calibration/resource sampling are integrated.
- D-005 v0.2 and the resource ceilings are approved and may be used for
  evaluation.
- G0 remains IN PROGRESS pending independent evidence, complete-producer
  integration and release validation.
