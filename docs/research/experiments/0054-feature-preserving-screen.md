# 0054: feature-preserving configuration screen

2026-10-22; RQ-004, T-008/O-006. MEASURED RESULT, diagnostic only.
Reproduction: run `0054-feature-preserving-screen.py <new-output> --frames 12`
from Drishti-2.5 using its environment. Saved evidence:
`artifacts/feature-preserving-screen-20261022/` (commands, environment before/after,
source diff, checkpoint hash, predictions, manifests, receipts and screen.json).
RTX 4050 6 GB, Windows, battery power. Sequence 08 first 12 scans per fresh
process, pinned FRNet, learned CUDA mapping, detection, association, visibility,
CPU temporal terrain, evaluator, audit-every 100 and paced 100 ms check enabled.

| Variant | Warm load-through-receipt p50 ms | Model p50 ms | Changed point labels vs reference | Matching terrain summaries |
| --- | ---: | ---: | ---: | ---: |
| FP32 reference | 1642.65 | 213.75 | 0 | 12/12 |
| FP16 | 1459.59 | 140.97 | 1873 | 0/12 |
| FP32 GPU interpolation | 1478.67 | 171.24 | 10 | 12/12 |
| FP16 GPU interpolation | 1370.80 | 113.93 | 1885 | 0/12 |
| FP32 repeat | 1458.36 | 196.27 | 0 | 12/12 |

Each variant covered 1,479,013 points. All 60 current-product receipts accepted;
all 60 deadlines missed. Fused arrays are outside the current receipt schema.
Matching summaries do not establish array parity. Label differences do not
measure accuracy. Reference timing drift prevents a controlled speedup claim.

DESIGN DECISION: keep FP32/CPU interpolation defaults. Quality scoring is needed
before adopting precision/interpolation changes. This screen retains terrain,
tracking and visibility; it does not meet 100 ms or close any release gate.

Next: controlled AC-power trace and exact-output GPU workspace work in the
[workflow](../../sub100ms-workflow.md). The script now exercises whatever
temporal implementation is in the checked tree; this recorded run predates
the CUDA neighbour integration in experiment 0055.
