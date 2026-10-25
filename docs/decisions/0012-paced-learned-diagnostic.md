# Decision 0012: paced learned diagnostic receipt timing

Date: 2026-10-22. Status: engineering diagnostic implemented under the owner's
request to reduce overall frame latency. No complete-product release approval.

## Problem

FACT: `--check-100ms` previously rejected learned mode. Its geometric endpoint
acknowledged a current-frame consumer before the optional product evaluator.
Unpaced learned reports therefore could not measure scheduled-arrival age
through the learned result's validation. Reusing that earlier endpoint for
learned replay would omit product construction, validation and digest cost.

## Decision

Allow label-free learned replay with `--check-100ms`. Pace scans at the existing
10 Hz schedule, count the first scan and retain every subsequent scheduled
arrival even when processing is late. Record completion only after the current
schema-2/3/4/5 product evaluator accepts the result and any tracking commit
finishes. Do not also invoke the geometric consumer. A rejection still fails
the run; a deadline miss returns exit code 2. Oracle mode and Rerun remain
excluded from this check. No stage is disabled to meet the budget.

Paced learned runs use **report schema 8**, identify the endpoint as
`current-product-inprocess-receipt-diagnostic`, and identify the consumer as
`in-process-current-product-evaluator`. Existing product schemas and digests,
unpaced report schemas, and the geometric timing endpoint are unchanged.
Frame `receipt_ms` includes product construction through accepted handoff;
`load_process_receipt_ms` includes scan loading. The timing JSONL measures
scheduled-arrival age, while report flush age remains separately reported.

## Limits and validation

The enabled temporal stage executes inside processing, so its compute time is
included; its fused arrays still are **outside** the product receipt schema.
Initialization before the first scheduled scan is outside this diagnostic
clock, while first-scan inference/kernel costs are included. Optional prediction
exports occur after receipt and can delay later scans. This is a serial replay
schedule, not a live ingress or queue implementation. The release flag remains
false regardless of the diagnostic outcome.

Authored semantic fixtures exercise the real mapper/evaluator for both schema 2
and schema 5, including tracking and temporal computation. An injected 125 ms
evaluator delay must produce receipt ages 125/150/175 ms, three misses, accepted
receipts and exit code 2. Geometric pacing and oracle/viewer rejection fixtures
remain in the suite. Real source and installed-wheel results are recorded in
[experiment 0051](../research/experiments/0051-exact-path-screen.md).
