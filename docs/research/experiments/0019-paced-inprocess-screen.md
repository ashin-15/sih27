# Experiment 0019: paced current-result screen without in-loop audit I/O

Status: MEASURED RESULT for the current geometric slice, 2026-09-25.
RQ-004, O-001/T-008. This is a research screen, not the approved output
consumer or a complete-path release benchmark.

## Question and setup

The saved paced CLI runs include snapshot digest and JSONL audit work before
starting the next scan. Experiment 0018 reconstructed an optimistic earlier
clock endpoint from those runs, but the audit still delayed later scans. This
screen schedules 100 SemanticKITTI scans at 10 Hz on the selected Core Ultra 9
185H laptop, loads each frame and calls the same `MappingEngine.process` path.
It immediately checks the returned current-slice result's sequence/frame
identity, input/accepted point counts and point-to-cell alignment. The receipt
timestamp follows that minimal check. It buffers timing records in memory and
writes JSONL and summary files only after the 100-scan loop. No map digest,
versioned full-product schema, external consumer, viewer or durable output is
included. Dataset loading and any accumulated schedule lag remain inside each
scan's measured age. The first scan is counted; there is no scan warmup.

The saved [harness](0019-paced-inprocess-screen.py) has SHA-256
`2f9209ef11a32d9f270fd4955e193595d70b1dab33510ea6b5eac24aff3e323f`.
Both runs used read-only `../data/dataset`, geometric mode, SLAM poses, the
default config digest
`ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`,
and runtime source digest
`4c726ea553ad74d8751dd3747111239f8c91fb68dc4b827438ab7676aa620d2a`.
Runs were sequential; laptop load and temperature were not controlled.

From `Drishti-2.5/`, use a new output directory for each run:

```sh
uv run --frozen python ../docs/research/experiments/0019-paced-inprocess-screen.py \
  --dataset ../data/dataset --sequence 08 --frames 100 \
  --output runs/NEW-INPROCESS-SCREEN-08
```

The same command with sequence 00 and a different output path produced the
second saved report.

## Result

| Metric | [Sequence 08](../../../Drishti-2.5/runs/drishti-o001-inprocess-screen-seq08-100-20260925/) | [Sequence 00](../../../Drishti-2.5/runs/drishti-o001-inprocess-screen-seq00-100-20260925/) |
| --- | ---: | ---: |
| Receipt-age deadline misses | 2/100, IDs 0 and 1 | 3/100, IDs 0, 1 and 7 |
| Receipt age p50/p95/p99/max | 84.38/90.44/108.94/113.06 ms | 80.12/85.49/105.20/108.92 ms |
| Process time p50/p95/max | 82.93/86.99/109.58 ms | 78.31/83.42/104.78 ms |
| Load-start lag p50/max | 0.02/13.07 ms | 0.03/8.94 ms |
| Peak worker RSS | 196,161,536 bytes | 186,732,544 bytes |

Both reports have 100 contiguous frame IDs. Their input point counts and
cell counts match the same frames from the saved experiment 0016 CLI runs;
source metadata hashes match as well. This confirms the same sampled workload
and coarse output shape, not exact map-array equivalence: this harness does
not calculate map digests during the timed loop. Summary miss counts agree
with the per-frame records. Ruff lint/format and targeted mypy passed for the
harness.

## Longer diagnostic window

The same harness and default configuration were then run separately for
1,000 scans on each sequence. These are still partial sequences, not the
proposed complete-path release window. Both reports completed with contiguous
IDs and summary/per-frame miss counts in agreement. The sequence source and
metadata hashes matched the 100-frame runs; the first 100 input point and
cell counts were checked against the earlier CLI baseline.

| Metric | [Sequence 08, 1,000 scans](../../../Drishti-2.5/runs/drishti-o001-inprocess-screen-seq08-1000-20260925/) | [Sequence 00, 1,000 scans](../../../Drishti-2.5/runs/drishti-o001-inprocess-screen-seq00-1000-20260925/) |
| --- | ---: | ---: |
| Receipt-age deadline misses | 28/1,000 | 3/1,000 |
| Receipt age p50/p95/p99/max | 85.54/96.54/106.11/128.85 ms | 80.61/85.18/90.23/116.98 ms |
| Process time p50/p95/max | 83.13/91.54/125.37 ms | 78.11/82.40/112.02 ms |
| Load-start lag p50/max | 0.02/28.86 ms | 0.02/16.99 ms |
| Peak worker RSS | 241,569,792 bytes | 226,394,112 bytes |

Sequence 08 missed at IDs 0 and 1 and 26 additional IDs through 786,
including four consecutive misses at 727-730. Sequence 00 missed only at
IDs 0-2 in this run. A short run's later ID 7 miss did not recur, so the
exact tail locations are sensitive to runtime conditions. Neither long run
shows an ever-growing start lag in this window, but the scattered sequence 08
tails and cold-start misses violate the selected per-scan rule.

## Judgment

MEASURED RESULT: removing synchronous digest/JSONL work from this research
loop greatly reduced accumulated lag, but the current geometric path still
missed the selected zero-miss 100 ms rule on both 100-frame and 1,000-frame
runs. The first scan exceeded 100 ms in every run, and sequence 08 showed
misses well beyond startup in its longer run.
Moving audit work outside the deadline would require an approved complete
result/consumer contract and a bounded, lossless audit path; this screen
implements neither. Learned inference, detection, temporal mapping and the
final publication event remain absent. AC-008 remains NOT VERIFIED.
