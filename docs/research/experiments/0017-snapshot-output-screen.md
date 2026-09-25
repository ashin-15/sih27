# Experiment 0017: current snapshot output format screen

Status: MEASURED RESULT for a research-only current-slice serialization screen,
2026-09-25. RQ-004, D-001/D-005, O-001/T-007/T-008. This does not select a
first-release output contract or establish an end-to-end deadline.

## Question and setup

The [output-boundary audit](../../o-001-output-boundary-audit.md) found no
persisted complete machine map. This screen measures two straightforward
lossless encodings of the current `MapSnapshot`: a ZIP archive of `.npy` arrays
and scalar JSON metadata, stored without compression or deflated at level 6.
It does not encode `FrameResult` observations/range image or future learned,
detector and temporal fields.

The saved [harness](0017-snapshot-output-screen.py) has SHA-256
`7688dc7811914c7da6e92b27bac806ef34eef76c51235d6de9a842fac37b4001`.
It ran with Python 3.12 and NumPy on the selected Core Ultra 9 185H laptop,
read-only SemanticKITTI sequence 08 frames 0-9, SLAM poses, geometric mode and
default config digest
`ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`.
The runtime source digest was
`4c726ea553ad74d8751dd3747111239f8c91fb68dc4b827438ab7676aa620d2a`.

Run from `Drishti-2.5/` into a fresh output directory:

```sh
.venv/bin/python ../docs/research/experiments/0017-snapshot-output-screen.py \
  --dataset ../data/dataset --sequence 08 --frames 10 \
  --output runs/NEW-SNAPSHOT-OUTPUT-SCREEN
```

The saved [10-frame run](../../../Drishti-2.5/runs/drishti-o001-snapshot-serialization-seq08-10-20260925/)
contains a manifest, per-frame and summary reports, and one stored and one
deflated frame-0 exemplar. Each frame/format was read back and checked for the
same field names, dtype, shape and raw bytes, including scalar metadata.
Both saved exemplar SHA-256 hashes and all frame-0 fields were independently
rechecked against a fresh current-source replay. Ruff lint/format and targeted
mypy passed for the harness.

## Result

| Per-scan metric, ten frames | Stored `.npz` | Deflated `.npz` |
| --- | ---: | ---: |
| Encoded bytes p50 | 15,644,350 | 765,004 |
| Encode time p50/p95/max | 13.59 / 16.88 / 17.50 ms | 261.96 / 268.47 / 272.05 ms |
| File write time p50 | 4.52 ms | 0.36 ms |
| File flush plus `fsync` p50 | 10.02 ms | 10.74 ms |
| Process + encode + write + file `fsync` p50/max | 115.03 / 135.32 ms | 355.89 / 383.91 ms |
| Exact current-snapshot round trips | 10/10 | 10/10 |

The process-only p50 in this short unpaced sample was 82.53 ms. The combined
numbers above add each frame's measured stages and are not a paced output-age
gate. The harness serializes both formats sequentially and verifies each
round trip, so cache, disk activity and thermal state differ from a production
single-format writer. File `fsync` does not prove directory-entry durability,
power-loss recovery or consumer acknowledgement.

For planning only, multiplying the ten-frame median bytes by the proposed
8,612 scans across full sequences 08 and 00 yields about 125.5 GiB stored or
6.14 GiB deflated. That is not a measured full-sequence artifact size: scan
density, scene content, future output fields and compression ratio can change.
The stored estimate exceeds the provisional 32 GiB artifact ceiling in the
unapproved [O-001 release proposal](../../o-001-release-profile.md).

## Judgment

MEASURED RESULT: a straightforward persisted current snapshot adds material
time or disk use. Deflate level 6 is far too slow for the selected 100 ms
per-scan goal in this screen; uncompressed ZIP is smaller in CPU cost but large
on disk, and its sampled process-plus-write sum already exceeds 100 ms. This
does not rule out better encodings, asynchronous persistence or an in-process
consumer. It supports freezing the actual payload and handoff event before
implementation and benchmarking the complete path. O-001 remains IN PROGRESS.
