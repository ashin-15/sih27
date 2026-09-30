"""Offline false-free scoring of saved observed-free cells against SemanticKITTI voxels.

Evaluation only: voxel labels are read here and never by inference. The completion grid is
256 x 256 x 32 voxels of 0.2 m in the scan's velodyne frame, assumed to span x 0..51.2 m,
y -25.6..25.6 m and z -2.0..4.4 m in x-major order. That layout is checked on every scored
frame by voxelizing the scan and comparing it with the provided input occupancy (``.bin``).
"""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from drishti.dataset import DatasetSource
from drishti.semantics import CLASS_NAMES, decode_semantickitti
from drishti.visibility import GROUND_SEMANTIC_IDS

VOXEL_SIZE_M = 0.2
GRID = (256, 256, 32)
GRID_MIN_M = np.array([0.0, -25.6, -2.0])
BAND_TOLERANCE_M = VOXEL_SIZE_M
SAMPLE_SPACING_M = 0.1
RANGE_EDGES_M = (20.0, 50.0)
SPEED_EDGES_MPS = (5.0, 10.0)
MOVING_RAW_MIN = 252


def unpack_bits(packed: NDArray[np.uint8]) -> NDArray[np.bool_]:
    """SemanticKITTI bit packing: most significant bit first."""
    return np.unpackbits(packed).astype(np.bool_)


def voxel_index(points_sensor: NDArray[np.float64]) -> tuple[NDArray[np.int64], NDArray[np.bool_]]:
    index = np.floor((points_sensor - GRID_MIN_M) / VOXEL_SIZE_M).astype(np.int64)
    inside = np.all((index >= 0) & (index < np.asarray(GRID)), axis=1)
    return index, inside


def input_occupancy_iou(scan: NDArray[np.float32], packed_input: NDArray[np.uint8]) -> float:
    """IoU between the scan voxelized with the assumed layout and the provided input grid."""
    index, inside = voxel_index(scan[:, :3].astype(np.float64))
    ours = np.zeros(GRID, dtype=np.bool_)
    ours[tuple(index[inside].T)] = True
    theirs = unpack_bits(packed_input).reshape(GRID)
    union = int(np.count_nonzero(ours | theirs))
    return int(np.count_nonzero(ours & theirs)) / union if union else 1.0


def _cell_samples(
    level: NDArray[np.uint8], indices: NDArray[np.int32], sizes_cm: NDArray[np.int32]
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Map-frame sample points covering each cell footprint, and their owning cell."""
    points: list[NDArray[np.float64]] = []
    owners: list[NDArray[np.int64]] = []
    for current, size_cm in enumerate(sizes_cm.tolist()):
        rows = np.flatnonzero(level == current)
        if not len(rows):
            continue
        width = size_cm / 100
        steps = int(np.ceil(width / SAMPLE_SPACING_M)) + 1
        offsets = np.linspace(1e-6, width - 1e-6, steps)
        grid = np.stack(np.meshgrid(offsets, offsets, indexing="ij"), axis=-1).reshape(-1, 2)
        low = indices[rows].astype(np.float64) * width
        points.append((low[:, None, :] + grid[None]).reshape(-1, 2))
        owners.append(np.repeat(rows, len(grid)))
    if not points:
        return np.empty((0, 2)), np.empty(0, dtype=np.int64)
    return np.concatenate(points), np.concatenate(owners)


def score_frame(
    free: dict[str, NDArray[np.generic]],
    labels_raw: NDArray[np.uint16],
    invalid: NDArray[np.bool_],
    occluded: NDArray[np.bool_],
    tau_free_m: float,
) -> dict[str, NDArray[Any]]:
    """Per free cell: inside-volume, verifiable, false-free, occluded and blocking class."""
    level = free["level"].astype(np.uint8)
    count = len(level)
    samples, owner = _cell_samples(
        level, free["indices"].astype(np.int32), free["cell_sizes_cm"].astype(np.int32)
    )
    pose = free["map_from_sensor"].astype(np.float64)
    sensor_from_map = np.linalg.inv(pose)
    semantic = decode_semantickitti(labels_raw.astype(np.uint32)).semantic.reshape(GRID)
    raw = labels_raw.reshape(GRID)
    invalid = invalid.reshape(GRID)
    occluded = occluded.reshape(GRID)
    inside_cell = np.zeros(count, dtype=np.bool_)
    verifiable = np.zeros(count, dtype=np.bool_)
    false_free = np.zeros(count, dtype=np.bool_)
    unknown_hit = np.zeros(count, dtype=np.bool_)
    occluded_hit = np.zeros(count, dtype=np.bool_)
    moving_hit = np.zeros(count, dtype=np.bool_)
    blocking = np.zeros(count, dtype=np.uint8)
    return_z = free["return_z_m"].astype(np.float64)
    for z_offset in np.arange(-BAND_TOLERANCE_M, tau_free_m + BAND_TOLERANCE_M + 1e-9, 0.1):
        map_points = np.column_stack((samples, return_z[owner] + z_offset, np.ones(len(owner))))
        sensor = (map_points @ sensor_from_map.T)[:, :3]
        index, inside = voxel_index(sensor)
        rows = owner[inside]
        x, y, z = index[inside].T
        inside_cell[rows] = True
        valid = ~invalid[x, y, z]
        verifiable[rows[valid]] = True
        labels = raw[x, y, z]
        # Empty in the completed scene yet hidden from the first viewpoint: the free claim
        # covers space this scan could not have seen.
        occluded_hit[rows[valid & occluded[x, y, z] & (labels == 0)]] = True
        occupied = valid & (labels != 0)
        classes = semantic[x, y, z]
        obstacle = occupied & (classes != 0) & ~np.isin(classes, GROUND_SEMANTIC_IDS)
        # Raw IDs 252+ are moving objects; completion aggregates future scans, so these are
        # often traces of objects that arrived after this scan rather than missed obstacles.
        moving = obstacle & (labels >= MOVING_RAW_MIN)
        static = obstacle & ~moving
        false_free[rows[static]] = True
        blocking[rows[static]] = classes[static]
        moving_hit[rows[moving]] = True
        unknown_hit[rows[occupied & (classes == 0)]] = True
    return {
        "inside": inside_cell,
        "verifiable": verifiable,
        "false_free": false_free,
        "moving_hit": moving_hit,
        "unknown_hit": unknown_hit,
        "occluded_hit": occluded_hit,
        "blocking_class": blocking,
    }


def evaluate_false_free(
    dataset: Path, visibility: Path, sequence: str, tau_free_m: float = 0.10
) -> dict[str, object]:
    source = DatasetSource(dataset, sequence)
    voxel_dir = dataset / "sequences" / sequence / "voxels"
    saved = sorted((visibility / "sequences" / sequence).glob("*.npz"))
    frames = [path for path in saved if (voxel_dir / f"{path.stem}.label").exists()]
    if not frames:
        raise ValueError("no saved free-cell frame has matching voxel labels")
    poses = source.map_from_sensor
    times = source.timestamps_s
    totals: dict[str, int] = {}
    by_class: dict[str, int] = {}
    strata: dict[str, dict[str, int]] = {}
    alignment: list[float] = []

    def add(bucket: dict[str, int], key: str, value: int) -> None:
        bucket[key] = bucket.get(key, 0) + value

    for path in frames:
        frame_id = int(path.stem)
        with np.load(path, allow_pickle=False) as data:
            free = {name: data[name] for name in data.files}
        if not np.allclose(free["map_from_sensor"], poses[frame_id], atol=1e-9):
            raise ValueError(f"{path.name}: saved pose differs from the dataset pose")
        scan = np.fromfile(source.scan_paths[frame_id], dtype="<f4").reshape(-1, 4)
        alignment.append(
            input_occupancy_iou(scan, np.fromfile(voxel_dir / f"{path.stem}.bin", dtype=np.uint8))
        )
        result = score_frame(
            free,
            np.fromfile(voxel_dir / f"{path.stem}.label", dtype="<u2"),
            unpack_bits(np.fromfile(voxel_dir / f"{path.stem}.invalid", dtype=np.uint8)),
            unpack_bits(np.fromfile(voxel_dir / f"{path.stem}.occluded", dtype=np.uint8)),
            tau_free_m,
        )
        previous = max(frame_id - 1, 0)
        elapsed = times[frame_id] - times[previous]
        speed = (
            float(np.linalg.norm(poses[frame_id][:3, 3] - poses[previous][:3, 3]) / elapsed)
            if elapsed > 0
            else 0.0
        )
        speed_bin = (
            "0-5mps"
            if speed < SPEED_EDGES_MPS[0]
            else "5-10mps"
            if speed < SPEED_EDGES_MPS[1]
            else "10mps+"
        )
        sizes_m = free["cell_sizes_cm"][free["level"]] / 100
        centers = (free["indices"] + 0.5) * sizes_m[:, None]
        distance = np.hypot(*(centers - free["map_from_sensor"][:2, 3]).T)
        range_bin = np.where(
            distance < RANGE_EDGES_M[0], 0, np.where(distance < RANGE_EDGES_M[1], 1, 2)
        )
        area = sizes_m**2
        checked = result["inside"] & result["verifiable"]
        add(totals, "free_cells", len(area))
        add(totals, "inside_volume", int(np.count_nonzero(result["inside"])))
        add(totals, "verifiable", int(np.count_nonzero(checked)))
        add(totals, "false_free", int(np.count_nonzero(checked & result["false_free"])))
        add(totals, "moving_trace_hits", int(np.count_nonzero(checked & result["moving_hit"])))
        add(totals, "unknown_voxel_hits", int(np.count_nonzero(checked & result["unknown_hit"])))
        add(totals, "occluded_voxel_hits", int(np.count_nonzero(checked & result["occluded_hit"])))
        add(totals, "verifiable_area_cm2", int(round(float(area[checked].sum()) * 1e4)))
        add(
            totals,
            "false_free_area_cm2",
            int(round(float(area[checked & result["false_free"]].sum()) * 1e4)),
        )
        for label in result["blocking_class"][checked & result["false_free"]].tolist():
            add(by_class, CLASS_NAMES[label], 1)
        for name, mask in (
            ("0-20m", range_bin == 0),
            ("20-50m", range_bin == 1),
            ("50m+", range_bin == 2),
            (speed_bin, np.ones(len(area), dtype=np.bool_)),
        ):
            bucket = strata.setdefault(name, {})
            add(bucket, "verifiable", int(np.count_nonzero(checked & mask)))
            add(bucket, "false_free", int(np.count_nonzero(checked & result["false_free"] & mask)))
    verifiable = totals["verifiable"]
    return {
        "schema_version": 1,
        "sequence": sequence,
        "scored_frames": len(frames),
        "saved_frames": len(saved),
        "tau_free_m": tau_free_m,
        "band_tolerance_m": BAND_TOLERANCE_M,
        "grid_layout_input_iou": {
            "min": min(alignment),
            "median": float(np.median(alignment)),
        },
        "totals": totals,
        "false_free_rate": totals["false_free"] / verifiable if verifiable else None,
        "false_free_definition": "valid static non-ground voxel in the claimed band",
        "moving_trace_rate": totals["moving_trace_hits"] / verifiable if verifiable else None,
        "occluded_empty_rate": totals["occluded_voxel_hits"] / verifiable if verifiable else None,
        "false_free_area_rate": (
            totals["false_free_area_cm2"] / totals["verifiable_area_cm2"]
            if totals["verifiable_area_cm2"]
            else None
        ),
        "false_free_by_blocking_class": dict(sorted(by_class.items())),
        "strata": {
            name: {
                **values,
                "false_free_rate": values["false_free"] / values["verifiable"]
                if values["verifiable"]
                else None,
            }
            for name, values in sorted(strata.items())
        },
        "limitations": [
            "completion labels aggregate future scans; moving raw IDs (252+) are reported "
            "separately as traces, and parked cars or late arrivals can still appear static",
            "a beam may pass under an overhang or car body inside the tolerance band",
            "0.2 m voxels are coarser than 0.05/0.10 m free cells",
            "the band is return height -0.2 m to +tau+0.2 m; lower obstacles are not checked",
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="T-006 false-free scoring against SSC voxels")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--visibility", type=Path, required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--tau-free-m", type=float, default=0.10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = evaluate_false_free(args.dataset, args.visibility, args.sequence, args.tau_free_m)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
