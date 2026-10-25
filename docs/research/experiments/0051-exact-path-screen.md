# Experiment 0051: receipt, visibility and paced learned replay

Dates: 2026-10-20 and 2026-10-22. RQ-004 / R-SYSTEM; T-008, O-001/O-006,
and T-006 installed-wheel verification. This is current-path development
evidence, not complete-product acceptance.

## Setup and changes

Windows, RTX 4050 Laptop GPU (6,141 MiB), driver 561.00, Python 3.12.14.
Power/thermal state and concurrent system activity were uncontrolled.
Sequence 08 scans 000000-000005, original pinned FRNet checkpoint SHA-256
`09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`.
Learned CUDA mapping, fp32 FRNet with NumPy interpolation, candidates,
tracking, visibility, diagnostic temporal fusion, sampled deep audit every
100 frames (including the first), and no viewer were enabled throughout.

The profile in `artifacts/profile-20261020-before.prof` identified the
schema-5 raw digest stream and visibility as costs. Implemented:

- Encode ordinary JSON scalar values directly into the existing typed digest
  stream; cache bounded immutable dataclass field-name metadata. No frame or
  array cache, changed digest bytes, skipped checks or changed audit schedule.
- Remove adjacent identical (cell, beam) samples before the visibility sort.
  Keep the later distinct-pair reduction, support counts and minimum proof ID.
- Add paced learned replay through the accepted current product receipt,
  report schema 8: [decision 0012](../../decisions/0012-paced-learned-diagnostic.md).
  The fused arrays remain outside the validated payload, although fusion runs
  inside the timed processing path.

## Matched GPU screen, 2026-10-20

The four six-frame runs used reference/current/current/reference order in one
process with a fresh sequence engine each time. The reference functions were
saved before editing under `artifacts/performance-20261020-reference/`.
The uninstrumented reports and a separate instrumented parity run are under
`artifacts/performance-20261020-abba-v2/`. Warm statistics omit frame zero.

| Run | Implementation | Visibility p50 | Receipt validation p50 | Processing p50 | Load through publication p50 |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 | Reference | 334.09 ms | 235 ms | 1,075.08 ms | 1,360.39 ms |
| 1 | Current | 308.24 ms | 157 ms | 1,109.30 ms | 1,348.10 ms |
| 2 | Current | 320.62 ms | 172 ms | 1,143.37 ms | 1,390.20 ms |
| 3 | Reference | 325.75 ms | 265 ms | 1,140.51 ms | 1,457.90 ms |

MEASURED RESULT: all 24 receipts were accepted; all 24 frames exceeded the
configured publication budget. Frame input/map digests, accounting,
candidate bounds/support/class summaries, tracks, visibility and temporal
summaries matched across runs. The separate same-input check matched all
30 reduced visibility chunks exactly and all six complete schema-5 digests
between the original and optimized encoders. Isolated digest p50 decreased
124.03 -> 56.16 ms; corridor chunk p50 decreased 12.57 -> 10.35 ms. Chunk
p95 did not improve (25.44 -> 26.70 ms); no tail guarantee is inferred.

Receipt reduction is clear on these samples. Whole-path gains are small and
variable because other stages dominate; these results do not support a large
overall speedup, sustained throughput, peak-memory claim or 100 ms pass.

## Paced learned diagnostic, 2026-10-22

`artifacts/learned-paced-source-20261022/` contains six accepted schema-5
receipts, six prediction files and report schema 8. MEASURED RESULT: warm
processing p50 1,157.89 ms; warm load-through-receipt p50 1,383.73 ms.
The summary's audit-inclusive p50 is 1,431.11 ms across all six frames,
including cold frame zero; it is a different metric.
All six scheduled-arrival deadlines failed. Receipt age grew from 3,687.65 ms
on scan zero to 10,181.29 ms on scan five; this includes accumulated schedule
lag and is distinct from each frame's service time. No scans were dropped.
The release flag stayed false. The outer PowerShell tool reported failure;
the CLI's documented miss result is 2 and is checked by the fixture and wheel
launcher. This short failed diagnostic is not the full 08/00/cold-density gate.

The source/wheel comparison and final validation results are linked in
[testing](../../testing.md) and the dated [work log](../../work-log.md).
The installed wheel uses a fresh package target with the existing locked
dependency environment; it is not a clean dependency installation.

MEASURED RESULT: source/wheel warm service through receipt was 1,383.73 /
4,285.68 ms p50. The wheel's warm processing was 3,637.07 ms and last scheduled
receipt age 31,507.86 ms. Both accepted 6/6 receipts and missed 6/6 deadlines.
The wheel launcher recorded CLI exit 2. All six prediction files matched
byte for byte, all compared report evidence matched, and all 27 installed
Python files matched final source. The slower wheel run is preserved, not
discarded or attributed to packaging without evidence; power, thermals and
system load were uncontrolled. See [saved verification](0051-validation-20261022.json).

## Reproduction

From `Drishti-2.5/`, use new output directories:

```text
.venv/Scripts/python.exe ../docs/research/experiments/0051-exact-path-screen.py <new-output> --reference ../artifacts/performance-20261020-reference
.venv/Scripts/python.exe -m drishti replay --dataset ../data/semantickitti --sequence 08 --mode learned --device cuda --frnet-runtime torch --frnet-checkpoint ../data/frnet-semantickitti_seg.pth --frnet-checkpoint-sha256 09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e --detect-obstacles --track-obstacles --visibility --temporal --evaluate-product-contract --audit-every 100 --view none --max-frames 6 --write-predictions --check-100ms --output <new-output>
```

For an independent reference checkout, supply its pre-change `visibility.py`
and `product_result.py` to the screen. The harness extracts only the original
functions and restores patched functions afterward. Retain failed runs:
`performance-20261020-abba` completed its first six-frame baseline, then its
initial reporting code incorrectly read the unavailable unpaced receipt-age
field. The corrected harness uses the recorded publication and product
validation fields. The 2026-10-22 GPU model-grouping screen failed strict
confidence equality; see [experiment 0052](0052-frnet-repeatability-screen.md).

NOT VERIFIED: complete fused schema, independent final quality, controlled
long-run tails and peak RSS/VRAM, or AC-008. T-008/O-001/O-006 remain IN PROGRESS.
