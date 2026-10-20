# Experiment 0044: diagnostic temporal cost and exact neighbour screen

Date: 2026-10-14. RQ-004 / R-SYSTEM; T-008 and O-006. This is a CPU
synthetic diagnostic, not an AC-008 release benchmark.

## Setup and reproduction

Windows 11, Intel Family 6 Model 186, Python 3.12.14, NumPy 2.5.3,
pypatchworkpp 1.4.1. Both runs used the same working tree, default mapping
config, seed 26053, 30 synthetic plane/wall frames of 21,000 points each,
geometric mode, no model, candidates, tracking, visibility, evaluator or
viewer. The runs were unpaced and sequential; power and thermal state were
not controlled. Source reports are retained at:

- `Drishti-2.5/runs/synthetic-no-temporal-screen-1791965850168`
- `Drishti-2.5/runs/synthetic-temporal-screen-1791965858559`

From `Drishti-2.5/`, reproduce with new output directories:

```text
.venv/Scripts/python.exe -m drishti demo --output <reference> --view none --frames 30
.venv/Scripts/python.exe -m drishti demo --output <temporal> --view none --frames 30 --temporal
.venv/Scripts/python.exe ../docs/research/experiments/0044-temporal-pair-summary.py <reference> <temporal>
.venv/Scripts/python.exe ../docs/research/experiments/0045-temporal-update-profile.py --frames 30 --profile-last 5
.venv/Scripts/python.exe ../docs/research/experiments/0046-temporal-neighbor-screen.py --frames 30 --repeats 10
```

The paired-summary script rejects any mismatch in frame ID/time, input/map
digest, accounting or snapshot cell count. All 30 pairs matched. Temporal
allocation was 53,737,911 bytes in every frame; published cells grew from
15,576 to 164,214. This is fixed retained allocation, not peak process RSS
or temporary scratch memory.

## Results

| Unpaced reported duration | p50 | p95 | max |
| --- | ---: | ---: | ---: |
| No-temporal processing | 37.839 ms | 46.627 ms | 69.796 ms |
| With-temporal processing | 412.537 ms | 694.266 ms | 769.606 ms |
| Temporal stage alone | 324.454 ms | 583.305 ms | 630.851 ms |

MEASURED RESULT: an isolated `cProfile` of temporal updates on the last five
synthetic frames ranked `_view` at 1.598 s cumulative of 2.065 s total,
including `_steps` 0.576 s and `_owned` 0.353 s; `_fuse_points` cost 0.361 s.
Profiler durations are ranking evidence, not uninstrumented latency.

An isolated candidate replaced the four toroidal neighbour-index calculations
in `_steps` with direct slot offsets. On the final synthetic state, all rise
and drop arrays matched exactly at each level. Ten repeated calls per level
measured reference/candidate 22.400/21.257 ms for 33,362 level-0 cells,
87.072/75.778 ms for 119,276 level-1 cells, and 6.833/6.784 ms for 11,576
level-2 cells. The sum of these isolated differences is about 12.5 ms per
full late-frame step evaluation. It is insufficient to resolve the observed
324 ms temporal median, let alone the complete learned release path, so this
candidate was not integrated. Timing order and one-state scope limit any
speedup claim.

## Judgment

FACT: the current diagnostic temporal output scales in compute with the
number of published cells even though retained allocation is fixed. No
cell, label, map-digest or accounting mismatch was found in the paired screen.
HYPOTHESIS: avoiding whole-view reconstruction or changing the complete output
layout could reduce cost, but either needs exact payload parity and the
complete-result contract first. T-008/O-006 remain IN PROGRESS; this result
does not establish a 100 ms path or justify dropping cells.
