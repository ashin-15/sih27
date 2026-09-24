# Experiment 0002: locate current replay costs

Status: MEASURED RESULT for the existing headless, geometric, single-frame path on 2026-09-24.
Question: RQ-004. Product features and release feasibility remain NOT VERIFIED.

## Reproduction and provenance

- Hardware: Intel Core Ultra 9 185H, 22 logical CPUs, approximately 30 GiB RAM, Linux
  7.2.6-1-cachyos x86_64. CPU scaling/power/thermal mode was not held constant or recorded.
- Git HEAD: `998e83ee4bc04769f98e73c20f97e900732300b1`, dirty working tree. Package source
  digest `fa72a9a15edfde2e40b9cc7ed3a9fe4c6da0bc74814fed805607355822f34b64`;
  config digest `ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`.
  Python 3.12.14, NumPy 2.5.3, pypatchworkpp 1.4.1.
- Dataset: SemanticKITTI sequence 08, frames 0-49, SLAM poses, geometric mode, no viewer.
  Input points per scan: min 119,593, median 123,386, max 124,125. All 50 frames passed
  input-point accounting. Metadata hashes and exact configuration are in the new manifest.
- Run from `Drishti-2.5/` with a fresh output directory:

```sh
uv run --frozen drishti replay --dataset /home/ashin/Hackathon/SIH/data/dataset --sequence 08 --mode geometric --output /home/ashin/Hackathon/SIH/Drishti-2.5/runs/drishti-profile-baseline-20260924-seq08-50 --view none --max-frames 50
```

The command completed, and the saved `manifest.json`, `frames.jsonl`, and `summary.json` are
in that run directory. To rerun, choose a different new output directory. The measurement
harness source is [`0002-profile-harness.py`](0002-profile-harness.py). It wraps existing
functions with `perf_counter` and runs a separate `cProfile` pass; it changes no production
source. The repeated 40-frame command was:

```sh
uv run --frozen python ../docs/research/experiments/0002-profile-harness.py --dataset /home/ashin/Hackathon/SIH/data/dataset --sequence 08 --frames 40 --output /tmp/drishti-profile-20260924-seq08-40-repro.jsonl
```

The harness excludes frame 0 from its percentile table. Its output JSONL includes frame IDs,
point accounting and digests. The separate profiler pass runs frames 0-11 with a new engine.
For frames 0-39, its input digests, map digests and accounting records exactly matched the
fresh CLI report, confirming that the timing wrappers did not change these outputs.

## Timings

The CLI 50-frame run reported 50/50 misses of the configured 100 ms budget. Its steady
`process` p50/p95 was 272.69/278.19 ms and audit-inclusive p50/p95 was 318.50/326.25 ms.
Observed throughput was 3.14 frames/s over 15.93 s; worker peak RSS was 198.1 MB. The
following CLI stage percentiles use frames 1-49 and linear interpolation:

| Stage | p50 ms | p95 ms | Timing boundary |
| --- | ---: | ---: | --- |
| Preprocess | 33.39 | 35.54 | Filtering, transform and aligned arrays |
| Ground | 25.23 | 26.06 | Patchwork++ plus output validation |
| Projection | 32.73 | 33.08 | Range image creation |
| Mapping | 180.99 | 186.18 | `aggregate_cells` plus observations/accounting assembly |
| Load | 26.31 | 27.28 | `next(frames)` scan/frame construction |

The repeated 40-frame harness measured `aggregate_cells` at p50/p95 180.75/185.96 ms,
while `mapping_ms` was 181.49/186.57 ms. The per-frame median residual was 0.77 ms. The
ownership calculation within aggregation cost p50/p95 17.74/18.48 ms. Separate CLI audit
work in the harness was input SHA-256 p50/p95 2.14/2.25 ms, snapshot digest 16.74/17.93 ms,
and JSON serialization/write/flush 0.12/0.13 ms. These are separate timed operations;
subtracting percentile values is not a valid way to derive a per-frame audit stage.

The snapshot digest is evaluated while building the CLI record, **after** `MappingEngine.process`.
It iterates over snapshot fields and hashes array bytes. It is not part of `mapping_ms`.
The input digest also hashes array bytes after processing. The small JSON write/flush timing
does not include these hashes. The CLI audit-inclusive metric also contains load, result
formatting, and miscellaneous loop work.

On 12 separately profiled frames, `cProfile` attributed 2.164 s cumulative to
`aggregate_cells`, of which 1.601 s was `np.unique(keys, axis=0)` and 1.550 s was the
underlying NumPy `ndarray.argsort`. This row-wise unique/sort is the dominant observed
hotspot. It accounts for roughly 74% of aggregation time in the profiled sample. In the
same pass, projection was 0.396 s and `resolve_owners` 0.217 s cumulative across 12 frames.
There were 420 calls to `immutable` with 0.054 s cumulative, about 4.5 ms per profiled frame;
this is a useful bound for copy work inside `process`, not an independently timed stage.

`cProfile` has call overhead and changes the runtime mix. Its 12-frame cumulative times
identify where work occurs; use the unprofiled CLI and timed harness for latency comparisons.
The independent 40-frame harness produced similar mapping and stage magnitudes to the CLI,
but the runs were sequential and not controlled for thermal or CPU scheduling variation.

## Next experiment

1. Prototype an alternative cell-key grouping algorithm in an isolated benchmark. Compare
   `np.unique` with integer-packed keys or a lexicographic grouping approach, only after
   proving no overflow or collisions across negative coordinates, all map levels and the
   configured coordinate bounds. Preserve inverse indices, cell ordering, ownership,
   point accounting and exact snapshot digest on held-out scans.
2. If grouping becomes faster, rerun the same 50-frame command with a fresh directory,
   then long and varied sequences. Check stage distribution, digests, memory and deadline misses.
3. Profile preprocessing/projection and audit only after addressing the larger grouping cost.
   Audit hashing is material for the CLI total but removing it alone cannot meet 100 ms.

No learned model, object detector, tracker, motion estimator, temporal fusion, free-space proof,
viewer, live sensor or planner path was present in this measurement. A 100 ms complete-path
deadline and sustained real-time behavior are NOT VERIFIED and are not met by the current slice.
