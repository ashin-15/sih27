# 0013: bounded CUDA temporal neighbour workspace

Date: 2026-10-22. Status: accepted internal exact-output optimization under the
owner's instruction to begin the feature-preserving workflow.

CUDA temporal maps use one fixed-capacity workspace and a fused four-neighbour
kernel; CPU remains the reference and Python default. CLI `--device cuda`
selects the CUDA neighbour step when temporal diagnostics are enabled.
Host fusion and output remain synchronous, and existing terrain rules remain
unchanged. Unknown remains unknown; no feature is removed to reduce timing.

GPU buffers are owned by the sequence map and reused across levels. Manifest
reports their bytes separately from existing host-array allocation. No fallback
silently changes the requested backend. The current diagnostic fused arrays
remain outside the receipt schema.

Evidence and limits: [0055](../research/experiments/0055-temporal-cuda-screen.md).
The isolated improvement does not demonstrate full-frame latency or quality
acceptance. Continue bounded residency, visibility, model and receipt work.
