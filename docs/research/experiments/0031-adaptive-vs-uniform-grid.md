# EXP-2026-031 - Adaptive versus uniform 5 cm grid, single-frame payload

Status: Completed
Research question: RQ-004 (real-time and resource feasibility); SIH26053 asks for evidence of
reduced memory versus a uniform high-resolution map.
Objective: measure how many observed cells and how many snapshot array bytes the default
adaptive grid stores, compared with a uniform 5 cm grid over the same 100 m radius and scans.
Hypothesis: the adaptive rings store fewer observed cells because sparse far returns share
coarser cells.
Setup and environment: this Intel laptop CPU, `drishti-25` 0.1.0, NumPy 2.5.3, pypatchworkpp
1.4.1, repository commit `b764411` with local working-tree changes, geometric mode, `--view none`,
unpaced replay, SLAM poses.
Inputs and dataset split: SemanticKITTI sequence 08, frames 0 to 19 (20 scans, mean 123,558
accepted points per scan). Both runs report the same input source digest
`0502866f9bedd39f807945785b07a6749a96110260c18ab4f529db9397bb9f4d`.
Configuration and checkpoint hashes:
- Adaptive: `Drishti-2.5/configs/default.toml` (5/10/50 cm cells to 10/25/100 m, radial),
  config digest `ce31fff9d82ef960a703d0558456514d3be6d86c13c411899ec52e361e3838db`.
- Uniform: [0031-uniform-5cm.toml](0031-uniform-5cm.toml) (5 cm cells to 100 m, radial,
  other fields default), config digest
  `e743d02f12b52dcfbb707e6fbfd8031a92fef68136f52cce0a276f9fb1356e88`.
- No model checkpoint is used in geometric mode.
Baseline: the uniform 5 cm 2.5D grid. This is not the uniform 3D voxel map named in SIH26053.
Metrics and acceptance thresholds: per-frame `cells` and `snapshot_array_bytes` from
`frames.jsonl`. No acceptance threshold is defined; this is a descriptive comparison.
Expected outcome: fewer cells and bytes for the adaptive grid.

Observed outcome: MEASURED RESULT

| 20 scans, sequence 08 | Adaptive 5/10/50 cm | Uniform 5 cm | Change |
| --- | ---: | ---: | ---: |
| Observed cells, mean (min to max) | 55,529 (54,832 to 55,972) | 83,603 (82,453 to 84,821) | 33.6% fewer |
| Snapshot array bytes, mean | 15,714,580 | 23,659,677 | 33.6% smaller |
| Mapping stage median, ms | 40.2 | 39.6 | no measured speed gain |

Reports are saved in
[the adaptive run](../../../Drishti-2.5/runs/drishti-grid-compare-adaptive-seq08-20-20260929/)
(`frames.jsonl` SHA-256 `193b165adf59758f7d2d5052853352996706bcd7590d0174ad71b52eecbf9e92`) and
[the uniform run](../../../Drishti-2.5/runs/drishti-grid-compare-uniform5cm-seq08-20-20260929/)
(`frames.jsonl` SHA-256 `af342bfb2d719a68a433f54fc1c2947ef8ba624cac889a82176e26a0616453fe`).

DESIGN CALCULATION, not a measurement: a fully covered 100 m disc needs about 12,566,371 cells
at 5 cm and about 408,407 cells with the default rings, about 31 times fewer. Drishti stores
only observed cells, so the measured saving above is the relevant figure for a single scan.

Interpretation: on these scans the adaptive grid stores about one third fewer cells and array
bytes than a uniform 5 cm grid. Most returns fall within 25 m, where the rings are fine, so the
saving is modest per scan. The full-coverage ratio shows why the saving grows once a map covers
the whole disc, but no temporal map exists to measure that.
Limitations: 20 consecutive scans from one sequence; single-frame maps only; snapshot array
bytes are logical payload, not process memory; no 3D voxel baseline; no accuracy comparison
between the two grids; timings are unpaced local observations.
Reproduction commands (from `Drishti-2.5/`):

```bash
uv run --frozen drishti replay --config configs/default.toml \
  --output /tmp/NEW_ADAPTIVE --view none --dataset ../data/dataset --sequence 08 --max-frames 20
uv run --frozen drishti replay --config ../docs/research/experiments/0031-uniform-5cm.toml \
  --output /tmp/NEW_UNIFORM --view none --dataset ../data/dataset --sequence 08 --max-frames 20
```

Conclusion: the adaptive grid measurably reduces single-frame stored cells and array payload
by 33.6% on this sample. It does not establish a process-memory, 3D-map or real-time result.
Next action: repeat over full sequences and several scenes; add a 3D voxel baseline and
process-memory measurement if the memory claim becomes an acceptance gate.
