# Production readiness roadmap and SIH26053 cross-check

Status: IN PROGRESS planning record, 2026-10-13. This is a delivery plan, not a
release approval or evidence that the 100 ms gate is met. The first release scope
in the current product contract is evidence-only SemanticKITTI replay on the
identified RTX 4050 laptop. Live input and planner-facing output are later work.
The owner has been asked to confirm those two boundaries.

## Release claim and measurement boundary

The proposed release claim is one complete, immutable, versioned result per
ordered scan, accepted by the same-process evaluator within 100 ms of scheduled
10 Hz arrival, with zero misses, drops, invalid receipts or unbounded backlog.
Count the first scan. The selected future workload is complete sequences 08 and
00 plus the sequence-10 frame-206 density boundary; record source, checkpoint,
driver, power mode, configuration and audit behavior. Rerun display and full
payload disk persistence have separate measurements. See
[the contract proposal](o-001-contract-proposal.md) and AC-008 in the
[acceptance criteria](../Drishti-2.5/docs/spec-driven/drishti-perception/ACCEPTANCE.md).
Freeze the remaining quality and resource thresholds under D-005 before claiming
acceptance. No shortened run, warmed subset, mean latency or configured budget
can stand in for this gate.

MEASURED RESULT: The current learned GPU path takes roughly 0.7-1.1 s per
frame before receipt in the recorded development work; the optional CPU temporal
stage adds p50 168-273 ms on two 250-frame chunks. Earlier receipt validation
itself took about 0.47 s per real frame after the light-receipt change. These
measurements differ in workload and configuration and cannot be summed into a
valid full-path benchmark. They show that AC-008 is currently failed or NOT
VERIFIED, not close to a demonstrated 100 ms pass. See
[experiment 0035](research/experiments/0035-t006-gpu-sequence08.md),
[experiment 0038](research/experiments/0038-temporal-drivability.md), and
[the work log](work-log.md).

A fresh three-frame complete-current-path diagnostic on 2026-10-13 measured
1,452 ms steady processing p50 with accepted current schema-5 receipts; see
[experiment 0041](research/experiments/0041-production-path-short-baseline.md).
It is a short, unpaced baseline and does not replace the AC-008 protocol.

MEASURED RESULT: a 2026-10-14 paired 30-frame CPU synthetic screen kept every
base-map digest and accounting record equal, while diagnostic temporal fusion
cost 324.454 ms p50 and 583.305 ms p95. Published fused cells grew from
15,576 to 164,214. An exact neighbour-index candidate saved only about
12.5 ms in isolated late-frame calls and was not integrated. See
[experiment 0044](research/experiments/0044-temporal-cost-and-neighbour-screen.md).
This adds a concrete G3 bottleneck but no release benchmark.

## Critical path

| Gate | Work and exit evidence | Dependencies / approval |
| --- | --- | --- |
| G0: freeze release contract | Resolve D-005 semantic, obstacle, motion, terrain, false-free and resource limits; freeze complete fused result schema, failure behavior and remaining measurement details. The 130,000-point cap and release windows are selected. Keep diagnostic results separate from release claims. | T-001; product-owner acceptance of numeric gates and material interface changes. |
| G1: correctness and quality | Finish T-003 checkpoint provenance; independent final semantic/candidate/tracking evaluation; add measured motion (T-005/T-018), terrain slope/drop/overhang evidence (T-017), and conservative temporal visibility (T-006). Prove unknown remains unknown and moving objects do not become static map evidence. | G0 quality definitions; final labels and motion evidence. Each stage needs fixtures, held-out metrics and source/wheel replay. |
| G2: map and output | Complete T-015 speed/direction foveation and T-016 fixed-capacity layered store with exact merge/split, nonoverlap and accounting; publish fused cells, motion and provenance in the complete evaluator schema; finish T-007/T-019 viewer and memory comparison. | Frozen interface and foveation weights; parity with the current CPU reference. The existing 53.7 MB diagnostic temporal store is a starting point, not T-016 acceptance. |
| G3: 100 ms feasibility | Profile a representative complete frame, including model, Patchwork++, map, visibility, temporal update, transfers and evaluator. Remove dominant costs with device-resident or native implementations while keeping exact contract checks. Run paced 10 Hz increasing windows, then both complete sequences and density boundary, with stage tails, queue age, RSS/VRAM and failure audit. | G1/G2 complete result; RTX 4050 on recorded power/driver state. Any replacement model or changed quality tradeoff returns to G0/G1. |
| G4: release judgment | Pass every blocking AC, lint/format/mypy/tests/build, installed-wheel replay, artifact reopening and digest checks, representative dashboard inspection, final quality and zero-miss complete-path run. Record a signed release decision and limitations. | G0-G3. The local Windows/Linux CI workflow is defined, but its first hosted run and CI/deployment/security ownership policy (O-009) must be resolved for a production release. |

DESIGN HYPOTHESIS for G3: instrument first, then set a per-stage tail budget
whose sum, evaluator and scheduling overhead included, is below 100 ms. The
current FRNet and visibility timings already exceed the whole deadline, so
small local optimizations cannot establish feasibility. Test GPU residency,
batching, compact proof representation, native ground segmentation and fused
map kernels as isolated candidates. Keep a CPU reference and measure parity,
quality, peak memory and p99/max on real scans after each change. If the
complete result cannot meet the gate on the selected host, record a failed
feasibility decision and seek an explicit platform, workload or deadline change;
do not relabel a slower run as production grade.

## SIH26053 requirement cross-check

Review this table at least weekly during active development, at each gate above,
and whenever a result schema, algorithm, model or performance claim changes.
Record the evidence link and status change in the dated work log and task/open-item
registers. A weekly review with no new evidence records "no status change";
it does not silently promote a requirement.

| Problem-statement requirement | Current evidence | Remaining acceptance work |
| --- | --- | --- |
| Deep-learning semantic segmentation of terrain and objects | FRNet learned point semantics; sequence-08 mIoU 0.675469 reference and 0.675473 GPU runtime. | D-005 quality gates, independent final sets, checkpoint terms and distance-stratified quality (T-003). |
| Drivable versus non-drivable terrain; curbs, potholes and overhangs | Diagnostic fused terrain states and curb/drop/overhang flags; two chunk IoUs 0.943/0.782. | Resolve parking/sidewalk confusion and false interior curb flags; slope, pothole and overhang truth; approve thresholds and include terrain in validated output (T-017). |
| Static obstacles and dynamic pedestrians/vehicles | Observed-point candidates and known-thing association exist; velocity and motion state remain unknown. | Full held-out object and tracking gates, measured world motion, static/moving map layer and ghost control (T-004/T-005/T-018). |
| Variable resolution 2.5D elevation/semantic grid with no alignment loss | Per-scan 5/10/50 cm cells use exact ownership and all accepted points; a fixed 53.7 MB diagnostic fused store exists. | Speed/direction foveation, exact ownership/merge/split as rings move, full-sequence bounded memory and output parity (T-015/T-016). |
| Colour-coded real-time dashboard | Rerun semantic and diagnostic terrain/occupancy/elevation/free-space layers; recording verified. | Owner visual inspection, motion and memory-comparison layers, separate display latency/FPS measurement (T-007/T-019). |
| Significant memory reduction versus uniform fine 3D map | Experiment 0036 measured per-scan adaptive cell-count comparisons; fused store allocation is fixed in sampled runs. | Same-workload measured process/device memory and an explicit fair uniform 3D baseline, with accounting of layers and limits (T-016). |
| Low latency and high classification accuracy across distance | Range-stratified semantic metrics exist; the current full path exceeds 100 ms. | Approved range/quality gates and G3/G4 complete-path zero-miss evidence (T-008). |

## Checkpoint record for each development loop

1. Name the SIH row, FR/AC ID, task and current approval scope before work.
2. Save a baseline and define one falsifiable change, including exact-output and
   conservative-evidence invariants.
3. Run focused fixtures, CPU/CUDA parity where applicable, then relevant real
   scans and package checks. Inspect receipts and artifacts.
4. Compare the SIH row and every affected AC with the new evidence. Update the
   task board, open items, interfaces/decision if changed, and dated work log.
5. Promote a gate only when its complete stated evidence passes; otherwise keep
   the gap open with the next experiment and owner decision clearly identified.

No production gate is marked complete by creating this roadmap.
