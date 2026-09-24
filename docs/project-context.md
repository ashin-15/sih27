# Project context

Updated 2026-09-24. Status labels distinguish current code from plans.

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
to 130,000 points per scan. A 100 ms capture-to-published-output goal is proposed but unmet by
the current path. UNKNOWN: release hardware/deadline policy, model milestone, free-space use,
live sensor scope, quantitative quality gates and release policy. See `docs/project-assessment.md`
and `docs/execution-plan.md`.
