# Experiment 0042: visibility GPU chunk-size screen

Date: 2026-10-13. Question: RQ-004; module: R-SYSTEM; task: T-008.
Host and checkpoint: RTX 4050 laptop and pinned FRNet checkpoint of
[experiment 0041](0041-production-path-short-baseline.md). Power state and
concurrent load were not controlled. This is an internal throughput screen,
not AC-008 or a full product result.

## Method

Run the same first six sequence-08 frames twice from a fresh engine with learned
CUDA FRNet, candidates, tracks, current-scan visibility, diagnostic temporal
fusion, light schema-5 receipt, `--audit-every 100` and no Rerun view. Only
`visibility._BEAM_CHUNK` changes from 4,096 to 8,192. Both runs use the
experiment-0041 CLI options and distinct ignored output directories:

- `artifacts/visibility-chunk4096-20261013-6f`
- `artifacts/visibility-chunk8192-20261013-6f`

Every receipt was accepted. Compare corresponding frame map digests and
visibility summaries. The product-result digests include run identity/timing,
so separate output directories do not give directly comparable digests.
A regression fixture additionally compares every visibility evidence array
and summary with 4,100 authored beams across the 4,096 boundary.

## Results (MEASURED RESULT)

| Metric, warm frames 1-5 | 4,096 | 8,192 |
| --- | ---: | ---: |
| Visibility median | 501.7 ms | 449.2 ms |
| Whole-frame processing median | 1,308.6 ms | 1,278.6 ms |
| Six-frame wall time | 14.83 s | 14.23 s |
| Accepted current receipts | 6/6 | 6/6 |
| Configured 100 ms audit-inclusive budget misses | 6/6 | 6/6 |
| Peak snapshot array bytes | 15,679,615 | 15,679,615 |

All six map digests and visibility summaries matched. The authored 4,100-beam
fixture matched exact occupancy, obstacle support, free-cell levels/indices,
ray support, supporting beam IDs and summary between chunk sizes. The stage
timing was noisy (frame 1 regressed), so the median change of 52.5 ms is a
short-run observation, not a guaranteed speedup. Peak process RSS and VRAM
were not measured; equal snapshot bytes do not establish equal scratch memory.

The same six-frame post-change report records current schema-5 evaluator
validation durations of 547-703 ms on warm frames. A separate instrumented
two-frame cProfile run placed receipt validation in cell/visibility checks
and digesting. These are diagnostic timings with different instrumentation;
the evaluator itself also needs a redesign or major optimization for AC-008.

## Conclusion and next action

The 8,192 chunk is retained as a small exact-output GPU-path optimization.
Visibility alone still exceeds 100 ms, and the current path is more than an
order of magnitude above the release deadline. Next profile the device
sampling/key-packing kernels and transfers on controlled warm frames; evaluate
a device-resident or fused corridor implementation against the CPU reference
and held-out false-free evidence before another release claim.
