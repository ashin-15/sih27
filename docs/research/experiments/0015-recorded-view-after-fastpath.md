# Experiment 0015: recorded replay after exact all-unknown aggregation

Status: MEASURED RESULT for the current geometric slice, 2026-09-25. RQ-004,
O-001/T-008. This is a diagnostic Rerun SDK boundary, not a rendered-view or
complete-product release gate.

## Setup and reproduction

The selected Core Ultra 9 185H laptop replayed read-only SemanticKITTI sequence 08,
frames 0-99, default config digest
`ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`,
geometric mode, 10 Hz scheduled arrival. Both the saved
[recorded](../../../Drishti-2.5/runs/drishti-o001-unknown-fastpath-record-flush-seq08-100-20260925/)
and [headless](../../../Drishti-2.5/runs/drishti-o001-unknown-fastpath-seq08-100-20260925/)
runs used source digest
`ea32d53d1893d89e617bd73bb0f385ac3f7f7fc29351b7278b68bd1ab3ab5b07`.
The earlier [recorded run](../../../Drishti-2.5/runs/drishti-o001-record-flush-paced-seq08-100-20260925/)
preceded the all-unknown aggregation path. Runs were sequential and cache, thermal
state and background load were not controlled.

Run from `Drishti-2.5/` into a new directory:

```sh
uv run --frozen --extra viz drishti replay --dataset ../data/dataset \
  --sequence 08 --mode geometric --output runs/NEW-RECORD-RUN \
  --view record --max-frames 100 --check-100ms
```

The CLI submitted each frame to Rerun, called the per-frame SDK `flush`, then
calculated the frame digests and flushed the Python JSONL report. The scheduled
arrival-to-report age therefore includes Rerun submission and SDK flush. It does
not imply a disk `fsync`, a rendered frame or final product output.

## Result

All 100 recorded frame IDs, input/map digests, cell counts and accounting records
matched the same-source headless run. The timing sidecar IDs were contiguous and
its 100 misses matched the summary. `rerun rrd verify` succeeded; a full `rrd stats`
command succeeded and reported 100 chunks each for geometry cells, raw points and
semantic cells. The recording was 273,224,630 logical bytes.

| Metric | Headless after change | Record with per-frame SDK flush after change | Earlier record with SDK flush |
| --- | ---: | ---: | ---: |
| Audited work p50/p95/p99 | 110.71 / 117.88 / 125.82 ms | 131.34 / 140.79 / 170.04 ms | 142.03 / 151.69 / 162.41 ms |
| Scheduled output age p50/max | 800.74 / 1273.93 ms | 1859.90 / 3368.26 ms | 2416.26 / 4432.17 ms |
| Rerun submission plus SDK flush p50 | 0 ms | 20.40 ms | 20.27 ms |
| SDK flush alone p50 | 0 ms | 10.16 ms | 10.01 ms |
| Deadline misses | 100/100 | 100/100 | 100/100 |
| Worker peak RSS | 210,202,624 bytes | 320,471,040 bytes | 321,380,352 bytes |

The same-source record/headless difference is observational; the publication timer
isolates Rerun submission plus SDK flush more directly. Earlier/new source runs also
differ in aggregation code, so the work p50 change does not isolate hardware state.

## Judgment

MEASURED RESULT: exact current-slice aggregation savings did not make Rerun recording
meet the selected 100 ms deadline. Every output age still missed, even with the
diagnostic SDK flush event. D-001/D-005 must specify whether Rerun is part of the
accepted output event. Learned, detector and temporal stages remain absent, and
AC-008 is NOT VERIFIED.
