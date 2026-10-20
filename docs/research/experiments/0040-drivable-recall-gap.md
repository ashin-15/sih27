# Experiment 0040: cause of the drivable recall gap

Date: 2026-10-05. Follows experiments 0038/0039 and open item O-013. Same pipeline,
host and labels-for-scoring-only rule as 0038. Script `0040-drivable-recall-gap.py`
attributes every missed labelled-drivable cell (label majority road/parking, terrain not
DRIVABLE) to the first failing decision-0011 rule. Outputs
`exp0040-recall-gap-seq08-{2000,0}-250-20261005.json` in
`C:\Users\Robin Joe\drishti-local\artifacts\`.

## Results (MEASURED RESULT, share of labelled-drivable cell observations)

| Cause | 2000-2249 | 0-249 |
| --- | ---: | ---: |
| Labelled parking, FRNet (current scan) says another class, mostly sidewalk | **14.3%** | 0.1% |
| Labelled road, FRNet says another class | 1.2% | 1.1% |
| Labelled road, FRNet right now but fused history class wrong | 0.3% | 0.4% |
| Obstacle from memory only (no current non-ground return; bottom p50 0.84 m) | 2.3% | 0.8% |
| Obstacle in a mixed cell (current returns of another class, e.g. car edge) | 1.4% | 0.6% |
| Obstacle from non-ground returns on road-labelled points | 0.9% | 0.2% |
| Curb/drop flag inside the road (all labelled neighbours drivable) | 0.3% | **1.4%** |
| Curb/drop flag at a labelled road edge | 0.1% | 0.1% |
| Total missed | 21.0% | 4.6% |

- FRNet on points labelled road/parking predicts sidewalk 16.5% of the time in
  2000-2249 versus 0.9% in 0-249. Its full-sequence parking IoU is 0.537 (road 0.959,
  sidewalk 0.839; experiment 0035).
- Interior false curbs: step p50 0.13 m; 72% (0-249) and 67% (2000-2249) are below
  0.15 m and 95% / 83% below 0.20 m, just above the 0.10 m limit.
- Non-ground returns on road points: obstacle bottom p50 0.004 m (2000-2249) and
  0.11 m (0-249) above the Kalman ground, i.e. ground-level returns that Patchwork++
  called non-ground.

## Conclusion

The 0.79 recall in frames 2000-2249 is mainly a **FRNet semantic error: parking lots
predicted as sidewalk** (14.3 of the 21.0 points missed). Fusion, Kalman and terrain
geometry are minor contributors there. Where FRNet is good (0-249), the largest loss is
**false interior curb flags** from the tight 0.10 m step limit, then remembered obstacles.

## Candidate fixes (not applied; thresholds need D-005 approval)

1. Parking/sidewalk: model-side (fine-tune or a stronger checkpoint), or an owner rule
   for flat, flag-free ground connected to road. Treating sidewalk as drivable is not
   acceptable without a decision.
2. Interior curbs: require the step to exceed the limit plus the cells' combined Kalman
   sigma, or raise the limit to about 0.15-0.20 m; re-score curb recall at labelled edges.
3. Ground-level non-ground returns: ignore obstacle returns within the step limit of
   the Kalman ground when judging blocking.
4. Remembered obstacles: faster ghost clearing or the T-018 motion layer.
