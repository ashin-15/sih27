# Experiment 0003: exact grouping and a lossless 10 Hz ingress design

Status: MEASURED RESULT for isolated grouping and current geometric `process` calls;
DESIGN PROPOSAL for recording and scheduling. Question: RQ-004. No live sensor, queue,
durable recorder, production optimization, learned model or complete-path guarantee was tested.

## Reproduce the measurement

- Hardware and software: the current Intel Core Ultra 9 185H Linux laptop, Python 3.12.14,
  NumPy 2.5.3 and the unchanged Drishti runtime. Source was a dirty working tree at Git HEAD
  `998e83ee4bc04769f98e73c20f97e900732300b1`. The mapping source SHA-256 was
  `f04464f9f087ca459e16e2ffd0a30f135c054b07328e81ef17edfa5f926ce732`.
- Dataset: read-only SemanticKITTI sequences 00 and 08, frames 0-29 each, geometric mode,
  default config digest `ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`.
  No viewer, model, tracker, temporal state, disk recorder, live acquisition or concurrent workers.
- Harness: [`0003-grouping-benchmark.py`](0003-grouping-benchmark.py), SHA-256
  `b0f32e0d3183a0c9bca48b8a65e4dd855903fbb3ebe4e0a44afd5a9b7075aae2`.
  It tests empty, negative, multilevel, wide and int64-extreme keys, then compares baseline
  row-wise `np.unique`, collision-checked mixed-radix int64 packing, and `np.lexsort`.
  Packing falls back to the baseline when the frame's key space cannot fit in signed int64.
  Each candidate's ordered unique keys, inverse indices and counts must exactly match the
  baseline. A second sequence-owned engine substitutes packed grouping only during its
  `process` call and must match every baseline snapshot digest and point-to-cell assignment.
  Percentiles below exclude initialization frame 0. The runs were sequential, not a controlled
  thermal comparison. `unittest.mock.patch` adds slight overhead to candidate process timing.

```sh
cd /home/ashin/Hackathon/SIH/Drishti-2.5
uv run --frozen python ../docs/research/experiments/0003-grouping-benchmark.py --dataset /home/ashin/Hackathon/SIH/data/dataset --sequence 00 --frames 30 --verify-frames 30 --output /tmp/drishti-grouping-new-seq00.json
uv run --frozen python ../docs/research/experiments/0003-grouping-benchmark.py --dataset /home/ashin/Hackathon/SIH/data/dataset --sequence 08 --frames 30 --verify-frames 30 --output /tmp/drishti-grouping-new-seq08.json
```

The complete per-frame timing records are [`0003-seq00-30.json`](0003-seq00-30.json) and
[`0003-seq08-30.json`](0003-seq08-30.json). Choose unused output paths for reruns.

| Sequence | Baseline grouping p50/p95 ms | Packed grouping p50/p95 ms | Lexsort p50/p95 ms | Baseline process p50/p95 ms | Packed process p50/p95 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 00 | 132.54 / 135.41 | 9.34 / 10.54 | 19.91 / 20.77 | 266.00 / 273.05 | 143.19 / 148.45 |
| 08 | 133.77 / 137.40 | 10.11 / 10.88 | 21.65 / 22.21 | 276.19 / 279.56 | 150.54 / 153.28 |

MEASURED RESULT: 60/60 real-frame grouping comparisons matched exactly and 60/60 snapshot
digests and cell-index arrays matched. The isolated packed operation was about 13 to 14 times
faster at p50; the full `process` p50 was still 43 to 51 ms above a 100 ms interval. These
process numbers exclude scan loading, CLI audit and all future features. They cannot establish
10 Hz throughput or 100 ms capture-to-published latency. Production integration, long-run
correctness, memory and thermal stability remain NOT VERIFIED.

## Capacity argument

FACT: A 10 Hz source adds 10 frames/s. The earlier current-path replay completed about
3.14 frames/s audit-inclusive on sequence 08. A single worker at that sustained rate would
accumulate about 6.86 frames/s during continuous acquisition. At 130,000 four-component
float32 points, scan payload alone is 2.08 MB/frame, so that deficit would add approximately
14.3 MB/s, or 51 GB/hour, before metadata, indexes, write amplification and derived outputs.
The packed `process` p50 is still above 100 ms; an isolated p50 is not sustained service rate.

DESIGN CONSTRAINT: no finite RAM or disk queue can simultaneously guarantee zero dropped
acquisitions, bounded backlog and bounded output latency under indefinite arrival faster than
service. A queue absorbs finite spikes. A durable log preserves acquired frames for eventual
processing while space remains. Live consumers must receive freshness and overload status; if
the storage reserve or age limit is reached, the source/vehicle must slow or stop according to
an approved policy. A safety-critical output must not silently substitute an old map for a
current one. This policy is unresolved in D-001/D-003/D-004.

## Proposed implementation technology

1. **Durable ingress:** use local SQLite in WAL mode with `synchronous=FULL`, one transaction
   per raw scan. Store sequence ID, frame ID, capture timestamp, pose/calibration version,
   point count, immutable payload and SHA-256. A scan is acknowledged only after its insert
   commits. Make `(sequence, frame_id)` unique and detect missing/out-of-order IDs. A reader
   processes uncompleted rows in order; completion is idempotent by frame ID and output digest.
   Keep a disk-reserve threshold and explicit acquisition fault. Benchmark real 2 MB inserts,
   checkpoints, recovery, endurance and disk-full behavior before accepting this choice.
   SQLite documents concurrent readers and writer in WAL mode and sync on every commit with
   FULL; WAL requires a local filesystem. See [WAL documentation](https://www.sqlite.org/wal.html).
2. **Compute:** first integrate exact packed grouping with overflow fallback after approval
   and repeat the CLI replay. Keep one ordered owner for the sequence-specific Patchwork++
   ground state. Split immutable, stateless projection and cell aggregation from that owner
   only after interface and digest tests. Use Python 3.12 processes and bounded
   `multiprocessing.shared_memory` slots for large NumPy arrays to avoid repeated pickling;
   the control queue carries only slot IDs and metadata. Shared memory is volatile and is
   never the sole copy of an acquired scan. See [Python multiprocessing](https://docs.python.org/3.12/library/multiprocessing.html)
   and [shared memory](https://docs.python.org/3.12/library/multiprocessing.shared_memory.html).
3. **Ordered publication:** assemble results by frame ID, keep sequence-owned temporal state
   ordered when it is implemented, and publish capture-to-output age, queue depth, oldest age,
   deadline misses, recorder commit latency and last complete ID. Do not claim a 100 ms live
   guarantee from overlapped throughput. A delayed result remains available for replay but
   must be marked stale for live use.

DESIGN PROPOSAL, not implementation: SQLite is the durable work queue; shared memory is a
bounded acceleration layer; ordered workers are only introduced where the stage is stateless.
The recorder is intentionally a local runtime addition, not a claim that the current repository
already has a database. MCAP could be an interchange/archive format, but its writer's message
call alone is not a per-frame durable acknowledgement contract; see its
[writer API](https://mcap.dev/docs/python/mcap-apidoc/mcap.writer).

## Acceptance experiments before a product claim

- Integrate packed grouping and compare exact CLI digests, accounting and ordered IDs over
  representative long sequences, coordinate boundaries and an overflow fallback case.
- Replay a 10 Hz paced source for a sustained period while profiling source capture, durable
  commit, each stage, parallel contention, capture-to-publish p50/p95/p99/max, memory, disk,
  queue depth, oldest age and total completed frames. Include the model and temporal stages
  once they exist. Sustained service must exceed arrival with headroom; p99 latency and miss
  policy need frozen acceptance values.
- Kill the process during ingest, processing and output commit, then restart. Verify contiguous
  acknowledged IDs, checksums, no missing committed scans, idempotent replay and no duplicate
  published frame. Inject disk-full and slow-disk faults. State what happens to an unacknowledged
  sensor frame, since software cannot promise recovery of a frame never committed.
- At 10 Hz, compare a one-worker version against bounded two-worker stateless mapping. Accept
  parallelism only if measured throughput, tail latency and exact outputs improve on the target
  CPU. Preserve the single ordered ground and future temporal-state owners.

UNKNOWN: live sensor retry/flow control, available disk and endurance, output consumer age
limit, model cost, real parallel contention and final hardware. All are required before a
no-loss or real-time product claim.
