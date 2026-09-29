# Decision 0006: bounded CPU association and AC-002 traffic gates

Date: 2026-09-29. Status: ACCEPTED for the bounded implementation scope.

The owner said "continue" after the explicit request to approve the concrete
AC-002 traffic-participant values and bounded T-005 contract. Record both as
approved. [AC-002 targets](../ac-002-quality-gates-proposal.md) remain unmet or
unverified; independent wider-obstacle labels/gates are still open.

Implement the [T-005 contract](../t-005-tracking-proposal.md) under AC-016:
known observed thing association, bounded sequence-owned lifecycle, schema-4
receipts and transactional tracker state. Use the fixed geometric gate and
fixture expectations recorded before code. Keep velocity/covariance unknown.
Full AC-004/005 quality and AC-008 remain separate. The current candidate
interface is sufficient to develop this stage while full T-004 quality stays
open. No new external service, model or runtime dependency is needed.

Main-agent ownership: tracking module, shared pipeline, product result,
CLI, focused tests, offline association evaluator and relevant documentation.
Preserve all prior T-004 edits and existing schema 1-3 behavior.
