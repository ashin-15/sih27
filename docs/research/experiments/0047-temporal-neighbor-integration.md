# Experiment 0047: exact temporal neighbour lookup

Date: 2026-10-15. RQ-004 / R-SYSTEM; T-008 and O-006. This is a bounded CPU
optimization of the optional diagnostic temporal map. It does not change its
output contract or establish the 100 ms release gate.

## Reproduction

Windows 11, Intel Family 6 Model 186, Python 3.12.14, NumPy 2.5.3 and
pypatchworkpp 1.4.1. From `Drishti-2.5/`:

```text
.venv/Scripts/python.exe -m drishti demo --output runs/synthetic-temporal-neighbor-20261015 --view none --frames 30 --temporal
.venv/Scripts/python.exe ../docs/research/experiments/0047-temporal-output-pair.py runs/synthetic-temporal-screen-1791965858559 runs/synthetic-temporal-neighbor-20261015
.venv/Scripts/python.exe ../docs/research/experiments/0048-temporal-step-ab.py --frames 30 --repeats 10
```

The A/B script rebuilds the same 30-frame geometric synthetic state, checks
both full rise/drop arrays for equality at each level, then times ten calls
per implementation. The run uses no model, candidates, tracking, visibility,
evaluator or viewer. Power state and concurrent load were uncontrolled.

## Results

MEASURED RESULT: all 30 saved records match for frame ID, input digest, map
digest, accounting and temporal summary. A boundary and slot-reuse regression
also passes. The local A/B result was:

| Level | Published cells | Previous lookup | Current lookup |
| --- | ---: | ---: | ---: |
| 0 | 33,362 | 27.479 ms | 24.654 ms |
| 1 | 119,276 | 112.620 ms | 86.175 ms |
| 2 | 11,576 | 8.906 ms | 7.215 ms |

The isolated sum is 149.005 versus 117.044 ms, a 31.961 ms saving on this
late synthetic state. The 30-frame temporal stage p50 was 324.454 ms in the
earlier saved report and 273.175 ms in the current report. Those complete runs
were on different dates and working trees, so their difference cannot be
attributed solely to this edit. The isolated A/B is the direct evidence.

A three-frame learned sequence-08 CUDA replay with FRNet, candidates, tracks,
visibility, temporal fusion and schema-5 evaluation completed with three
accepted receipts. Its input/map digests, accounting and temporal summaries
match a preceding three-frame instrumented replay. The new report is retained
at `artifacts/gpu-temporal-neighbor-20261015`; all three audit-inclusive
frames missed the configured 100 ms budget. This was a short run with
uncontrolled concurrent test activity and is not a latency comparison.

An additional screen skipped step calculations for cells without valid ground.
It retained saved-output equality but worsened 30-frame temporal p50 from
273.175 to 280.237 ms; that change was reverted.

## Judgment

DESIGN DECISION: retain the exact neighbour lookup and regression. Temporal
view construction still costs hundreds of milliseconds; complete current-path
FRNet, visibility and receipt validation have separate large costs. T-008 and
O-006 remain IN PROGRESS. No AC-008 acceptance or full GPU implementation is
claimed.
