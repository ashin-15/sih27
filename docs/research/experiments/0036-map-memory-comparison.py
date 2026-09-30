"""Adaptive 2.5D grid memory versus uniform 5 cm 2.5D and 3D grids (experiment 0036).

Run from Drishti-2.5. Uses the shared MappingEngine (geometric CPU path: the same cell
lattice, ownership and per-cell layers as the learned path) on frames spread over
sequence 08. Reports measured snapshot cells and logical array bytes, plus analytic
dense-allocation counts for the adaptive rings and uniform references. Snapshot bytes
are map payload, not process memory.
"""

import argparse
import json
import math
import statistics
from pathlib import Path

import numpy as np

from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.pipeline import MappingEngine


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=80)
    parser.add_argument("--height-min-m", type=float, default=-3.0)
    parser.add_argument("--height-max-m", type=float, default=5.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = MappingConfig()
    engine = MappingEngine(config, mode=Mode.GEOMETRIC)
    source = DatasetSource(args.dataset, "08")
    cells: list[int] = []
    payload: list[int] = []
    per_level: list[list[int]] = []
    for frame_id in range(0, source.frame_count, args.stride):
        frame = next(source.frames(start_frame=frame_id, max_frames=1))
        snapshot = engine.process(frame).snapshot
        cells.append(len(snapshot.level))
        payload.append(snapshot.array_bytes)
        per_level.append(np.bincount(snapshot.level, minlength=len(config.cell_sizes_cm)).tolist())
    bytes_per_cell = statistics.median(p / c for p, c in zip(payload, cells, strict=True))
    sizes_m = [size / 100 for size in config.cell_sizes_cm]
    radii = config.radii_m
    # Dense cell counts over the radial footprint (disk and annuli).
    ring_area = [math.pi * radii[0] ** 2] + [
        math.pi * (radii[i] ** 2 - radii[i - 1] ** 2) for i in range(1, len(radii))
    ]
    adaptive_dense = sum(area / size**2 for area, size in zip(ring_area, sizes_m, strict=True))
    uniform_2d = math.pi * radii[-1] ** 2 / sizes_m[0] ** 2
    height_cells = round((args.height_max_m - args.height_min_m) / sizes_m[0])
    uniform_3d = uniform_2d * height_cells
    median_cells = statistics.median(cells)
    report = {
        "frames": len(cells),
        "stride": args.stride,
        "config": {"cell_sizes_cm": config.cell_sizes_cm, "radii_m": config.radii_m},
        "measured": {
            "cells_median": median_cells,
            "cells_max": max(cells),
            "snapshot_bytes_median": statistics.median(payload),
            "snapshot_bytes_max": max(payload),
            "bytes_per_cell_median": bytes_per_cell,
            "cells_per_level_median": [
                statistics.median(level[i] for level in per_level)
                for i in range(len(config.cell_sizes_cm))
            ],
        },
        "analytic_cells": {
            "adaptive_rings_dense": adaptive_dense,
            "uniform_5cm_2_5d": uniform_2d,
            "uniform_5cm_3d_voxels": uniform_3d,
            "height_range_m": [args.height_min_m, args.height_max_m],
        },
        "bytes": {
            "adaptive_measured_median": statistics.median(payload),
            "adaptive_rings_dense_same_layers": adaptive_dense * bytes_per_cell,
            "uniform_5cm_2_5d_same_layers": uniform_2d * bytes_per_cell,
            "uniform_5cm_3d_1_byte_per_voxel": uniform_3d,
        },
    }
    measured = report["bytes"]["adaptive_measured_median"]
    report["ratios_vs_measured_adaptive"] = {
        key: value / measured for key, value in report["bytes"].items()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
