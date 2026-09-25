# Experiment 0013: independently scheduled replay producer

Status: MEASURED RESULT for the current geometric path, 2026-09-25. RQ-004/RQ-005,
O-001/O-011. This is a research harness, not the active CLI or a live sensor.

## Question and setup

The CLI's `--check-100ms` advances a virtual 10 Hz schedule inside the processing loop.
This experiment starts a separate dataset producer thread with that schedule and passes
immutable `ScanFrame` values through a bounded two-slot queue to one sequence-owned
`MappingEngine`. If the queue fills, the producer records the event and blocks rather
than dropping the frame. The consumer still writes exact per-frame digests and a report
age measured from the original scheduled arrival. A blocked producer cannot keep the
10 Hz source schedule, which is itself a failed replay-service condition.

The saved [harness](0013-independent-producer-replay.py) has SHA-256
`f2b341c618c49689fac75118883cddc875a24bdd61aec3d3f016bb3a8f315512`.
It uses Python 3.12, NumPy and the current installed Drishti package on the selected
Core Ultra 9 185H laptop. Input is read-only SemanticKITTI sequence 08, frames 0-99,
SLAM poses, default config digest
`ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`,
geometric mode, no model or viewer. The runtime source digest in its manifest is
`7ae2b2ce550d08ee215f61473bfb62c682f6f8691486325fb576d332b0dd175f`.

Run from `Drishti-2.5/` with a fresh output directory:

```sh
uv run --frozen python ../docs/research/experiments/0013-independent-producer-replay.py \
  --dataset ../data/dataset --sequence 08 --frames 100 --queue-capacity 2 \
  --output runs/NEW-INDEPENDENT-ARRIVAL-RUN
```

The preserved [100-frame run](../../../Drishti-2.5/runs/drishti-o001-independent-arrival-seq08-100-20260925/)
completed and returned code 2. A separate
[10-frame smoke run](../../../Drishti-2.5/runs/drishti-o001-independent-arrival-smoke-seq08-10-20260925/)
also completed with expected code 2. The 100-frame run's manifest, frame records,
timing records and summary total 77,494 logical bytes. `ruff check`, `ruff format
--check` and targeted mypy passed for the harness.

## Result

All 100 IDs were contiguous, and every input/map digest, cell count and accounting
record matched the same frames from the saved headless CLI baseline. The timing file had
100 IDs and 100 deadline misses, matching the summary. No scan was silently discarded;
the producer blocked when the two-slot queue filled.

| Metric | Observed |
| --- | ---: |
| Scheduled-arrival-to-report age p50/p95/p99/max | 1312.4 / 2168.3 / 2263.9 / 2288.0 ms |
| Producer load-start lag p50/p95/p99/max | 844.3 / 1681.6 / 1767.7 / 1790.7 ms |
| Worker start lag p50/p95/p99/max | 1194.4 / 2042.6 / 2139.4 / 2163.7 ms |
| Producer enqueue block p50/p95/p99/max | 117.9 / 123.9 / 127.9 / 129.1 ms |
| Queue-full events | 93 of 100 scans |
| Maximum observed queue depth | 2 of 2 slots |
| Deadline misses | 100 of 100 scans |
| Worker peak RSS | 208,121,856 bytes |

The first scan's report age was 174.9 ms; the last scan's was 2288.0 ms. A queue
with two slots preserved all frames in this finite run but delayed source loading
once the worker fell behind. The producer's median load-start lag of 844.3 ms shows
that it did not sustain independent 10 Hz ingestion. Increasing queue capacity can
delay blocking, but a finite queue cannot make a sustained slower worker meet a
100 ms output-age deadline.

## Limits and next decision

The producer is a Python thread reading preexisting dataset files, not a sensor or
durable recorder. Its reads and the worker contend for this laptop and Python runtime;
schedule jitter, cache and machine load were not controlled. The queue's full event
does not prove a live source would retry or preserve data. The harness does not contain
the learned, temporal or viewer stages and cannot satisfy AC-008.

MEASURED RESULT: the current geometric worker fails both the strict output deadline
and bounded 10 Hz independent replay service. O-001 remains IN PROGRESS. A future
complete-path gate needs an approved overload policy, a measured publication event,
and service fast enough for the frozen workload. O-011's durable no-loss claims remain
separate from this volatile queue experiment.
