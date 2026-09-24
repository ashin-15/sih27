# Experiment 0004: paced SQLite WAL scan ingress

Status: MEASURED RESULT for an isolated recorder prototype on 2026-09-24. Question: RQ-004.
This is not the Drishti runtime, a live LiDAR driver, a concurrent pipeline, or a no-loss
product guarantee.

## Method

[`0004-sqlite-ingress.py`](0004-sqlite-ingress.py) read the first 100 SemanticKITTI sequence
08 `.bin` scans from the existing read-only dataset, scheduled one every 100 ms, and inserted
each raw payload as one transaction into a new local SQLite database. It checked
`journal_mode=wal` and `synchronous=FULL` and stored sequence, frame ID, capture time, point
count, SHA-256 and payload under a unique `(sequence, frame_id)` key. The payload was read
and hashed before commit. After closing the writer, a fresh connection read all rows and
verified contiguous IDs, point lengths, payload hashes and matching hashes of source files.

Hardware: current Intel Core Ultra 9 185H Linux laptop. Python 3.12.14 and the installed
SQLite from its standard-library `sqlite3` module were used. The first database was placed in
`/tmp`, which `findmnt` showed was **tmpfs**; that run measures RAM-backed WAL, not persistent
storage. Its record is [`0004-seq08-100-tmpfs.json`](0004-seq08-100-tmpfs.json). The second
database was placed under `Drishti-2.5/runs/drishti-sqlite-ingress-20260924-seq08-100/` on
the project's ext4 filesystem backed by `/dev/nvme0n1p2`, also confirmed with `findmnt`.
Its record is [`0004-seq08-100-ext4.json`](0004-seq08-100-ext4.json). Other system load,
thermal mode, power-loss behavior and storage cache state were not controlled.

```sh
cd /home/ashin/Hackathon/SIH/Drishti-2.5
uv run --frozen python ../docs/research/experiments/0004-sqlite-ingress.py --dataset /home/ashin/Hackathon/SIH/data/dataset --sequence 08 --frames 100 --interval-ms 100 --db /home/ashin/Hackathon/SIH/Drishti-2.5/runs/drishti-sqlite-ingress-new/ingress.sqlite --report /tmp/drishti-sqlite-ingress-new.json
```

Create a new unique run directory and choose unused database and report paths. The script
refuses to write inside the dataset.
SQLite's [WAL documentation](https://www.sqlite.org/wal.html) says FULL synchronization
syncs the WAL at each commit. A successful commit is the proposed acknowledgement boundary;
the experiment did not test power loss or a sensor retry protocol.

| Ext4/NVMe stage | p50 ms | p95 ms | p99 ms | max ms |
| --- | ---: | ---: | ---: | ---: |
| Read scan file | 0.58 | 1.49 | 1.81 | 1.94 |
| SHA-256 | 2.25 | 2.72 | 2.95 | 3.00 |
| SQLite insert and commit | 6.34 | 17.38 | 18.48 | 19.82 |
| Read through commit | 9.26 | 20.48 | 22.05 | 23.98 |

MEASURED RESULT: all 100 scheduled scans were committed and verified after reopen in each
run. The ext4 database file was 196,493,312 bytes after close; this excludes any transient
WAL size during the run. The maximum measured ext4 read-through-commit time was 23.98 ms,
below the 100 ms arrival interval in this short, recorder-only test. The earlier tmpfs run
measured 6.07 ms p50 and 15.62 ms max read-through-commit; it is not storage-durability
evidence. Neither test says anything about sustained compute
service, output age, long-run disk behavior, source backpressure, process kill or power-loss
recovery. A real live source may deliver at more irregular times and may have a different
payload and metadata contract.

Next: repeat on a selected persistent local filesystem with the actual sensor encoding and
disk-reserve policy. Test concurrent processing, hours-long writing and checkpoints, forced
process termination during transactions, restart and idempotent replay, slow/full disk,
unacknowledged-frame behavior and capture-to-published-output latency with all enabled stages.
