# Experiment 0039: single-scan versus fused terrain

Date: 2026-10-05. Question (owner): does temporal fusion earn its cost? Decision 0011.
Host and power state as experiment 0038.

## Method

`0039-single-vs-fused-terrain.py`: one learned CUDA engine (candidates, tracking,
visibility, every receipt accepted) per chunk. The same frame inputs (points, ground
classes, FRNet semantics, free cells) update (a) the sequence-long `TemporalMap` and
(b) a fresh `TemporalMap` each frame: identical rules with no history (allocation
excluded from timing). Scoring as experiment 0038, plus flicker (cells published in
consecutive frames whose state or drivable verdict changes) and area within 20 m of
the sensor with a drivable or any known verdict. Frames 0-249 and 2000-2249 of
sequence 08. Outputs `exp0039-single-vs-fused-seq08-{0,2000}-250-20261005.json` in
`C:\Users\Robin Joe\drishti-local\artifacts\`.

## Results (MEASURED RESULT)

| Metric | Single 0-249 | Fused 0-249 | Single 2000-2249 | Fused 2000-2249 |
| --- | ---: | ---: | ---: | ---: |
| Drivable precision | 0.984 | 0.988 | 0.984 | 0.987 |
| Drivable recall | 0.974 | 0.954 | 0.807 | 0.790 |
| Drivable IoU | 0.959 | 0.943 | 0.797 | 0.782 |
| False drivable on obstacle cells | 0.09% | 0.10% | 0.09% | 0.09% |
| Obstacle recall | 0.922 | 0.837 | 0.949 | 0.937 |
| State change rate between frames | 29.7% | 3.6% | 25.5% | 3.0% |
| Drivable flip rate between frames | 12.5% | 1.2% | 14.8% | 1.1% |
| Drivable area within 20 m, p50 (m^2) | 35 | 181 | 25 | 144 |
| Known area within 20 m, p50 (m^2) | 225 | 851 | 132 | 487 |
| Update time p50 (ms) | 210 | 287 | 130 | 182 |

## Interpretation

- Per-cell accuracy on currently observed cells is about the same; single-scan is
  slightly higher on recall/IoU (+0.015 to +0.021) and obstacle recall.
- Fusion makes the map about 10x more stable (drivable flips 12-15% -> about 1%)
  and gives 3.7-5.7x more known area and 5-6x more drivable area near the vehicle,
  because cells hidden or not hit in the current scan keep their last verdict.
- The 2000-2249 recall gap appears in single-scan too, so it is not caused by
  fusion (O-013 remains: FRNet confusion or curb/drop flags).
- HYPOTHESIS for the lower fused obstacle recall in 0-249: fused ground history lets
  canopy-like returns 2 m or more above ground become overhang rather than obstacle.
  Not verified.
- Cost: with this implementation single-scan is not cheap (130-210 ms) because the
  per-scan grouping, Kalman and terrain work dominate; history adds about 50-80 ms.
  A truly cheap single-scan terrain would reuse the snapshot cells; not built.
