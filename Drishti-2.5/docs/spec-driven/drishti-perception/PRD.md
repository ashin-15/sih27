# Drishti-2.5 perception product requirements

Status: Draft, awaiting product decisions. Updated: 2026-09-24. Approval: Pending.

## Problem and goal

The current standalone application maps one LiDAR scan at a time. It cannot infer semantic classes, objects, motion, persistent state, or observed free space without ground-truth labels. It records a budget but cannot claim a deadline guarantee. The goal is a versioned, testable perception-to-map pipeline for repeated LiDAR frames, with unknown and unsupported evidence explicit.

## Users and flow

The immediate users are developers evaluating SemanticKITTI replay and operators inspecting a local 2.5D dashboard. A future navigation consumer is conditional on validated free-space, clearance and freshness contracts. The expected flow is: load an ordered frame and pose; infer point labels; detect obstacle candidates; update motion and tracks; fuse into bounded map state; publish evidence with provenance, uncertainty and latency.

## Functional requirements

| ID | Requirement | Status |
| --- | --- | --- |
| FR-001 | In geometric production mode, predict a semantic learning ID and confidence or unknown for every accepted original point, without reading evaluation labels. | Draft |
| FR-002 | Detect obstacle instances with stable object type, bounded geometry and evidence provenance; preserve small/thin objects and ambiguous height cases. | Draft |
| FR-003 | Fuse ordered frames in a bounded local map using poses and timestamps; distinguish observed, stale and unknown evidence and reset on a new sequence. | Draft |
| FR-004 | Assign and maintain object track IDs across visible frames, occlusion and reappearance, with explicit confidence and expiry. | Draft |
| FR-005 | Estimate motion relative to the world from sequential observations; publish velocity/uncertainty or unknown. Semantic class and oracle motion labels may not substitute for measured motion. | Draft |
| FR-006 | Publish conservative occupied, observed-free and unknown evidence. Missing returns, occluded areas and out-of-FOV cells remain unknown; a free-space claim requires valid ray evidence. | Draft |
| FR-007 | Publish clear per-frame provenance: model and checkpoint, pose source, point attrition, dropped frames, stage timing, evidence age, state memory, viewer costs and release-gate result. | Draft |
| FR-008 | Meet a user-approved deadline on user-approved target hardware for the complete replay/live path under a specified load and measurement window. | BLOCKED by target hardware and deadline decision |
| FR-009 | Keep oracle labels isolated to evaluation, preserve the original point order, and evaluate semantic, obstacle, motion, tracking, free-space and latency quality on held-out sequences. | Draft |
| FR-010 | Expose unknown, stale and ambiguous states in the viewer and machine output without silently turning them into drivable space. | Draft |
| FR-011 | State whether live sensor input and navigation integration are part of the first release, and support the needed timestamp, calibration and deskew contract if they are. | BLOCKED by deployment decision |

## Success measures

Baseline: no measured learned accuracy, tracking, free-space quality, or full-pipeline latency. Targets for semantic mIoU, obstacle recall by size/range, moving IoU, track ID switches, false-free rate, maximum evidence age, peak memory and deadline miss rate are TBD. They must be frozen before implementation acceptance. Synthetic demo and oracle scores are not substitutes.

## Data and use rules

- Keep raw scans and labels read-only. Training uses training sequences only; validation and final evaluation must be held out. The official SemanticKITTI tasks and API define label formats and benchmark metrics: https://semantic-kitti.org/tasks.html and https://github.com/PRBonn/semantic-kitti-api.
- Preserve the 0 unknown/ignored and 1..19 learning-ID convention at every point and cell boundary.
- Do not publish a navigation-safe verdict from a height envelope or from a missing return. Stationary objects remain collision obstacles.
- Record checkpoint, configuration, code and dataset provenance for every evaluated run.

## Scope and non-goals

In scope: the existing Python package, its CLI, deterministic replay, model adapter and training/evaluation tools, rolling local map, viewer and performance gate. Autonomous route planning and global georeferencing are out of scope. A navigation-ready output is conditional on an explicit product decision and stronger acceptance tests.

## Open product decisions

| ID | Decision | Recommendation | Affected requirements |
| --- | --- | --- | --- |
| D-001 | Target hardware, input rate, complete-path deadline and allowed miss rate. | Development target selected: current Core Ultra 9 185H machine, 10 Hz and up to 130,000 SemanticKITTI points per scan; 100 ms capture-to-published-output engineering goal. Release deadline, miss policy and vehicle hardware remain TBD. | FR-008 |
| D-002 | First model milestone: semantic-only, joint semantic/motion, or checkpoint integration before training. | Integrate a versioned semantic checkpoint first, then measure a motion model separately. | FR-001, FR-005, FR-009 |
| D-003 | Free-space output for evidence only or navigation consumption in the first release. | Evidence-only until false-free and recovery behavior are validated. | FR-006, FR-010 |
| D-004 | Dataset replay only or live LiDAR and planner integration in the first release. | Replay first, then add a timed live source after contracts are proven. | FR-008, FR-011 |
| D-005 | Numeric release thresholds for every success measure. | Set thresholds after a baseline on held-out data and target hardware; do not infer them from the synthetic demo. | FR-001 to FR-010 |

## Decision log

2026-09-24: The user selected the current machine for development and delegated provisional
workload and latency choices to measured tests. Two 100-frame real-data replays and a 22-sequence
structure check support the D-001 development profile above. The current path missed 100 ms on
every measured frame, so the 100 ms number is an engineering goal, not an achieved requirement or
release approval. See `docs/research/experiments/0001-replay-baseline-protocol.md` and
`docs/research/hardware-targets.md`. D-001's release branch and D-002 to D-005 remain open; the
PRD, design and acceptance contract are not frozen.
