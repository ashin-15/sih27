# Project context

Updated 2026-09-25. Status labels distinguish current code from plans.

## Identity and users

FACT: `SIH26053.md` asks for learned LiDAR perception and a variable-resolution 2.5D map. `Drishti-2.5/` is the standalone Python implementation. Current consumers are its CLI, JSON run reports and optional Rerun viewer. A navigation consumer is proposed, not implemented.

## Current system

FACT: Python 3.12, NumPy, pypatchworkpp, optional Rerun SDK, uv lockfile. `DatasetSource` reads SemanticKITTI scans, timestamps, calibration, poses and optional oracle labels. `MappingEngine.process` filters and transforms points, segments ground, projects an auxiliary range image, then aggregates accepted points into one-frame adaptive 2.5D cells. `MapSnapshot` is read-only and carries counts, height statistics, semantic evidence and motion status. CLI emits `manifest.json`, `frames.jsonl`, `summary.json` and optional `.rrd`.

FACT: No runtime database, external API, cloud service, container deployment or CI configuration is tracked. There is a repository-level dataset validation script. Raw dataset and model files are ignored. Live sensor protocol, security model and deployment environment are UNKNOWN.

## Limits and terms

FACT: Geometric mode returns semantic/motion unknown; oracle mode uses dataset labels. No trained model, object detector, persistent map, tracker, measured motion, free-space proof, clearance/passability output or real-time guarantee exists. Pose is supplied, not estimated. Per-point timing/deskew is unavailable.

`accepted point`: a scan point passing geometry, ROI and height filters. `projection winner`: point selected for a range pixel; non-winners still enter mapping. `unknown`: unsupported evidence, not free. `oracle`: ground-truth semantic/motion labels used for evaluation, not autonomous inference. `snapshot payload`: logical array bytes, not RSS.

## Stable constraints and unresolved questions

FACT: Semantic IDs are 0 unknown/ignored and 1..19 classes; frames and timestamps increase within one engine sequence; original point IDs are retained; source data is read-only. See `docs/interfaces.md`.

DESIGN DECISION for development: use the current Core Ultra 9 185H machine, 10 Hz replay and up
to 130,000 points per scan as the CPU baseline. DESIGN DECISION for the first CUDA-backed release:
dataset replay on an identified NVIDIA host, with a 100 ms publication deadline per scheduled
scan and zero misses in the accepted window; live sensor input is deferred. This laptop has no
CUDA device and remains the CPU parity reference. Its current path fails the deadline.
DESIGN DECISION: publication is a same-process evaluator receipt for the complete versioned
immutable result; persist receipts/audit, with full-payload disk persistence outside that endpoint.
DESIGN DECISION, later clarification: the current laptop CPU is the active implementation and
execution target, with optional CUDA support for later use. NVIDIA access must not block
approved CPU-only development; only GPU-specific validation is deferred.
Output is evidence-only; planner-facing use is deferred. Workload/window/cap approval is explicitly
deferred. UNKNOWN: physical NVIDIA host, complete payload schema, resource limits, model milestone,
quantitative evidence-quality gates and release policy. See
`docs/decisions/0002-cuda-replay-release-platform.md`, `docs/o-001-release-profile.md` and
`docs/execution-plan.md`.
