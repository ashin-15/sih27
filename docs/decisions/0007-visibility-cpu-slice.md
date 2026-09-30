# Decision 0007: bounded CPU current-scan visibility

Date: 2026-09-29. Status: ACCEPTED for the bounded implementation scope.

The owner replied "approve all four and continue" to the four approval points
in the [T-006 contract](../t-006-visibility-proposal.md):

1. First slice is current-scan only; temporal fusion, STALE and AC-003 are
   deferred to a later slice.
2. Schema 5 (`stage=visibility`) extends the learned CPU candidate/tracking
   path.
3. Ground-only cells stay UNKNOWN, preserving the frozen schema-1 rule that a
   free cell contains no accepted return.
4. Development defaults: `tau_free = 0.10 m`, `corridor_max_m = 5.0 m`,
   `conflict_margin_m = 0.30 m`, `max_free_cells = 65,536`, raised by the owner on
   2026-09-30 to 262,144 after real sequence-08 frames needed about 131k-146k.

Observed-free is evidence only: a ground-terminated current beam crossed the
cell interior at no more than `tau_free` above its return, with no conflicting
return nearby. It is not clearance, drivability or navigation proof. The
numeric false-free gate (O-003/D-005), AC-003, AC-008 and AC-010 remain open.
No new runtime dependency or external service is introduced.

Evidence limit at approval: the active workstation has no SemanticKITTI data,
voxel labels, saved runs or Python toolchain. Fixture tests need a Python 3.12
toolchain; the sequence-08 replay and false-free report need the dataset with
voxel files on a data host.
