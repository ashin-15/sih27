# Experiment 0018: reconstruct the process-return timing boundary

Status: MEASURED RESULT from saved current geometric replay reports, 2026-09-25.
RQ-004, O-001/T-008. This is a diagnostic bound, not a consumer receipt or
complete-product release measurement.

## Question and method

Would stopping the current 100 ms clock when `MappingEngine.process` returns
make the already saved paced runs pass? The headless CLI records the start lag
from each scheduled arrival, `load_process_publish_ms`, the process-only
stage time, and the later audit-report age. In headless mode its intervening
viewer `publish` step is absent and the publication duration is negligible.
For each frame, this analysis adds `load_start_lag_ms +
load_process_publish_ms` to approximate scheduled arrival to the process
return, including dataset loading and accumulated lag. It does not re-time
the original run or assert that a complete consumer received it.

The source reports are the existing [sequence 08](../../../Drishti-2.5/runs/drishti-o001-reuse-frame-arrays-seq08-100-20260925/)
and [sequence 00](../../../Drishti-2.5/runs/drishti-o001-reuse-frame-arrays-seq00-100-20260925/)
100-frame headless runs. Each `frames.jsonl` ID was matched to the corresponding
`replay-timing.jsonl` ID. Both use the same exact-output candidate described
in [experiment 0016](0016-reuse-accepted-frame-arrays.md).

## Result

| Sequence | Process-only time above 100 ms | Approximate process-ready age above 100 ms | Audit-report age above 100 ms | Approximate process-ready age p50/p95/max |
| --- | ---: | ---: | ---: | ---: |
| 08 | 3/100 | 100/100 | 100/100 | 586.80 / 904.71 / 979.80 ms |
| 00 | 2/100 | 67/100 | 82/100 | 122.13 / 161.70 / 162.78 ms |

The first process-ready ages were 122.75 and 120.96 ms on 08 and 00. The
process-only medians were 87.33 and 82.97 ms, but their maxima were 118.51
and 115.81 ms. Post-process digest/audit work also delays the next scan in
this sequential CLI, so simply moving the timestamp before that work cannot
remove all accumulated lag.

## Reproduction and limits

Read both JSONL files, assert matching frame IDs, and compute the same three
counts with these expressions per frame:

```python
ready_age_ms = timing["load_start_lag_ms"] + frame["load_process_publish_ms"]
process_missed = frame["timings_ms"]["total_ms"] > 100.0
ready_missed = ready_age_ms > 100.0
report_missed = timing["report_output_age_ms"] > 100.0
```

This reconstruction includes the negligible headless publication interval
and uses values rounded only for display. It does not simulate a separate
consumer, eliminate audit work, prove a warmup policy, or include learned,
detection, temporal, persistence or viewer stages. The laptop load was not
controlled. Even this optimistic process-return boundary fails the selected
zero-miss rule on both saved runs. O-001 remains IN PROGRESS and AC-008 remains
NOT VERIFIED.
