# Decision 0010: light per-frame receipt with sampled deep audit

Date: 2026-09-30. Status: ACCEPTED.

The owner said "approve the lighter receipt, stop the run and rerun" after
profiling showed the full same-process check cost about 3 s per real frame,
far more than any perception stage. This amends the receipt behaviour chosen
for D-001/decision 0002; publication is still the same-process receipt.

- Every receipt runs the light contract checks: identity and provenance, sealed
  canonical arrays, shapes/dtypes/ranges, point alignment, cell nonoverlap,
  tracking lifecycle and capacity, visibility summary and temporal claims, and
  that every free cell references a declared beam proof.
- The deep geometric re-verification (candidate bounds from raw points, beam
  return and corridor geometry, occupied-cell exclusion, conflict margin and
  point-to-cell reconstruction) runs on every N-th accepted frame
  (`--audit-every`, CLI default 100; library default 1). Each receipt records
  `deep_audit`.
- Schema 5 stores beam proofs as a columnar `BeamTable` (one frame origin) with
  an empty `beams` tuple, and its digest is a typed, length-prefixed SHA-256 over
  raw array bytes (`drishti-raw-digest-v1`). Schemas 1 to 4 keep their frozen
  canonical JSON digest and `beams` tuple.

Evidence: on 8 real sequence-08 frames on the release host, receipt time fell
from about 3.0 s to 0.47 s median with byte-identical predictions; all evaluator
rejection tests pass, including new tests showing a deep-only forgery passes a
light receipt and is rejected when audited. Risk: a geometric error on an
unaudited frame is caught only by the sampled audit or offline checks.
