# Experiment 0038: fused terrain, Kalman elevation and drivability on sequence 08

Date: 2026-10-05. Decision 0011. Host: release host (decision 0009), on AC power
with the Balanced plan; other applications open. Code: working tree after
decision 0011 (uncommitted).

## Runs

1. `drishti replay` learned CUDA path with candidates, tracking, visibility,
   `--temporal`, `--audit-every 100`, `--view record`, frames 0-99. Output
   `C:\Users\Robin Joe\drishti-local\artifacts\t006-temporal-seq08-100-20261005`
   (outside OneDrive). 100 frames completed and `rerun rrd verify` passed (1.23 GB
   recording). This run used the first, unoptimised fused map: temporal stage p50
   517 ms, total p50 1,508 ms.
2. `0038-temporal-drivability.py`, frames 0-249 and 2000-2249 (two fresh engines,
   every receipt accepted, optimised code). Labels come from a separate ORACLE
   source and are read only for scoring. Outputs
   `exp0038-drivability-seq08-{0,2000}-250-20261005.json` in the same folder.

Scoring: each published fused cell holding current-scan points is compared with the
majority label of those points: drivable = road/parking, non-drivable ground =
sidewalk/other-ground/terrain, obstacle = every other known class, unlabelled
excluded. Cells are counted once per frame, so a cell seen in many frames counts
many times.

## Results (MEASURED RESULT)

| Frames | Drivable precision | Drivable recall | Drivable IoU | False drivable on obstacle cells | False drivable on non-drivable ground | Obstacle recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0-249 | 0.9883 | 0.9536 | 0.9430 | 0.10% | 0.44% | 0.837 |
| 2000-2249 | 0.9871 | 0.7896 | 0.7816 | 0.09% | 0.92% | 0.937 |

- By level (frames 0-249): 5 cm IoU 0.965, 10 cm 0.912, 50 cm 0.675. Frames
  2000-2249: 0.780 / 0.793 / 0.706.
- In frames 2000-2249, 319,391 cell observations labelled drivable were judged
  NON_DRIVABLE (17% of drivable truth). The cause is UNKNOWN: this evaluation does
  not separate FRNet road/sidewalk confusion from curb/drop flags on road.
  HYPOTHESIS: both contribute; a flag-level breakdown is the next check.
- Kalman ground sigma over valid cells (sampled): p50 0.020 m, p95 0.030 m.
  With the decided process noise (0.0025 m^2/s) the filter reaches a steady state
  after about three scans at 10 Hz (fixture test), so it smooths but does not
  average long histories.
- STALE never appeared in the scored cells (scored cells are observed in the
  current scan by construction). Run 1 showed STALE cells in the published map
  (e.g. 15,605 at frame 99).
- Fixed allocation: 53.7 MB for the three windows, constant over every frame.

## Latency (MEASURED RESULT, not a real-time claim)

The optimised temporal stage (counting-based grouping, integer ownership,
neighbour gathers only for published cells, uint8 semantic evidence) took p50
273 / 168 ms and p95 397 / 249 ms per frame in the two chunks, with one 9.7 s
stall in frames 0-249 (HYPOTHESIS: paging under memory pressure). Whole-frame
total p50 942 / 711 ms. The stage runs on the CPU and is not part of any 100 ms
claim (AC-008 still fails).

## Limits

The fused map is a diagnostic layer, not part of the receipt-validated product
schema. Thresholds are the decision-0011 values, not tuned or owner-approved
under D-005. Labels score current-scan points only; there is no pothole or overhang
ground truth, so curb/drop/overhang flags are fixture-verified only. No motion
layer (T-018), so moving objects leave occupancy ghosts until ground-only or
free-beam evidence clears them.
