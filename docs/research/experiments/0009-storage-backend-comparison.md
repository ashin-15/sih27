# Experiment 0009: SQLite alternatives for durable scan acquisition

Date: 2026-09-25. RQ-005 / T-014. Research prototype only; no runtime integration or
accepted architecture decision. This review supersedes the **technology preference** in
experiment 0008, whose measurements remain valid for their conditions.

## Question and workload

Which local storage backend can acknowledge each 10 Hz scan after a durable commit, keep
ordered replay possible, and handle a restart without silently losing acknowledged frames?
The current geometric worker is slower than 10 Hz, so storage must be considered separately
from processing. A durable recorder can preserve captured input only while source retry and
capacity contracts hold. It cannot bound output age under indefinitely slower processing.

The isolated C++20 harness [`0009-storage-backends.cpp`](0009-storage-backends.cpp) reads the
same raw SemanticKITTI `.bin` scan from the extracted local dataset every 100 ms, hashes it
with SHA-256, and stores its bytes and frame ID. It starts a new output directory for each
run and, after closing the writer, opens the store afresh and compares every frame ID,
recorded payload length, digest and payload to the original scan. Timings exclude subsequent
verification and CSV output. Acquisition time starts just before reading a local scan file
and ends when the append or transaction returns. It is **not sensor capture-to-ack time**.

Three backends used one record per transaction/sync:

| Backend | Commit/ack boundary | Prototype representation |
| --- | --- | --- |
| SQLite | `COMMIT` with WAL and `synchronous=FULL` | Indexed table with payload BLOB and digest; `journal_mode` and `synchronous` are checked in the final harness. |
| LMDB | `mdb_txn_commit` with default sync flags | Big-endian frame ID key, header and payload value; 8 GiB map limit, with no `MDB_NOSYNC`, `MDB_NOMETASYNC` or `MDB_WRITEMAP`. |
| Custom append log | `fdatasync` after each record | Single file, 72-byte packed header plus payload; parent directory synced after creation. This **does not implement** partial-tail repair, work state, retention, or segment rotation. |

The ext4 filesystem is `/dev/nvme0n1p2` on the local NVMe drive. CPU: Intel Core Ultra 9
185H. Compiler GCC 16.2.1; SQLite 3.53.4; LMDB 0.9.35; OpenSSL 3.6.4. The `/tmp` smoke
tests are on tmpfs and are excluded from performance claims. Source dataset files were read
only. The three 100-scan rounds used two sequences and changed run order (A: log, LMDB,
SQLite; B: SQLite, LMDB, log; C: LMDB, log, SQLite). These are observational local runs,
not randomized controlled trials. Source files can be page-cached, and filesystem writeback,
thermal and background load were not held constant. Every round starts with a fresh store.

## Observed paced 100-scan results

All nine runs reverified 100/100 source payloads and contiguous IDs after writer close.
Numbers below are milliseconds, including all 100 samples per run, with linear-interpolated
percentiles. Commit is backend insertion/sync only. Acquisition includes local file read,
SHA-256 and commit. No observed schedule lag exceeded 0.489 ms.

| Sequence / order | Backend | Commit p50 / p95 / p99 / max | Acquisition p50 / p95 / p99 / max |
| --- | --- | ---: | ---: |
| 08 / A | log | 7.865 / 17.855 / 19.205 / 20.088 | 11.366 / 21.554 / 23.913 / 25.639 |
| 08 / A | LMDB | 3.952 / 5.017 / 5.336 / 5.636 | 7.599 / 9.145 / 9.437 / 9.502 |
| 08 / A | SQLite | 5.840 / 16.990 / 17.415 / 20.048 | 9.614 / 20.632 / 21.342 / 24.057 |
| 08 / B | SQLite | 5.744 / 16.946 / 18.289 / 19.571 | 9.635 / 20.715 / 22.205 / 22.410 |
| 08 / B | LMDB | 4.143 / 6.916 / 7.419 / 7.697 | 7.768 / 10.945 / 11.419 / 11.645 |
| 08 / B | log | 2.589 / 3.538 / 4.100 / 4.966 | 5.498 / 7.920 / 8.535 / 8.926 |
| 00 / C | LMDB | 3.267 / 4.863 / 5.255 / 5.495 | 8.046 / 9.885 / 11.060 / 13.033 |
| 00 / C | log | 2.537 / 3.604 / 4.133 / 4.174 | 5.972 / 7.383 / 8.084 / 8.375 |
| 00 / C | SQLite | 5.382 / 15.474 / 16.674 / 18.020 | 9.241 / 19.703 / 20.993 / 21.956 |

Raw per-frame reports are `0009-{log,lmdb,sqlite}-seq08-100-{a,b}.csv` and
`0009-{log,lmdb,sqlite}-seq00-100.csv`. Ignored binary stores remain in unique
`Drishti-2.5/runs/drishti-storage-*` directories. Logical file sizes after close for
sequence 00 were 194,104,656 bytes (log), 194,338,816 (LMDB `data.mdb`) and 194,371,584
(SQLite). The 8 GiB LMDB map is a maximum address-space reservation, not an 8 GiB physical
file in these runs. The source payload sum was 194,097,456 bytes.

MEASURED RESULT: LMDB had a lower observed commit p95 and max than SQLite in each short
round. The custom log was faster in B and C but much slower in A; one favorable log result
would have been misleading. None of these sample maxima establishes a hard deadline.

## Matched 1,000-scan runs

The final harness (including explicit SQLite PRAGMA assertions) ran sequence 00 for 1,000
arrivals at 100 ms intervals, first LMDB and then SQLite. Each writer closed and a fresh
reader reverified 1,000/1,000 contiguous IDs, source payloads and SHA-256 digests. The
source payload total was 1,934,444,720 bytes. The LMDB `data.mdb` file was 1,936,666,624
logical and 1,936,670,720 allocated bytes; SQLite was 1,937,178,624 logical/allocated bytes
after close. These are file measurements, not process RSS or lifetime write amplification.

| Backend | Commit p50 / p95 / p99 / max (ms) | Acquisition p50 / p95 / p99 / max (ms) | Max schedule lag (ms) | Acquisition >100 ms |
| --- | ---: | ---: | ---: | ---: |
| LMDB | 3.215 / 16.271 / 18.507 / 22.159 | 7.815 / 30.029 / 34.767 / 40.695 | 0.404 | 0 / 1,000 |
| SQLite | 5.462 / 18.230 / 24.451 / 31.362 | 8.920 / 22.080 / 28.295 / 33.597 | 1.520 | 0 / 1,000 |

MEASURED RESULT: LMDB still had a lower backend-commit p95/p99/max in this matched pair.
Its end-to-end acquisition p95 and max were **higher** than SQLite's, largely because the
separate local source-file read was slower in that run (LMDB read p95 12.725 ms versus
SQLite 1.821 ms). We cannot attribute that input-read difference to LMDB. This variation
reinforces that the short runs do not justify a universal speed claim. Neither run included
the current perception worker or an LMDB reader during writes.

At the observed 1,934,444,720 payload bytes per 100 seconds, indefinitely retaining this
sequence would add about 69.64 GB of raw payload per hour at 10 Hz, before storage metadata
or any processing outputs. The benchmark's 8 GiB LMDB map cap would accommodate only about
7.4 minutes at this observed rate if all scans remain retained. This is a capacity
calculation from the sampled sequence, **not a measured time-to-full run**. A real service
needs a declared disk reserve, map growth/rotation and deletion policy tied to durable
processing acknowledgement; otherwise capture must stop with an explicit fault before
unrecoverable data loss.

## Injected LMDB failures

[`0009-lmdb-faults.cpp`](0009-lmdb-faults.cpp) uses a separate writer process. It commits
scan 0, starts scan 1 without committing, then the parent sends `SIGKILL`. A fresh LMDB
environment found exactly scan 0 with matching payload. `MDB_NOOVERWRITE` rejected a retry
of scan 0, then scan 1 committed and both payloads reverified. In a separate 8 MiB map-limit
environment, four copies of a real scan committed; the next write returned `MDB_MAP_FULL`,
and the four committed payloads still matched. This is an artificial map limit, **not a
physical disk-full test**. No power failure, kernel crash or storage-controller cache failure
was injected. The kill test validates transaction rollback in this local scenario only.

## Concurrent reader and current replay: first attempt

An LMDB writer paced 500 sequence 08 scans while an independent process used short read
transactions to inspect all 500 records and a separate current geometric CLI replay
processed 100 frames. The reader verified all 500 headers and payload hashes with a
maximum lookup-plus-hash duration of 4.446 ms. The CLI completed 100 frames. **The writer
run failed** its immediate close/reopen verification with `mdb_txn_begin: Resource
temporarily unavailable` while the independent reader was still active. The writer therefore
did not emit its timing CSV in that attempt. After both processes exited, an independent
reader re-opened the same store and reverified 500/500 payload hashes; `mdb_stat` reported
500 entries. This narrows the failure to the concurrent reopen/verification step and does
not prove the run's commit timings.

The failure was reproduced deliberately with a reader holding its environment open while
the writer closed/reopened. A new reader process also received `EAGAIN`. Two independently
launched sandbox commands both reported PID 2, and `mdb_stat -r` recorded PID 2 in the
reader table. [LMDB's source](https://raw.githubusercontent.com/LMDB/lmdb/mdb.master/libraries/liblmdb/mdb.c)
uses the process ID as a byte offset for the lock-file reader marker. **INFERENCE:** the
tool's separate PID namespaces caused a false PID collision on a shared LMDB lock file.
To test this, [`0009-same-namespace-concurrency.py`](0009-same-namespace-concurrency.py)
launched the writer and a held-open reader under one namespace: parent PID 2, writer PID 3,
reader PID 4. The reader remained open through the writer's final reopen check, and both
completed successfully; the writer reverified 100/100 source payloads. This resolves the
observed harness failure under this environment, while ordinary process restart behavior
outside this sandbox remains to be validated in the target deployment.

A second 500-scan concurrent run used a reader for the first 400 scans, so the reader closed
before the recorder's final check despite the separate sandbox launch. The writer then
reverified all 500 source payloads and IDs. Writer commit p50/p95/p99/max was
4.405/6.039/7.181/12.550 ms, acquisition 8.106/10.040/11.761/16.541 ms, maximum schedule
lag 0.430 ms, and zero acquisitions exceeded 100 ms. The reader reverified 400/400 headers
and payload hashes with a 4.102 ms maximum lookup-plus-hash time. A concurrent 100-frame
geometric CLI replay completed with 100/100 configured deadline misses. Its frame IDs,
input/map digests, cell contents, accounting and snapshot array sizes matched the earlier
standalone sequence 08 baseline on all 100 frames. These are independent processes, and the
reader's reported capture-to-read age includes tool startup delay, so it is not a live
sensor-to-output freshness measure. The first failed run is not counted as a successful
timing sample.

## Source-backed behavior and design implications

- [LMDB's C API](https://github.com/openldap/openldap/blob/master/libraries/liblmdb/lmdb.h)
  documents synchronous commit by default, `MDB_MAP_FULL`, a single writer, and the loss
  of durability when `MDB_NOSYNC` or `MDB_NOMETASYNC` are selected. The default flags were
  used in this prototype. LMDB readers must have short transaction lifetimes to avoid
  retaining old pages; map sizing, growth and disk reserve need explicit handling.
- [SQLite's WAL documentation](https://www.sqlite.org/wal.html) documents FULL sync on each
  commit and checkpoint work. A long reader can prevent checkpoint progress, and checkpoint
  work can add commit tails. The earlier SQLite fault and concurrent-replay tests remain
  useful evidence for SQLite, not proof that LMDB is ready for production.
- [Linux `fsync` documentation](https://man7.org/linux/man-pages/man2/fsync.2.html) explains
  why creating a durable file also requires syncing its containing directory. The custom
  log does this for the initial file, but a complete recorder would need a defined recovery
  marker/tail-truncation scheme, idempotent replay state, segment rotation, deletion policy,
  and tests for torn writes and crash at every transition.

DESIGN PROPOSAL: advance LMDB as the next **research prototype** for a single-writer local
scan inbox on this machine. Retain SQLite WAL/FULL as a credible, tested fallback. Do not
select the custom log for production based on these latencies: the missing correctness and
operability work outweighs its uncertain speed advantage. The product contract and accepted
ADR have not yet selected a backend.

## Reproduce and remaining gates

From the repository root, use fresh output paths:

```sh
g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror \
  docs/research/experiments/0009-storage-backends.cpp \
  -o /tmp/drishti-storage-backends-0009 -lsqlite3 -llmdb -lcrypto -pthread
/tmp/drishti-storage-backends-0009 lmdb data/dataset 08 100 100 \
  Drishti-2.5/runs/NEW-LMDB-RUN docs/research/experiments/NEW-LMDB.csv
g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror \
  docs/research/experiments/0009-lmdb-faults.cpp \
  -o /tmp/drishti-lmdb-faults-0009 -llmdb
/tmp/drishti-lmdb-faults-0009 \
  data/dataset/sequences/00/velodyne/000000.bin Drishti-2.5/runs/NEW-LMDB-FAULTS
g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror \
  docs/research/experiments/0009-lmdb-reader.cpp \
  -o /tmp/drishti-lmdb-reader-0009 -llmdb -lcrypto -pthread
python docs/research/experiments/0009-same-namespace-concurrency.py \
  --writer /tmp/drishti-storage-backends-0009 \
  --reader /tmp/drishti-lmdb-reader-0009 --dataset data/dataset \
  --directory Drishti-2.5/runs/NEW-LMDB-SAME-NAMESPACE \
  --csv docs/research/experiments/NEW-LMDB-SAME-NAMESPACE.csv
```

For an implementation decision, still require sustained paced ingestion alongside the
current worker for longer than 500 frames, memory and allocated disk trends,
long-lived-reader/map-growth faults, source retry semantics, retention/backpressure, and
output-age measurement. Physical disk-full and real power-loss behavior remain UNKNOWN.
Even a perfect recorder cannot keep both no-loss input and bounded fresh output if sustained
processing capacity stays below arrival rate without a declared limit and stop policy.
