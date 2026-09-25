# Experiment 0012: recorded viewer cost during paced replay

Status: MEASURED RESULT for the current geometric path, 2026-09-25. RQ-004 / O-001.
This measures Rerun recording work on the selected laptop; it does not certify display
latency or the future complete product.

## Setup and reproduction

Run from `Drishti-2.5/` with a new output directory:

```sh
uv run --frozen --extra viz drishti replay --dataset ../data/dataset \
  --sequence 08 --mode geometric --output runs/NEW-RECORD-RUN \
  --view record --max-frames 100 --check-100ms
```

The saved [recording run](../../../Drishti-2.5/runs/drishti-o001-record-view-paced-seq08-100-20260925/)
used read-only SemanticKITTI sequence 08 frames 0-99, SLAM poses, the default mapping
configuration, a virtual 10 Hz schedule and source digest
`925a4c0ed05ffd29892dfd98073865b8952205998a7739f4131c4453f9a1a03d`.
The comparison [headless run](../../../Drishti-2.5/runs/drishti-o001-native-float32-final-seq08-100-20260925/)
has the same source digest and workload. Runs were sequential and did not control laptop
temperature, cache or other activity. No model, temporal state or independent producer
was present.

The CLI calls `RerunView.publish` before calculating the frame digests and flushing
`frames.jsonl`. The current `--check-100ms` publication event is return from that Python
JSONL flush. `RerunView.close` calls Rerun `flush` and `disconnect` only after the final
scan; this final flush is reported separately. Therefore the check includes per-frame
Rerun SDK submission cost but does not prove that each `.rrd` frame was durable or visible
within 100 ms. It does not measure a spawned viewer rendering a frame.

## Observed result

The recording CLI completed all 100 scans and returned expected deadline-failure code 2.
All 100 frame IDs, input/map digests, cell counts and accounting matched the headless run.
The timing sidecar had contiguous IDs and 100 misses, agreeing with `summary.json`.
`rerun rrd verify` returned 0 and reported one file verified without error. Its analytics
initialization logged a read-only filesystem error, unrelated to file verification.
Decoded `rerun rrd stats` reported 391 chunks, including 100 chunks each for
`world/geometry/cells`, `world/semantics/cells` and `world/raw/points`; this supports
that the saved recording contains the 100 submitted scan views. It does not measure
when a viewer displayed them.

| Metric | Headless | Record Rerun |
| --- | ---: | ---: |
| Audited work p50/p95/p99 (ms) | 120.3 / 126.7 / 133.6 | 132.2 / 148.4 / 152.6 |
| Scheduled output age p50/p95/p99/max (ms) | 1260.2 / 2087.1 / 2183.5 / 2210.1 | 1929.0 / 3348.1 / 3503.3 / 3544.4 |
| `publication_ms` p50 (ms) | 0.0004 | 9.93 |
| Deadline misses | 100/100 | 100/100 |
| Worker peak RSS (bytes) | 205,770,752 | 330,760,192 |
| Run files logical/allocated (bytes) | 100,939 / 110,592 | 270,675,431 / 270,700,544 |

The recording's `map.rrd` is 270,574,874 bytes. Final viewer flush was 12.08 ms after
the scan loop. These are measured resource uses for 100 scans, not memory or disk ceilings.
The p50 work difference is observational; the direct publication timer isolates SDK
submission more narrowly, but it still does not measure display or per-frame durability.
The manifests report 4,071 scans in sequence 08 and 4,541 in sequence 00. A linear
extrapolation of this 100-frame `.rrd` size would be about 11.0 and 12.3 GB for those
full sequences, respectively. This is a planning estimate, not a measured full-sequence
recording size: scene content, compression and Rerun buffering may vary.

## Engineering impact

If the release gate includes Rerun, name whether submission, per-frame recording flush,
or rendered display counts as complete output and instrument that event. The current
recorded path fails 100 ms on all 100 scans even under the weakest submission boundary.
The current headless path also fails. Viewer participation, sustained window, workload
and resource limits remain decisions under D-001/D-005; AC-008 is NOT VERIFIED.

## Per-frame Rerun SDK flush follow-up

The current diagnostic `--check-100ms --view record` path now calls
`RecordingStream.flush()` after every `RerunView.publish` and before the frame JSONL
report is written and flushed. Each frame record includes `viewer_flush_ms`, and the
manifest names `frame-jsonl-flushed-after-rerun-sdk-flush` as the measured event. The
installed SDK documents `flush` as waiting for batched data to propagate to its file
descriptor. This is stronger than SDK submission, but is not disk `fsync` or proof of
rendered display.

A fresh [100-frame sequence 08 run](../../../Drishti-2.5/runs/drishti-o001-record-flush-paced-seq08-100-20260925/)
used source digest `7ae2b2ce550d08ee215f61473bfb62c682f6f8691486325fb576d332b0dd175f`,
the same dataset/config and a virtual 10 Hz schedule. It completed all 100 frames and
returned expected code 2. Frame IDs, input/map digests, cell counts and accounting
matched the prior record-mode run. Its sidecar had 100/100 misses, agreeing with the
summary. `rerun rrd verify` passed; decoded stats showed 100 cell, raw-point and
semantic-cell chunks each. Per-frame flushing produced 1,023 chunks rather than the
earlier batched recording's 391.

| Metric | SDK submission only | Per-frame SDK flush |
| --- | ---: | ---: |
| Audited work p50/p95/p99 (ms) | 132.2 / 148.4 / 152.6 | 142.0 / 151.7 / 162.4 |
| Scheduled report age p50/p95/p99/max (ms) | 1929.0 / 3348.1 / 3503.3 / 3544.4 | 2416.3 / 4189.6 / 4384.3 / 4432.2 |
| Viewer SDK `flush` p50/p95/p99/max (ms) | Outside per-frame check | 10.01 / 14.37 / 16.42 / 19.00 |
| Deadline misses | 100/100 | 100/100 |
| RRD bytes | 270,574,874 | 273,224,628 |

The final close still took 13.49 ms in the flush-each-frame run. Its whole run files
occupied 273,329,106 logical and 273,350,656 allocated bytes; worker peak RSS was
321,380,352 bytes. These are sequential observations with uncontrolled machine state,
not a causal estimate of Rerun flush cost beyond its direct timer. Even this measured
recording boundary fails the selected 100 ms deadline on every scan. The product owner
still must decide whether recorded output and which durability or display event belongs
to AC-008; the full product stages are absent.
