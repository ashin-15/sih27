# 0003 - Version-1 product result and evaluator receipt

Status: DESIGN DECISION, staged T-002 contract, 2026-09-26.

## Context

The product owner approved the O-001 checklist and authorized staged implementation starting
with T-002. The existing `FrameResult` receipt only validates the current single-frame slice.
It cannot stand for the proposed complete product output or AC-008.

## Decision

Freeze the version-1 typed `ProductFrameResult` and `ProductReceipt` in
`Drishti-2.5/src/drishti/product_result.py` and the exact validation/canonical digest rules in
the T-002 technical design. The same-process evaluator receives the actual immutable arrays
and returns a timestamped acceptance or rejection receipt. A `diagnostic` result is adapted
from the existing geometric mapping path with explicit unknown/empty future fields. Its receipt
is schema evidence only. Future learned/temporal producers must populate the `complete` stage
and meet separate quality, audit, resource and deadline gates.

The selected release workload is complete SemanticKITTI sequences 08 and 00 at 10 Hz, plus
sequence 10 frame 206 as a separate cold-start case; raw scans over 130,000 points are explicit
rejects. CPU development proceeds now. A physical NVIDIA host, checkpoint/license, numeric
quality/resource thresholds and final release judgment remain open.

## Consequences

The optional CLI contract check produces version-1 diagnostic receipts in schema-3 frame audit
rows while preserving the older current-frame diagnostic timing path. It does not enable a
100 ms or real-time claim. Any incompatible payload change requires a new schema version.
Full-payload disk persistence, bounded audit fsync/drain, viewer coverage, fault recovery and
complete-path performance remain later tasks.
