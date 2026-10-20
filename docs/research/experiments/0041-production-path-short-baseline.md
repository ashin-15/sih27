# Experiment 0041: short complete-current-path GPU baseline

Date: 2026-10-13. Question: RQ-004, complete-path 100 ms feasibility.
Module: R-SYSTEM. Host: local RTX 4050 Laptop GPU, 6,141 MiB, driver 561.00;
the recorded `nvidia-smi` idle power draw was 9.02 W. Power mode and concurrent
load were not controlled. Code: existing working tree, including uncommitted
decision-0011 temporal implementation, before the CLI provenance correction.

Command from `Drishti-2.5/` (checkpoint SHA-256 shown in full):

```powershell
uv run --no-sync drishti replay --dataset ../data/semantickitti --sequence 08 --mode learned --device cuda --frnet-runtime torch --frnet-checkpoint ../data/frnet-semantickitti_seg.pth --frnet-checkpoint-sha256 09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e --detect-obstacles --track-obstacles --visibility --temporal --evaluate-product-contract --audit-every 100 --view none --max-frames 3 --output ../artifacts/production-baseline-20261013-3f
```

The output directory is new and ignored, under this workspace. Source scans and
labels were not modified. All three current schema-5 product receipts were
accepted. The diagnostic fused map is outside those receipts. The run was not
paced, so its configured 100 ms budget is not AC-008 deadline evidence.

## Measured results (ms)

| Frame | Model | Ground | Projection | Mapping | Candidates | Visibility | Temporal | Processing total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0, cold | 1,881 | 81 | 858 | 708 | 403 | 863 | 367 | 5,260 |
| 1 | 542 | 66 | 14 | 92 | 80 | 428 | 358 | 1,615 |
| 2 | 211 | 73 | 9 | 92 | 118 | 431 | 323 | 1,290 |

The summary reports steady processing p50 1,452 ms, three of three
audit-inclusive frame budgets missed, and `realtime_release_gate_met=false`.
This small, uncontrolled sample cannot supply p99, sustained throughput or a
release judgment. It does expose multiple individually over-budget stages:
model, visibility and temporal update. Candidate generation also exceeded
100 ms on frame 2. The next performance experiment should profile warm
complete frames, GPU synchronization/transfers, evaluator cost and power state
before choosing an optimization. Any changed stage must preserve CPU-reference
output and quality gates.

The manifest incorrectly stated `no temporal fusion` and described a
single-frame scope while `--temporal` was enabled. The CLI provenance text and
its regression fixture were corrected after this run; the saved artifact is
preserved as evidence of the issue. No data contract was changed.
