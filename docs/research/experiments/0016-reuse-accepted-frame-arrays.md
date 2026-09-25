# Experiment 0016: reuse immutable frame arrays when all points are accepted

Status: MEASURED RESULT for the current geometric slice, 2026-09-25. RQ-004,
O-001/T-008. This is a local exact-output optimization, not a complete-product
release benchmark.

## Setup and change

Both prior 100-frame SemanticKITTI sequence 08 and 00 replays accepted every
input point. `ScanFrame` already owns immutable point and original-ID arrays, but
`MappingEngine.process` indexed and copied both even when the accepted indices
covered the full frame. The engine now reuses those two arrays in that case and
keeps the existing filtered-copy path for any rejected point. Point order and
ownership are unchanged. The unit suite includes filtered and immutable result
fixtures; no source dataset file was modified.

The candidate source digest is
`4c726ea553ad74d8751dd3747111239f8c91fb68dc4b827438ab7676aa620d2a`.
The same default config digest
`ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`
was used on the selected Core Ultra 9 185H laptop.

Run from `Drishti-2.5/` into a fresh directory:

```sh
uv run --frozen drishti replay --dataset ../data/dataset --sequence 08 \
  --mode geometric --output runs/NEW-REUSE-RUN --view none \
  --max-frames 100 --check-100ms
```

The same command was run for sequence 00. A 50-frame sequence 00 oracle replay
used `--mode oracle` without the paced check. Each new `frames.jsonl` record was
compared with the corresponding saved pre-change run on frame ID, input/map
digest, cell count and accounting.

## Result

| Run | Exact pre-change outputs | Preprocess p50 before/after | Audited work p50 before/after | Deadline result |
| --- | ---: | ---: | ---: | --- |
| [Sequence 08 geometric](../../../Drishti-2.5/runs/drishti-o001-reuse-frame-arrays-seq08-100-20260925/) | 100/100 | 14.84/12.19 ms | 110.71/108.35 ms | 100/100 misses; age p50 605.09 ms |
| [Sequence 00 geometric](../../../Drishti-2.5/runs/drishti-o001-reuse-frame-arrays-seq00-100-20260925/) | 100/100 | 14.49/11.95 ms | 100.04/98.93 ms | 82/100 misses; age p50 137.18 ms |
| [Sequence 00 oracle](../../../Drishti-2.5/runs/drishti-o001-reuse-frame-arrays-oracle-seq00-50-20260925/) | 50/50 | Not compared | 111.91/108.87 ms | Not paced |

The new sequence 08/00 summaries and timing sidecars agreed on miss counts and
contiguous IDs. Sequence 00 had 18 passing scans, but the accepted gate requires
zero misses; its p95 audited work was 110.19 ms. The first scan is counted.
Runs were sequential; temperature, cache and background load were not controlled.

Focused pipeline tests passed (10), then the full suite passed (51). Ruff lint,
format and mypy passed. The package source and wheel build succeeded after an
initial sandbox cache-lock failure; an isolated offline cache lacked setuptools,
and the approved build with the existing cache completed. No build warning was
ignored.

## Judgment

MEASURED RESULT: reusing validated immutable frame arrays preserves sampled
outputs and lowers preprocessing time, but strict 100 ms replay still fails on
both tested sequences. The model, detection, temporal state, final output and
approved publication boundary are absent. O-001 remains IN PROGRESS and AC-008
remains NOT VERIFIED.
