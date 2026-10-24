# Decision 0012: G0 complete result and D-005 implementation contract

Date: 2026-10-24. Status: SUPERSEDED FOR DETAIL BY [DECISION 0013](0013-g0-complete-result-quality-resource-release-freeze.md).
The schema, D-005 policy, resource envelope and release protocol are frozen;
acceptance remains pending.

## Context

The staged T-002 through T-006 slices have separate schemas, while the
diagnostic temporal map is not part of a receipt-validated product result. G0
needs one explicit complete-result boundary, executable D-005 rows,
resource ceilings and a release replay protocol before a release replay can
be judged. Decision 0013 freezes those details.

## Decision for implementation

The product owner approved D-005 v0.2, all resource ceilings listed in this
decision and the release-protocol boundary on 2026-10-24. The unresolved-row
policy is also frozen: missing independent evidence remains `not-verified` and
cannot silently pass. Decision 0013 is authoritative for the complete field
inventory, stable failure codes, the GPU allocated/reserved split, candidate
and logical-map limits, and run-stop behavior.

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

The semantic values come from the D-005 v0.1 sheet and the traffic participant
values come from the approved AC-002 sheet. Unsupported-free fixture output
must remain zero. Independent range, wider-obstacle, terrain, motion and
held-out false-free rows are frozen as blocking `not-verified` until their
independent protocols exist. No synthetic run or inspected sequence-08
baseline is promoted to final evidence.

## Resource boundary

The initial ceilings are 130,000 points, 12 GiB process RSS, 5,500 MiB each
for GPU allocated and reserved memory, a 64 MiB logical fused-map allocation,
262,144 fused cells, 512 tracks, 8,192 candidates, queue depth 2, 100 ms
queue age, 2 MiB receipts, 8 MiB audit, zero swap growth and 10 GiB free disk
reserve. They are a host-derived implementation baseline for the inventoried
RTX 4050 laptop, not a measured AC-008 pass. The product owner approved them
on 2026-10-24; a controlled complete-path pilot must validate their measured
behavior.

## Consequences

- Schemas 1 through 5 retain their existing digest and validation behavior;
  decision 0013 freezes the compatibility boundary for schema 6.
- The current CLI remains diagnostic/schema-5 when temporal fusion is enabled;
  the complete producer is available as a separate shared-path adapter until
  the release producer and calibration/resource sampling are integrated.
- D-005 v0.2, the resource ceilings and the release protocol are frozen and
  may be used for implementation and evaluation.
- G0 remains IN PROGRESS pending independent evidence, complete-producer
  integration, controlled target-host samples and release validation.
