# Experiment 0008: durable 10 Hz ingress technology review

Research update, 2026-09-25: the technology preference below was provisional. A direct
SQLite/LMDB/custom-log comparison and LMDB injected-fault results are now in
[`0009-storage-backend-comparison.md`](0009-storage-backend-comparison.md). Experiment 0008's
measurements remain evidence for their tested conditions.

Status: MEASURED RESULT for the isolated recorders and current geometric replay;
DESIGN PROPOSAL for the future pipeline. Date: 2026-09-24. Question: RQ-005.
No live LiDAR, learned model, temporal map, production recorder or complete-path deadline
was tested.

## Decision in scope

Use a **local SQLite WAL database with `synchronous=FULL` and one transaction per scan** as
the first durable-ingress candidate. Keep the recorder separate from perception, with a
single writer, a stable sequence/frame key, a payload checksum and acknowledgement only after
`COMMIT` returns. Python is sufficient for the measured recorder workload. Use C++20 where a
sensor SDK or measured CPU-heavy stage warrants native code, and retain the Python package as
the present orchestration and evaluation surface. This is a research recommendation, not an
accepted runtime architecture or a no-loss guarantee.

The recommendation follows a direct comparison: native C++ did not materially reduce SQLite
commit latency in these short runs. The common storage boundary dominated both implementations.
MCAP is a strong recording/interchange candidate, especially if multiple synchronized topics
or ROS tooling become required. Its buffering and sealing policy must be part of the loss
contract. A one-scan-per-file MCAP prototype met this short 10 Hz recorder test, but would
produce 36,000 files per hour. Ten-scan segments delayed the first scan's durable acknowledgement
by nearly a second. Neither strategy is a ready work queue.

In plain terms, SQLite would be a **numbered inbox stored in one local file**, with no
database server. The recorder writes scan 42, waits for that write to commit, then reports
"scan 42 saved." A slower worker can fetch it later; after a process restart it can find
the next unprocessed ID. The short tests make this viable as a *capture prototype* on this
laptop: all 100 scans in each run were reverified, and the observed write time stayed below
the 100 ms arrival interval. They do not make the current mapping path viable at 10 Hz.
If the sensor cannot retry a scan before it is saved, or the disk fills while processing
remains slower than arrival, the system still loses the ability to retain every capture.
SQLite's value over plain numbered files or MCAP segments is the atomic per-scan commit
and keyed recovery/work-state query. The team can change the recorder language without
changing that storage contract; the C++ measurement gives no reason to rewrite it now.

## What "without losing data" means

There are four distinct events: sensor exposure, process receipt, durable commit, and processed
output. This experiment starts with already saved dataset files and proves only the third event
for those files. A live source needs a monotonic ID, capture timestamp, payload/format and
calibration version, retry or backpressure semantics, and an explicit failure signal when a
scan cannot be committed. A publisher must report output age and skipped/stale state separately
from storage acknowledgement. If a live sensor discards frames before the recorder sees them,
no local database can recover them. [SQLite WAL](https://www.sqlite.org/wal.html) documents
transaction and sync behavior; [ROS 2 QoS](https://design.ros2.org/articles/qos)
is transport policy, not a substitute for a local durable commit.

For the development workload of 10 scans/s and 130,000 XYZI float32 points, one raw scan is
2.08 MB and ingress is 20.8 MB/s, before indexes, WAL and metadata. The current audit-inclusive
100-frame replay with the native recorder concurrently took 31.43 s, about 3.18 scans/s.
If 10 Hz arrival continued while service stayed at that rate, the raw backlog would grow by
about 6.82 scans/s, or 14.2 MB/s and 51.1 GB/h. The finite-storage time horizon is approximately
`available_bytes / backlog_bytes_per_second`. Any finite buffer eventually fills under sustained
arrival faster than service. The packed-key research candidate in experiment 0003 still took
143-151 ms p50 for geometric `process` alone. The model and temporal stages do not exist yet.

## Reproduction and provenance

Source: read-only SemanticKITTI sequence 08 scans 000000-000099, paced by a monotonic clock at
100 ms intervals. This is file replay, not real sensor timing. Hardware: Intel Core Ultra 9 185H
Linux laptop, local ext4 filesystem on NVMe, GCC 16.2.1, SQLite C library 3.53.4,
OpenSSL 3.6.4, Python 3.12 and MCAP Python package 1.4.0. The C++ benchmark was built with
`-std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror` and linked to SQLite/OpenSSL. Neither CPU
frequency/temperature nor the OS cache was held fixed. The sequential runs are a comparison
of candidates under local conditions, not a controlled language microbenchmark.

The source and result files are:

- [`0005-cpp-sqlite-ingress.cpp`](0005-cpp-sqlite-ingress.cpp),
  [`0005-cpp-seq08-100.csv`](0005-cpp-seq08-100.csv), and
  [`0005-cpp-concurrent-seq08-100.csv`](0005-cpp-concurrent-seq08-100.csv). The C++ program uses
  prepared SQLite BLOB insertion, one `BEGIN IMMEDIATE`/`COMMIT` per scan, SHA-256, and a fresh
  read-only connection that compares every stored payload with its source after completion.
- [`0004-sqlite-ingress.py`](0004-sqlite-ingress.py), the previous standalone
  [`0004-seq08-100-ext4.json`](0004-seq08-100-ext4.json), and the new concurrent
  [`0008-python-concurrent-seq08-100.json`](0008-python-concurrent-seq08-100.json). The two
  concurrent CLI reports are under
  `Drishti-2.5/runs/drishti-concurrent-cpu-20260924-seq08-100/` and
  `Drishti-2.5/runs/drishti-concurrent-python-cpu-20260924-seq08-100/`.
- [`0006-mcap-ingress.py`](0006-mcap-ingress.py) and three
  [`0006-mcap-*-seq08-100.json`](0006-mcap-single-none-seq08-100.json) reports. Each segment
  was written as a partial file, finished, flushed, `fsync`ed, renamed, and its parent
  directory `fsync`ed before its scans were counted as acknowledged. All segments were
  reopened through the MCAP reader with CRC validation and source SHA-256 comparison.
- [`0007-sqlite-faults.py`](0007-sqlite-faults.py) and
  [`0007-sqlite-faults-seq08.json`](0007-sqlite-faults-seq08.json) for process-kill and an
  artificial SQLite page-capacity fault. The page limit is not physical disk exhaustion.

To rerun, use new output paths. From `Drishti-2.5/`:

```sh
g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror \
  ../docs/research/experiments/0005-cpp-sqlite-ingress.cpp \
  -o /tmp/drishti-cpp-sqlite-ingress-0005 -lsqlite3 -lcrypto -pthread
/tmp/drishti-cpp-sqlite-ingress-0005 /home/ashin/Hackathon/SIH/data/dataset \
  08 100 100 NEW_RUN/ingress.sqlite NEW_REPORT.csv
uv run --frozen python ../docs/research/experiments/0004-sqlite-ingress.py \
  --dataset /home/ashin/Hackathon/SIH/data/dataset --sequence 08 --frames 100 \
  --interval-ms 100 --db NEW_RUN/ingress.sqlite --report NEW_REPORT.json
uv run --frozen --with mcap python ../docs/research/experiments/0006-mcap-ingress.py \
  --dataset /home/ashin/Hackathon/SIH/data/dataset --sequence 08 --frames 100 \
  --interval-ms 100 --segment-frames 1 --compression none \
  --output NEW_RUN --report NEW_REPORT.json
uv run --frozen python ../docs/research/experiments/0007-sqlite-faults.py \
  --dataset /home/ashin/Hackathon/SIH/data/dataset --sequence 08 \
  --output NEW_RUN --report NEW_REPORT.json
```

The concurrent tests ran the recorder and
`drishti replay --mode geometric --view none --max-frames 100` at the same time, each in a new
output directory. The recorder overlapped
the CLI only for its approximately 10-second capture window; the CLI then continued to
completion. CSV/JSON values are in milliseconds. Percentiles use NumPy linear interpolation
over 100 samples and exclude no warmup. Full raw SQLite database and MCAP files are ignored
local run artifacts; the small reports and CLI manifests are retained as evidence.

## Measured recorder results

All rows below stored and independently reverified 100 of 100 payloads. "Acquisition" for
SQLite is file read through committed transaction, including SHA-256. It is not capture to
published perception. MCAP "ack" is arrival through durable segment sealing.

| Technology and load | p50 ms | p95 ms | p99 ms | max ms | Stored bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Python SQLite WAL/FULL, alone | 9.26 | 20.48 | 22.05 | 23.98 | 196,493,312 |
| C++20 SQLite WAL/FULL, alone | 9.40 | 19.91 | 20.65 | 20.84 | 196,493,312 |
| Python SQLite WAL/FULL, with CLI | 9.15 | 20.22 | 21.55 | 22.71 | 196,493,312 |
| C++20 SQLite WAL/FULL, with CLI | 9.32 | 20.45 | 22.79 | 23.31 | 196,493,312 |
| Python MCAP, one scan/file, no compression | 11.30 | 13.25 | 13.51 | 13.52 | 196,269,188 |
| Python MCAP, ten scans/file, no compression | 483.07 | 935.85 | 939.67 | 939.86 | 196,211,438 |
| Python MCAP, ten scans/file, zstd | 560.72 | 998.70 | 1007.81 | 1019.59 | 144,030,573 |

The MCAP zstd run used about 26.6% less storage than its uncompressed counterpart, but its
`add_message` p95 was 96.12 ms and its schedule lag p95 was 11.66 ms. Compression on the
capture thread is a poor first choice for the CPU-first design. The multi-scan file results
are not evidence of data loss: the held scans were verified once sealed. They show the extra
unacknowledged exposure window under a durable-segment contract. The one-file design's file
count, directory operations and retention behavior need a long-run test.

The concurrent C++ CLI report recorded audit-inclusive p50/p95/p99 of
313.53/324.90/328.05 ms and 100/100 misses of the configured 100 ms budget. The concurrent
Python report was 313.37/329.43/340.54 ms and also 100/100 misses. These are separate
uncontrolled runs. They demonstrate that this recorder did not prevent its own short 10 Hz
capture workload under the observed load; they do not show processing kept up, and cannot
isolate a C++ versus Python scheduling effect. The C++ harness measured sub-millisecond
schedule lag; the Python harness did not record schedule lag.
Each concurrent replay's 100 input digests, map digests, frame IDs, cell counts and accounting
records matched the earlier standalone sequence 08 baseline at every frame. Timing changed;
the current geometric outputs did not in these samples.

## Failure experiment

After scan 0 committed, a worker was killed with scan 1 inserted but uncommitted. Reopening
the database returned `PRAGMA integrity_check = ok` and only frame ID 0. A restart inserted
frame 1, giving contiguous IDs 0 and 1; a duplicate frame-1 insert was rejected by the key.
With an artificial `PRAGMA max_page_count` restriction, the next insert failed with
`database or disk is full`; the previous committed row and database integrity remained intact.
This proves the observed process-kill and database-size-limit behavior only. It does not test
power interruption, a real full filesystem, a slow SSD, kernel failure or a sensor retry.

## Verification of the research harnesses

The C++ source compiled with all listed warnings treated as errors and a final two-scan
reopen/verification smoke run passed after the last source edit. The MCAP and SQLite fault
Python harnesses passed Ruff lint and format checks; the formatted fault harness reproduced
the saved process-kill and page-limit result. The package test suite passed 42 tests with
the virtual environment's `bin` directory on `PATH`. No production module or locked
dependency was edited.

## Technology comparison

| Candidate | Useful capability | Main limitation for this task | Present judgment |
| --- | --- | --- | --- |
| Python + SQLite WAL/FULL | Atomic per-scan ack, keyed replay and state transitions, existing package and measured 10 Hz recorder feasibility. [SQLite WAL](https://www.sqlite.org/wal.html) permits concurrent readers and one writer. | `fsync` and checkpoints shape tails; one writer and long readers can grow WAL. Python does not accelerate current mapping. | First ingress prototype. |
| C++20 + SQLite | Same durable store plus direct sensor SDK/zero-copy interfaces and predictable native worker integration. [SQLite C BLOB API](https://www.sqlite.org/c3ref/bind_blob.html). | Same storage sync cost; C++ safety/ABI/integration maintenance. The measured recorder is not faster. | Use for SDK or measured compute need, not as a speculative recorder rewrite. |
| MCAP | Open robotics log with schemas/channels, chunking, indexes and recovery tooling. [Format](https://mcap.dev/spec), [writer API](https://mcap.dev/docs/python/mcap-apidoc/mcap.writer). | Buffered segments need an explicit flush/seal ack contract. One-scan files create many files; it lacks a built-in processing state machine. | Archival/interchange candidate; compare when sensor/multi-topic contract is known. |
| Rust + redb/Tokio | Native typed recorder with [immediate durable commit](https://docs.rs/redb/latest/redb/enum.Durability.html) and [bounded channels](https://docs.rs/tokio/latest/tokio/sync/mpsc/index.html). | New language/FFI and sensor SDK work; no local throughput, recovery or integration test. | Viable challenger if the team chooses Rust; not selected from documentation alone. |
| RocksDB | Tunable high-write key-value WAL. [WAL performance](https://github.com/facebook/rocksdb/wiki/WAL-Performance) documents sync tradeoffs. | Its default unsynced writes are not the requested durable ack; compaction and configuration add operational complexity for 10 Hz. No local test. | Keep as a scale-driven option, not the initial dependency. |
| ROS 2/DDS QoS | Useful transport policy if the sensor stack requires ROS. | Reliability and history do not by themselves define a disk commit or recovery log; queues are resource bounded. No live sensor contract exists. | Adapter/transport option, not the durable source of truth. |

The data path should be bounded: sensor adapter -> one durable writer -> indexed backlog ->
bounded compute work -> ordered sequence-owned state -> output with source ID and age. The
recorder's acknowledgement boundary precedes the compute queue. Processing state must be
idempotent across worker restart; database state changes and published output need an explicit
reconciliation protocol. The storage path must report low disk space, commit failures,
checkpoint time and oldest unprocessed scan age. A strict no-loss claim requires source-side
retry or an upstream recorder and an agreed failure response when storage is unavailable.

For the compute side, [oneTBB's parallel pipeline](https://oneapi-spec.uxlfoundation.org/specifications/oneapi/v1.3-rev-1/elements/onetbb/source/algorithms/functions/parallel_pipeline_func)
offers a bounded number of live tokens and serial ordered or parallel filters. This is a
scheduler option, not a measured speedup. Ground extraction uses sequence-specific Patchwork++
state, and future tracking/temporal fusion will also be ordered. If any required serial stage
itself needs over 100 ms per frame, downstream parallelism alone cannot sustain 10 Hz. The
first native compute experiment should target a measured independent hotspot (packed cell
grouping and aggregation), compare exact point/cell IDs and snapshot digests, and measure full
CLI throughput. A [pybind11 GIL release](https://pybind11.readthedocs.io/en/stable/advanced/misc.html)
is relevant only around native code that does not touch Python objects. Existing NumPy and
Patchwork++ already execute substantial work in native code, so a whole-codebase rewrite has
no demonstrated benefit.

## Next evidence gate

1. Freeze live source frame ID, timestamp, payload, calibration, retry/ack and stop behavior;
   specify whether every captured scan must be retained and for how long. Define output-age,
   stale-map, backlog and disk-reserve thresholds.
2. Build a long-duration recorder prototype with explicit WAL checkpoint control, a concurrent
   reader/worker, exact IDs/hashes, process and power fault injection, physical disk pressure,
   and recovery after restart. Measure p99.9/max commit time, WAL size, disk writes and oldest
   backlog age on the selected hardware.
3. Measure the full ordered compute graph with realistic model, detector and temporal stages.
   Prove sustained service rate above 10 Hz with headroom and the frozen capture-to-output
   deadline. Compare Python/process and selective C++/oneTBB alternatives using the same inputs
   and output digests. Keep CPU affinity/power mode and thermal state in the run manifest.

Conclusion: the short experiments support **SQLite WAL/FULL as a pragmatic durable-ingress
prototype** on this laptop. They do not justify rewriting the recorder in C++ for speed.
Current compute is still slower than arrival and future perception work is unmeasured, so
T-014 and the release real-time gate remain open.
