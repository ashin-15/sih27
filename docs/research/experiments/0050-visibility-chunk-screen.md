# Experiment 0050: CUDA visibility beam-batch screen

Date: 2026-10-15. RQ-004 / R-SYSTEM; T-008 and O-006. This screen tests an
internal batch-size change with the same current result schema and evaluator.

## Setup

Windows 11, NVIDIA GeForce RTX 4050 Laptop GPU (6,141 MiB), driver 561.00,
Python 3.12.14, pinned FRNet checkpoint SHA-256
`09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`.
Power state was not controlled. The four runs used the same process and the
first six real sequence-08 scans in order 8,192 / 16,384 / 16,384 / 8,192.
Each used learned CUDA mapping and FRNet, candidates, tracking, visibility,
diagnostic temporal fusion, sampled schema-5 deep audit, and no viewer. From
`Drishti-2.5/`, reproduce into a new output directory with:

```text
.venv/Scripts/python.exe ../docs/research/experiments/0050-visibility-chunk-screen.py <new-output-directory>
```

The local reports are retained in
`artifacts/visibility-chunk-screen-20261015/run{0,1,2,3}-*`. Each frame had
80,833 to 81,786 qualifying beams, crossing both tested batch boundaries.

## Results

| Run | Batch | Warm visibility p50/p95 | Steady processing p50/p95 | Wall time |
| --- | ---: | ---: | ---: | ---: |
| 0 | 8,192 | 887.2 / 984.7 ms | 2,899.8 / 2,956.2 ms | 35.80 s |
| 1 | 16,384 | 773.8 / 977.4 ms | 2,684.5 / 2,980.4 ms | 30.78 s |
| 2 | 16,384 | 754.7 / 836.6 ms | 2,744.3 / 2,865.3 ms | 29.65 s |
| 3 | 8,192 | 1,295.4 / 1,750.5 ms | 3,984.1 / 4,209.2 ms | 38.55 s |

MEASURED RESULT: all 24 current schema-5 receipts were accepted, and each
run missed the configured audit-inclusive 100 ms budget on all six frames.
Corresponding frame IDs, input/map digests, accounting and visibility
summaries matched across runs. A CUDA regression with 11,000 authored ground
points exceeded 8,192 qualifying beams and matched every visibility evidence
array and summary between both batch sizes. A separate CPU boundary fixture
also matched full evidence arrays for 4,096/8,192 and 8,192/16,384 pairs.

The second 8,192 run slowed substantially despite reverse ordering, so this
small screen does not establish a stable percentage gain or tail guarantee.
The 16,384 batch was faster in both pairs and is retained as an exact-output
current-path optimization. Peak process RSS, device memory and scratch
allocation were not measured. The optional diagnostic fused map remains CPU;
neither this result nor the batch setting establishes a full GPU pipeline or
AC-008 release acceptance.
