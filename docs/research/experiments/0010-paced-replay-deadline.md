# Experiment 0010: paced replay against the 100 ms per-scan deadline

Status: Completed for the current geometric path, 2026-09-25. Research question RQ-004;
engineering task T-008 and open item O-001. The user selected a strict 100 ms first-release
deadline for every scan on the current laptop. This experiment tests the available slice,
not the complete future product.

## Setup and measurement boundary

- Platform: current Intel Core Ultra 9 185H laptop, Linux x86_64, 22 logical CPUs. Python
  package from working-tree HEAD `9dd11fb6830ec8940ef354a755bb905f0cf0f27d` plus the
  uncommitted CLI timing change. Source digest in the manifest:
  `ec61863f1e81d7cef18ba0f81633a7b735a3a6987dd22af5d654e260579a17a7`.
- Input: read-only SemanticKITTI sequence 08, frames 0-99, geometric mode, SLAM poses,
  default mapping configuration digest
  `ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`.
  One sequence-owned engine processed all scans in order. No model, detector, tracker,
  temporal map, live sensor or viewer was present.
- Schedule: the CLI sets a monotonic origin immediately before the replay loop and assigns
  frame `i` a scheduled arrival at origin + `i * 100 ms`. It waits when early; when processing
  is late, it records the lag and reads the next file without waiting. No independent producer
  captures scans at 10 Hz, so this is a virtual arrival schedule, not live sensor evidence.
- Publication boundary: Python's `frames.jsonl` stream flush returns. This includes scan
  file read, `MappingEngine.process`, frame digest, JSON encoding, write and Python flush.
  It does not mean `fsync`, durable disk commit, downstream viewer display or completion of
  the future model/temporal pipeline. The sidecar `replay-timing.jsonl` records the age after
  this boundary. `frame_budget_ms` remains a separate, configurable diagnostic threshold;
  `--check-100ms` always uses 100 ms.

## Reproduce

Run from `Drishti-2.5/` with a fresh output directory:

```sh
uv run --frozen drishti replay --dataset ../data/dataset --sequence 08 \
  --mode geometric --output runs/NEW-O001-RUN --view none \
  --max-frames 100 --check-100ms
```

Expected exit code is 2 when any scan misses, while `summary.json` still records
`status: completed` if all selected scans were processed. The preserved output is
[`Drishti-2.5/runs/drishti-o001-paced-seq08-100-20260925/`](../../../Drishti-2.5/runs/drishti-o001-paced-seq08-100-20260925/).
The command wrote `manifest.json`, `frames.jsonl`, `replay-timing.jsonl` and `summary.json`.

## Observed result

MEASURED RESULT: all 100 frame reports and 100 sidecar timing records have contiguous IDs;
100/100 scan report ages exceeded 100 ms. Output age from scheduled arrival was 11,371.8 ms
p50, 21,014.1 ms p95, 21,903.7 ms p99 and 22,129.9 ms maximum. Maximum recorded load-start
lag was about 21,800 ms. Audit-inclusive work duration was 319.7 ms p50. Worker peak RSS
reported by this process was 202,473,472 bytes. The four report files total 100,833 logical
bytes. These are run-specific observations, not resource ceilings.

Verification compared all 100 `frame_id`, `input_digest`, `map_digest`, `cells` and `accounting`
records against the earlier headless sequence 08 baseline. All matched. The deadline sidecar
had 100/100 misses, agreeing with the summary. CLI exit code was 2 and
`replay_deadline_check_met` was false. `realtime_release_gate_met` stayed false.

## Exact grouping integration follow-up

A second 100-frame run used the packed-int64 grouping with overflow fallback from
[experiment 0003](0003-lossless-10hz-design.md) in the active `aggregate_cells` path.
Its saved output is
[`Drishti-2.5/runs/drishti-o001-packed-paced-seq08-100-20260925/`](../../../Drishti-2.5/runs/drishti-o001-packed-paced-seq08-100-20260925/).
The manifest source digest is
`9a005ab9e496164b40ea5504bb910c8c1205377ea373cb2c8d39bb0101f7558e`;
dataset, config, mode, view and scheduled 10 Hz workload were otherwise the same. The
run returned code 2 and completed 100/100 scans. Every frame ID, input/map digest, cell
count and accounting record matched the first paced run exactly. The grouping tests also
cover empty, negative, wide and int64-extreme keys against row-wise `np.unique`.

MEASURED RESULT: audit-inclusive per-frame duration fell from 319.7 ms p50 to 193.4 ms
p50 under these sequential runs. Scheduled-arrival-to-report-flush age fell from
11,371.8 ms to 4,952.4 ms p50, but all 100 scans still missed 100 ms; age peaked at
9,520.3 ms. The optimized run's p50 stages were load 26.5 ms, preprocessing 34.0 ms,
ground 25.4 ms, projection 32.7 ms and mapping 55.6 ms. Stage medians are separate
distributions and do not sum into a representative frame. The runs were not controlled
for cache, thermal or background load. This demonstrates exact sampled output and a
large local improvement, not a release deadline pass.

## Interpretation and limits

The current single-frame geometric path, including packed grouping, cannot meet the selected
100 ms per-scan deadline at the paced 10 Hz sequence 08 workload. Schedule lag accumulated
because service remained slower than arrivals; a finite queue would not remove this deficit.
A p50 work duration or
short storage commit measurement cannot establish the complete-path deadline. This run
does not test the model, temporal state, viewer cost, independent arrival, sustained release
window, process-tree memory or allocated disk budget. AC-008 remains NOT VERIFIED for the
future complete path and O-001 stays IN PROGRESS.

## Nearest-return projection follow-up

A third 100-frame run retained packed grouping and replaced the range-image `np.lexsort`
winner search with exact minimum range per pixel, then minimum original point ID for
equal-range ties. The output is
[`Drishti-2.5/runs/drishti-o001-packed-scatter-paced-seq08-100-20260925/`](../../../Drishti-2.5/runs/drishti-o001-packed-scatter-paced-seq08-100-20260925/).
Its manifest source digest is
`5e4aa0e69760ec6b16966da0cbdd5a40cda166966de1660eea5c1a73e2b94bf0`.
Projection contract tests still cover nearest return, equal-range original-ID ties and
out-of-FOV behavior. All 100 frame IDs, input/map digests, cell counts and accounting
records matched the packed-grouping run exactly.

MEASURED RESULT: projection stage p50 was 15.7 ms versus 32.7 ms in the earlier packed
run; audit-inclusive frame work p50 was 177.2 ms versus 193.4 ms. The 10 Hz scheduled
output age was 4,172.0 ms p50 and 7,985.2 ms maximum, with 100/100 misses and exit code
2. These sequential runs do not isolate machine-state variation and still exclude all
future learned/temporal stages. The current path remains over the deadline.

## Ordered point-ID validation follow-up

`ScanFrame` now checks strictly increasing point IDs in linear time and uses the full
uniqueness check only when IDs are unordered. This preserves the contract for arbitrary
unique nonnegative IDs while avoiding NumPy's expensive hash uniqueness operation for
SemanticKITTI's original index order. Direct tests accept ordered and unordered unique
IDs and reject duplicates and negatives. The two saved current-path runs are
[`sequence 08`](../../../Drishti-2.5/runs/drishti-o001-ordered-ids-paced-seq08-100-20260925/)
and [`sequence 00`](../../../Drishti-2.5/runs/drishti-o001-ordered-ids-paced-seq00-100-20260925/).
The sequence 08 manifest source digest is
`e5a48bce30df8c161091ed782919b3314e5be78357ea998b62d2438a466575f3`.

MEASURED RESULT: sequence 08 frame load p50 fell from 26.5 to 1.7 ms; audited work
p50 was 149.0 ms and all 100 scans still missed. Sequence 00 had 1.7 ms load p50,
138.9 ms audited work p50 and 100/100 misses. All 100 input/map digests, frame IDs,
cell counts and accounting records in each sequence matched its earlier headless
baseline. The two runs cover more than one sequence but do not establish long-run,
cross-configuration or future complete-path equivalence.

A later memoryview-based snapshot-digest trial produced an exact-output 100-frame
[sequence 08 run](../../../Drishti-2.5/runs/drishti-o001-digest-view-paced-seq08-100-20260925/)
with 149.8 ms audited p50 and 100/100 misses. It did not improve the full replay
result compared with the 149.0 ms ordered-ID run. The change was reverted; the run
remains as negative evidence, with its distinct source digest in its manifest.

## Current-laptop replay after finite-coordinate preprocessing

The active path also replaced two row-wise maximum reductions with pairwise `np.maximum`
and made the finite-geometry mask from three column-wise `np.isfinite` arrays. The latter
retains the rejection of nonfinite coordinates; a focused test covers an infinite input.
An intermediate [sequence 08 run](../../../Drishti-2.5/runs/drishti-o001-pairwise-max-paced-seq08-100-20260925/)
had 139.7 ms audited work p50. A subsequent finite-mask
[run](../../../Drishti-2.5/runs/drishti-o001-finite-check-paced-seq08-100-20260925/)
had 137.4 ms p50. Both matched the prior sequence 08 frame outputs and missed 100/100
deadlines. These sequential observations do not isolate the effect of each change from
machine-state variation.

Fresh current-laptop 100-frame runs with the same source digest
`1cae07e7387d8dec0ad9d5c02c7ec49819b4d9b5ffaeef8072fd7d236a17b8d7` are
[`sequence 08`](../../../Drishti-2.5/runs/drishti-o001-current-laptop-seq08-100-20260925/)
and [`sequence 00`](../../../Drishti-2.5/runs/drishti-o001-current-laptop-seq00-100-20260925/).
Both used the original 10 Hz virtual arrival schedule, geometric mode, no viewer, the
default configuration and a new output directory. Each completed 100 scans and returned
code 2. All 200 frame IDs, input/map digests, cell counts and accounting records matched
the original 2026-09-24 headless baselines; timing sidecars had contiguous IDs and their
miss counts agreed with the summaries.

| Sequence | Audited work p50/p95/p99 (ms) | Output age p50/p95/p99/max (ms) | Deadline misses | Worker peak RSS |
| --- | --- | --- | --- | --- |
| 08 | 137.0 / 145.1 / 156.9 | 2135.6 / 3687.4 / 3850.2 / 3891.6 | 100/100 | 207,708,160 bytes |
| 00 | 125.1 / 131.2 / 138.6 | 1423.0 / 2450.5 / 2559.1 / 2587.9 | 100/100 | 193,130,496 bytes |

MEASURED RESULT: the current geometric path still fails the selected deadline on both
sequences. Sequence 08 stage p50 values were 1.76 ms load, 19.83 ms preprocessing,
25.16 ms ground, 15.45 ms projection and 55.73 ms mapping. Sequence 00 mapping p50 was
49.71 ms. Stage medians are different distributions and should not be summed as one scan.
The four report files occupied 101,010 and 100,987 logical bytes, respectively. No model,
temporal map, independently arriving producer, durable report commit or viewer publication
was measured. A one-frame random-label microbenchmark found `np.bincount` histogramming
faster than `np.add.at` (0.95 versus 2.57 ms median over five trials); it was not integrated
or tested as a full-run improvement at that stage.

## Fewer distance reductions and semantic histogram

On one sequence 08 frame, computing radial cell-footprint distance from the two coordinate
columns instead of a row-wise norm reduced `resolve_owners` median from 18.58 to 9.99 ms
over ten trials with identical level and index arrays. This was integrated, followed by
column-wise Euclidean norms in preprocessing and projection and an integer `np.bincount`
semantic histogram. The histogram uses the existing 20 learning IDs and preserves int64
evidence counts. A competing sorted `reduceat` candidate for height bounds and ground sums
was rejected: it matched one frame but took 19.78 ms versus 4.97 ms for the current
reductions over five trials.

An intermediate [ownership-only 100-frame replay](../../../Drishti-2.5/runs/drishti-o001-owner-distance-paced-seq08-100-20260925/)
matched every prior sequence 08 frame output; mapping p50 was 49.21 versus 55.73 ms and
audited work p50 was 130.98 versus 137.02 ms. A subsequent
[distance-reduction replay](../../../Drishti-2.5/runs/drishti-o001-distance-reductions-paced-seq08-100-20260925/)
also matched all outputs and had 122.75 ms audited work p50. Both missed all 100 deadlines.
These sequential runs were not controlled for local machine state.

The final source digest for this follow-up is
`3e466ed0104c0a85bd16f33ae0df5f3507ab40eda7b85c70a75e6124cc56acbc`.
Fresh [sequence 08](../../../Drishti-2.5/runs/drishti-o001-reductions-histogram-paced-seq08-100-20260925/)
and [sequence 00](../../../Drishti-2.5/runs/drishti-o001-reductions-histogram-paced-seq00-100-20260925/)
geometric replays each completed 100 scans at the same virtual 10 Hz schedule, returned
code 2 and matched the original 2026-09-24 frame IDs, input/map digests, cell counts and
accounting. Timing sidecar IDs were contiguous and miss totals agreed with summaries.

| Sequence | Audited work p50/p95/p99 (ms) | Output age p50/p95/p99/max (ms) | Misses | Mapping p50 (ms) |
| --- | --- | --- | --- | ---: |
| 08 | 122.3 / 126.7 / 144.0 | 1333.2 / 2249.1 / 2352.2 / 2378.0 | 100/100 | 47.93 |
| 00 | 108.3 / 114.8 / 130.5 | 668.9 / 976.1 / 1016.8 / 1030.8 | 100/100 | 40.74 |

The nonzero-label path was also checked with a fresh
[50-frame sequence 00 oracle replay](../../../Drishti-2.5/runs/drishti-o001-histogram-oracle-seq00-50-20260925/).
It completed with code 0 and matched all 50 prior oracle frame IDs, input/map digests,
cell counts and accounting records. A focused unit test checks unknown, car and
traffic-sign evidence within one cell. Full suite: 50 passed; Ruff lint/format, mypy and
source/wheel build passed. These checks show exact sampled behavior, not a 100 ms pass.
The future model, detector, tracker, temporal map and viewer are still absent from this
measurement; the complete-path release gate remains NOT VERIFIED.

## Native ground input dtype follow-up

The installed `pypatchworkpp.patchworkpp.estimateGround` binding declares float32 array
input. `PatchworkGround.segment` previously converted accepted float32 points to float64
before that call. A first-scan comparison produced identical ground and nonground index
arrays for float64 and float32 Nx4 inputs; omitting intensity changed indices and was
rejected. The runtime now passes the accepted float32 Nx4 points directly, and its local
protocol matches the installed binding.

The final source digest is
`925a4c0ed05ffd29892dfd98073865b8952205998a7739f4131c4453f9a1a03d`.
The [sequence 08](../../../Drishti-2.5/runs/drishti-o001-native-float32-final-seq08-100-20260925/)
and [sequence 00](../../../Drishti-2.5/runs/drishti-o001-native-float32-paced-seq00-100-20260925/)
100-frame geometric replays completed with expected code 2. All 200 frame IDs, input/map
digests, cell counts and accounting matched their original baselines; both timing sidecars
had 100 misses. A separate
[50-frame oracle run](../../../Drishti-2.5/runs/drishti-o001-native-float32-oracle-seq00-50-20260925/)
matched its prior oracle baseline. The oracle source digest differs only by the subsequent
typing-only protocol edit; the native call and processing code were unchanged.

| Sequence | Audited work p50/p95/p99 (ms) | Output age p50/p95/p99/max (ms) | Misses |
| --- | --- | --- | --- |
| 08 | 120.3 / 126.7 / 133.6 | 1260.2 / 2087.1 / 2183.5 / 2210.1 | 100/100 |
| 00 | 108.4 / 113.9 / 123.6 | 607.3 / 912.3 / 956.6 / 968.8 | 100/100 |

MEASURED RESULT: sequence 08 ground stage p50 was 24.34 ms with the float32 path versus
25.33 ms in the preceding distance/histogram run; audited work p50 was 120.3 versus
122.3 ms. These sequential runs do not isolate cache or machine load. All 200 paced
deadlines still fail, and the future complete-path release gate remains NOT VERIFIED.

## High-density boundary scan

The structure-only dataset report identified sequence 10 frame 206 as the extracted
dataset's largest scan by file size: 129,392 points. A fresh
[one-frame paced replay](../../../Drishti-2.5/runs/drishti-o001-high-density-seq10-frame206-20260925/)
on the final source digest used `--sequence 10 --start-frame 206 --max-frames 1
--mode geometric --view none --check-100ms`. It loaded and accepted all 129,392 points,
completed with exit code 2 and recorded 129.13 ms scheduled-arrival-to-report-flush age,
so its one deadline missed. The snapshot arrays occupied 5,583,307 logical bytes and
worker peak RSS was 115,822,592 bytes for that process.

This is a cold-start scan with a new Patchwork++ engine and no preceding frames. It
checks the near-130,000-point development boundary and first-scan deadline, but neither
the entire sequence nor a warm steady-state distribution. Its map output has no
same-frame prior baseline comparison; accounting and saved artifacts were inspected.
