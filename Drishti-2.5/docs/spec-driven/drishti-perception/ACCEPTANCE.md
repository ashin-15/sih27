# Drishti-2.5 perception acceptance contract

Status: Draft, not frozen. Based on draft PRD and technical design dated 2026-09-24. Approval: Pending. Numeric thresholds and target platform are TBD under D-001/D-005. No item below is claimed as implemented.

## Release boundaries

The initial release scope is pending D-003/D-004. A release cannot claim learned perception, tracking, free space or real-time behavior because the current geometric/oracle demo passes. Every blocking criterion needs a saved command, configuration, dataset split, checkpoint hash and result artifact. If navigation use is selected, false-free and clearance gates become release blocking.

## Criteria

| ID | FR | Scenario and observable result | Evidence | Blocking |
| --- | --- | --- | --- | --- |
| AC-001 | 001, 009 | Replay held-out scans with labels inaccessible to the inference path. Output one aligned semantic ID/confidence per accepted original point; unknown is 0, not car. Report class IoU, mIoU by range and unknown coverage against frozen thresholds. | Point-order fixtures, label access guard, official evaluation output, manifest. | Yes |
| AC-002 | 002 | Replay wall, pole, curb, vehicle, pedestrian, overhang and partial-view fixtures. Detect instances with bounds and class/unknown; do not infer solid occupancy from a sparse vertical envelope. Meet frozen recall/false-positive limits by size and range. | Fixture traces, reviewed detections, metrics. | Yes |
| AC-003 | 003 | Revisit static cells under pose change, frame gap and repeated scan. Fuse evidence without duplicate growth, preserve nonoverlap at resolution seams, distinguish stale/unknown and reset across sequences. | State diffs, memory bounds, replay tests. | Yes |
| AC-004 | 004 | Follow multiple objects through crossing, short occlusion, disappearance and reappearance. Track IDs obey frozen lifecycle; report ID switches, fragmentation and false tracks. | Sequence traces and tracking metrics. | Yes |
| AC-005 | 005 | Ego vehicle moves past a static wall and a moving object. Wall speed remains within frozen tolerance; moving object receives velocity/uncertainty only with sufficient evidence; first frame stays unknown. | Motion fixtures, moving IoU and velocity-error report. | Yes |
| AC-006 | 006, 010 | Rays end before, at and beyond candidate cells; include no return, out-of-FOV and occluded cases. Only supported traversed cells become observed-free. No invalid case becomes free. | Ray fixtures and false-free metric on held-out scans. | Yes |
| AC-007 | 007 | Run a complete sequence and inspect manifest/frame/summary artifacts. Every frame records model, pose and evidence provenance, stage timings, drops, state age and memory; failure is reported, never silently omitted. | Schema validation and saved run artifacts. | Yes |
| AC-008 | 008 | On approved hardware, replay or ingest approved representative density and duration with model, fusion, viewer and audit enabled. Meet frozen end-to-end deadline, miss, memory and drop thresholds. | Reproducible benchmark logs and hardware inventory. | Yes |
| AC-009 | 009 | Compare geometric, learned and oracle modes using the same accepted points and map path. Oracle labels never enter learned prediction or tracking. Validation and final evaluation splits remain disjoint. | Split manifest, access tests, metric report. | Yes |
| AC-010 | 010 | Viewer and machine output distinguish occupied, observed-free, unknown, stale and ambiguous cells and show track/motion provenance. Unknown never appears drivable. | Output schema tests and real viewer recording inspection. | Yes |
| AC-011 | 011 | If live input is in scope, feed timestamped scans with calibration and pose quality; invalid or missing timing degrades explicitly. Deskew status is accurate. | Live-source fixtures and target sensor run. | Conditional |
| AC-012 | 001 to 011 | Existing tests, lint, format, type check and package build pass; a complete-path regression replay finishes from an installed wheel. | Commands, logs and wheel replay artifact. | Yes |

## Required threshold decisions

Freeze numeric targets for semantic classes and ranges, obstacle classes and sizes, motion/track quality, false-free rate, map freshness and capacity, target hardware, full-path deadline, miss rate and sample window. Until then this remains a draft; passing the existing 42 tests cannot satisfy this contract.
