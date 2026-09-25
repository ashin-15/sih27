# Experiment 0014: exact all-unknown cell evidence path

Status: MEASURED RESULT for the current geometric slice, 2026-09-25. RQ-004,
O-001/T-008. This is not a complete-product release benchmark.

## Setup and change

The selected Core Ultra 9 185H laptop replayed read-only SemanticKITTI sequences
08 and 00, frames 0-99, in geometric mode with default config digest
`ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`.
The 40-frame [current-path profile](0014-profile-seq08-40.jsonl), taken before the
change on source digest `7ae2b2ce550d08ee215f61473bfb62c682f6f8691486325fb576d332b0dd175f`,
had aggregate-cell p50 47.72 ms, owner resolution p50 10.75 ms, and snapshot
digest p50 16.90 ms. `cProfile` also showed semantic tie/count reductions inside
aggregation. Profile instrumentation adds overhead and is not the release clock.

`aggregate_cells` now constructs the exact all-unknown semantic evidence and motion
arrays directly when both input arrays contain only zero. Oracle or other nonzero
inputs continue through the generic histogram and motion logic. The change keeps
the dense `MapSnapshot` schema and its digest bytes intact. Candidate replay source
digest: `ea32d53d1893d89e617bd73bb0f385ac3f7f7fc29351b7278b68bd1ab3ab5b07`.

Run from `Drishti-2.5/` into a fresh output directory:

```sh
uv run --frozen drishti replay --dataset ../data/dataset --sequence 08 \
  --mode geometric --output runs/NEW-UNKNOWN-PATH-08 --view none \
  --max-frames 100 --check-100ms
```

The same command was run for sequence 00. A separate 50-frame sequence 00 oracle
replay omitted `--check-100ms` and used `--mode oracle`. Each candidate frame was
compared with the prior same-sequence baseline on ID, input/map digests, cell count
and accounting. A further 100-frame run used the separate scheduled producer in
[experiment 0013](0013-independent-producer-replay.md) with a two-frame queue.

## Result

| Run | Exact baseline outputs | Mapping p50 before/after | Audited work p50 before/after | Deadline result |
| --- | ---: | ---: | ---: | --- |
| [Sequence 08 geometric](../../../Drishti-2.5/runs/drishti-o001-unknown-fastpath-seq08-100-20260925/) | 100/100 | 47.60/37.16 ms | 120.31/110.71 ms | 100/100 misses; age p50 800.74 ms |
| [Sequence 00 geometric](../../../Drishti-2.5/runs/drishti-o001-unknown-fastpath-seq00-100-20260925/) | 100/100 | 41.29/33.45 ms | 108.41/100.04 ms | 100/100 misses; age p50 220.80 ms |
| [Sequence 00 oracle](../../../Drishti-2.5/runs/drishti-o001-unknown-fastpath-oracle-seq00-50-20260925/) | 50/50 | 42.93/42.44 ms | 112.97/111.91 ms | Not paced |
| [Separate producer, sequence 08](../../../Drishti-2.5/runs/drishti-o001-unknown-fastpath-independent-seq08-100-20260925/) | 100/100 | Not recorded | Not recorded | 100/100 misses; 89 queue-full events; age p50 836.07 ms |

The separate producer's load-start lag p50 was 403.51 ms and maximum output age
was 1338.65 ms. It blocked on a volatile queue, so it did not sustain 10 Hz source
loading. It does not prove live capture or durable no-loss behavior.

A post-change [40-frame profile](0015-profile-seq08-40.jsonl) measured aggregate-cell
p50 37.52 ms and snapshot-digest p50 17.11 ms. Its 12-frame `cProfile` pass still
ranked packed grouping, owner resolution, immutable array copies and projection as
current-slice costs. These are diagnostic timings with instrumentation overhead.

Focused mapping/pipeline tests passed (18), then the full suite passed (51).
Ruff lint/format, mypy and source/wheel build passed. The saved `frames.jsonl`
records of all four candidate runs matched their baseline frames exactly.

## Judgment and limits

MEASURED RESULT: the all-unknown path reduces sampled mapping and audited work
while preserving exact outputs, but the current geometric path still fails every
tested strict 100 ms deadline. Sequential local runs do not control cache, thermal
state or unrelated load. The learned, detector, temporal and final publication
stages remain absent; AC-008 and the complete release gate remain NOT VERIFIED.
