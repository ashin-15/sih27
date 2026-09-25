# Decision: CUDA host for the replay release gate

Status: Accepted
Date: 2026-09-25
Scope: Release-platform direction, with separately dated viewer and replay-output selections below; the full product specification remains draft.

## Context

O-001 requires a strict 100 ms deadline for every scheduled replay scan, with zero misses in
the accepted window. The earlier release-machine choice was this Core Ultra 9 185H laptop.
The user subsequently selected a CUDA frame path. This laptop exposes Intel Arc graphics and
an NPU, with no NVIDIA CUDA device, so it cannot execute or validate that path.

## Problem

The previously selected release host cannot execute the CUDA implementation direction.
Keeping that host as the CUDA acceptance machine would make AC-008 untestable.

## Options Considered

Keep the Intel laptop as the release host and treat CUDA as experimental; move the replay
release gate to an NVIDIA CUDA host; or abandon the selected CUDA direction.

## Decision

The first CUDA-backed replay release gate will run on an identified NVIDIA CUDA host. The
current Intel laptop remains the CPU development baseline and parity reference; it is no
longer the release acceptance machine for the CUDA-backed 100 ms goal. Dataset replay,
scheduled-arrival-to-complete-output timing, and zero allowed deadline misses remain the
selected scope and deadline policy. A physical host, GPU model, driver, memory and power
configuration must be recorded in the acceptance manifest before the gate runs.

## Reasoning

A CUDA implementation cannot make a deadline claim on hardware that cannot execute it.
Historical vrgrid timing on an RTX 5050 laptop shows the approach is worth testing, while
its T4 free-running p99 exceeded 100 ms. Neither result predicts Drishti's complete-path
latency on a new host. Keeping the CPU path allows contract and output comparisons.

## Consequences

- Do not choose an NVIDIA GPU solely by VRAM size or a historical benchmark. Obtain access
  to a specific host and measure the approved workload before claiming AC-008.
- CUDA execution must be explicit; selecting it without a usable device must fail clearly.
  CPU mode remains runnable on the current laptop.
- The complete-output consumer and publication event, workload/window, viewer participation,
  resource ceilings, model and quality gates still need a frozen contract. This decision does
  not approve production implementation or establish a real-time guarantee.

## 2026-09-25 clarification

DESIGN DECISION: the user excluded Rerun recording and display from the strict 100 ms
deadline. Measure their costs separately. The complete machine-output handoff remains
inside the deadline; its consumer and receipt event are still open.

## 2026-09-25 handoff-review output selections

DESIGN DECISION: the product owner selected a same-process evaluator as the first-release
machine consumer. Publication is its receipt after validating the complete versioned immutable
product result, timed from scheduled arrival on the same monotonic clock. Every accepted scan
must receive that acknowledgement within 100 ms. Persist receipts and audit evidence;
full-payload disk persistence is not part of this endpoint. A digest-only report, queued result
or receipt for the current geometric slice cannot substitute for the complete future payload.

DESIGN DECISION: first-release output is evidence-only for evaluation and visualization.
Planner-facing output and navigation-safe or drivable-space verdicts are deferred beyond this
release. Unknown/stale states and evidence-quality tests remain required.

DEFERRED by the product owner: approval of the proposed full-sequence workload, measurement
window and 130,000-point cap. Physical host selection remains deferred. Payload schema,
model and numeric quality/resource gates remain open; these selections do not freeze the
PRD/design/acceptance contract or authorize the broader product implementation. The alternative
persisted-writer and external-consumer endpoints were not selected for this release.

## 2026-09-25 CPU-first implementation clarification

DESIGN DECISION: the product owner selected the current laptop CPU as the active
implementation and execution target. Keep NVIDIA CUDA support optional for later use;
NVIDIA access is not expected soon and must not block CPU-side development or verification.
Physical NVIDIA selection/access and GPU-specific validation are deferred.

This settles implementation hardware, not complete-path acceptance. It does not demonstrate
a CPU 100 ms pass, approve a new release workload or resolve payload/quality/resource gates.
The earlier CUDA-backed acceptance direction remains a future validation requirement, not a
prerequisite for approved CPU-only implementation slices. Do not silently treat CPU tests as
CUDA evidence or CUDA unavailability as a reason to stop all project development.

## Rejected Alternatives

Keeping this laptop as the CUDA release host cannot validate a CUDA path. Abandoning CUDA
would contradict the selected implementation direction. Neither alternative resolves the
100 ms complete-path gate.

## Evidence

Local `lspci -nn` and absent `nvidia-smi` on 2026-09-25; the CUDA direction and proof boundary
in `docs/o-001-cuda-frame-path.md`; historical timings in
`vrgrid-26/docs/gpu-lane/13-PS-SCHEDULE.md` and `vrgrid-26/docs/gpu-lane/t4/timing_cuda.log`.
Linked requirements: FR-008/FR-011, AC-008/AC-012, RQ-004 and T-008.
