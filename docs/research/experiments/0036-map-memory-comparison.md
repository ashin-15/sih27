# Experiment 0036: adaptive 2.5D map memory versus uniform grids

Date: 2026-09-30. Question: the SIH26053 memory-reduction deliverable. Script:
`0036-map-memory-comparison.py` (run from `Drishti-2.5`), output
`C:\Users\Robin Joe\drishti-local\artifacts\map-memory-seq08-20260930.json`.

Method: the shared `MappingEngine` geometric CPU path (same lattice, ownership and
per-cell layers as the learned path) on 51 sequence-08 scans (every 80th). Snapshot
bytes are logical map array payload, not process memory. Uniform references use the
same 100 m radial footprint; the 3D reference spans -3..+5 m at 5 cm with 1 byte per
voxel.

MEASURED RESULT: median 44,375 cells (max 58,159) and 12.56 MB (max 16.46 MB) per
snapshot, 283 B per cell; median cells per ring 26,488 / 14,380 / 2,211 (5 / 10 / 50 cm).

Analytic comparison: fully allocated adaptive rings 408,407 cells versus 12,566,371
uniform 5 cm cells (30.8x fewer cells). Against the measured snapshot: uniform 5 cm
2.5D with the same layers 3.56 GB (283x), uniform 5 cm 3D occupancy 2.01 GB (160x),
fully allocated adaptive rings 116 MB (9.2x).

Limits: single-frame snapshots, not a persistent map; the per-cell layout is not
size-optimised (20 int64 semantic counters are 160 B per cell); the 3D reference
stores only 1-byte occupancy, so it is favourable to the uniform grid.
