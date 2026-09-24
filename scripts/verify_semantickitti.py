"""Check the extracted KITTI odometry / SemanticKITTI dataset without changing it.

Read every scan and label, match frame names and point counts, validate temporal
and calibration metadata, and emit a JSON report. ZIP CRC checks belong to the
extraction step; this verifies that the extracted dataset is usable.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

RAW_IDS = {
    0,
    1,
    10,
    11,
    13,
    15,
    16,
    18,
    20,
    30,
    31,
    32,
    40,
    44,
    48,
    49,
    50,
    51,
    52,
    60,
    70,
    71,
    72,
    80,
    81,
    99,
    252,
    253,
    254,
    255,
    256,
    257,
    258,
    259,
}
FRAME_COUNTS = [
    4541,
    1101,
    4661,
    801,
    271,
    2761,
    1101,
    1101,
    4071,
    1591,
    1201,
    921,
    1061,
    3281,
    631,
    1901,
    1731,
    491,
    1801,
    4981,
    831,
    2721,
]


def check(condition, message, errors):
    if not condition:
        errors.append(message)
    return bool(condition)


def poses_metadata(path, frames, errors):
    if not check(path.is_file(), f"Missing pose file: {path}", errors):
        return None
    try:
        values = np.loadtxt(path, ndmin=2)
    except ValueError as exc:
        errors.append(f"Invalid pose file {path}: {exc}")
        return None
    if not check(
        values.shape == (frames, 12), f"Pose shape {path}: {values.shape}", errors
    ):
        return {"rows": len(values)}
    check(np.isfinite(values).all(), f"Nonfinite pose values: {path}", errors)
    rotations = values.reshape(-1, 3, 4)[:, :, :3]
    orthogonality = float(
        np.max(np.abs(rotations @ rotations.transpose(0, 2, 1) - np.eye(3)))
    )
    determinant_error = float(np.max(np.abs(np.linalg.det(rotations) - 1)))
    check(
        orthogonality < 1e-3 and determinant_error < 1e-3,
        f"Invalid pose rotation: {path}",
        errors,
    )
    return {
        "rows": frames,
        "max_rotation_orthogonality_error": orthogonality,
        "max_rotation_determinant_error": determinant_error,
    }


def verify_sequence(root, seq, full_content, errors):
    folder = root / "sequences" / seq
    scans = sorted((folder / "velodyne").glob("*.bin"))
    labels = sorted((folder / "labels").glob("*.label"))
    frame_ids = [path.stem for path in scans]
    expected = FRAME_COUNTS[int(seq)]
    check(
        frame_ids == [f"{i:06d}" for i in range(expected)],
        f"Sequence {seq}: missing, extra or noncanonical scan frame names",
        errors,
    )
    labeled = int(seq) <= 10
    if labeled:
        check(
            [p.stem for p in labels] == frame_ids,
            f"Sequence {seq}: label frame names do not match scans",
            errors,
        )
    else:
        check(
            not labels,
            f"Sequence {seq}: unexpected labels in hidden-label test split",
            errors,
        )
    calibration = {}
    calib_path = folder / "calib.txt"
    if check(calib_path.is_file(), f"Missing calibration: {calib_path}", errors):
        for line in calib_path.read_text().splitlines():
            if not line.strip():
                continue
            key, value = line.split(":", 1)
            calibration[key] = np.fromstring(value, sep=" ")
        for key in ("P0", "P1", "P2", "P3", "Tr"):
            values = calibration.get(key, np.array([]))
            check(
                values.size == 12 and np.isfinite(values).all(),
                f"Sequence {seq}: invalid calibration {key}",
                errors,
            )
        tr = calibration.get("Tr", np.array([]))
        if tr.size == 12:
            rot = tr.reshape(3, 4)[:, :3]
            check(
                np.allclose(rot @ rot.T, np.eye(3), atol=1e-3)
                and abs(np.linalg.det(rot) - 1) < 1e-3,
                f"Sequence {seq}: invalid calibration rotation",
                errors,
            )

    times_path = folder / "times.txt"
    intervals = None
    if check(times_path.is_file(), f"Missing timestamps: {times_path}", errors):
        timestamps = np.loadtxt(times_path, ndmin=1)
        check(
            timestamps.shape == (len(scans),) and np.isfinite(timestamps).all(),
            f"Sequence {seq}: timestamp count or values invalid",
            errors,
        )
        differences = np.diff(timestamps)
        check(
            np.all(differences > 0),
            f"Sequence {seq}: timestamps not strictly increasing",
            errors,
        )
        if differences.size:
            intervals = {
                "min_s": float(differences.min()),
                "median_s": float(np.median(differences)),
                "max_s": float(differences.max()),
            }
    slam_poses = poses_metadata(folder / "poses.txt", len(scans), errors)
    gt_poses = (
        poses_metadata(root / "poses" / f"{seq}.txt", len(scans), errors)
        if labeled
        else None
    )

    points_total, scan_bytes, label_bytes = 0, 0, 0
    smallest, largest = None, 0
    histogram = np.zeros(65536, dtype=np.int64)
    scans_over_cap = 0
    start = time.monotonic()
    for i, path in enumerate(scans):
        size = path.stat().st_size
        if not check(
            size > 0 and size % 16 == 0, f"Invalid scan byte count: {path}", errors
        ):
            continue
        count = size // 16
        points_total += count
        scan_bytes += size
        smallest = count if smallest is None else min(smallest, count)
        largest = max(largest, count)
        scans_over_cap += count > 150000
        if full_content:
            points = np.fromfile(path, dtype="<f4").reshape(-1, 4)
            check(np.isfinite(points).all(), f"Nonfinite scan values: {path}", errors)
        label_path = folder / "labels" / f"{path.stem}.label"
        if labeled and label_path.is_file():
            label_size = label_path.stat().st_size
            label_bytes += label_size
            check(
                label_size == count * 4,
                f"Point/label count mismatch: {label_path}",
                errors,
            )
            if full_content and label_size % 4 == 0:
                words = np.fromfile(label_path, dtype="<u4")
                raw_ids = words & 0xFFFF
                counts = np.bincount(raw_ids.astype(np.int32))
                histogram[: len(counts)] += counts
        if i and i % 1000 == 0:
            print(f"Sequence {seq}: {i}/{len(scans)} scans checked", flush=True)
    observed_ids = np.flatnonzero(histogram)
    unknown_ids = sorted(set(observed_ids.tolist()) - RAW_IDS)
    check(
        not unknown_ids,
        f"Sequence {seq}: unsupported raw semantic IDs {unknown_ids}",
        errors,
    )
    return {
        "sequence": seq,
        "split": "valid" if seq == "08" else ("train" if labeled else "test"),
        "scans": len(scans),
        "labels": len(labels),
        "point_count": points_total,
        "scan_bytes": scan_bytes,
        "label_bytes": label_bytes,
        "points_per_scan_min": smallest,
        "points_per_scan_max": largest,
        "scans_above_drishti_default_150000_point_cap": scans_over_cap,
        "timestamp_intervals": intervals,
        "slam_poses": slam_poses,
        "gt_poses": gt_poses,
        "semantic_histogram": {str(int(i)): int(histogram[i]) for i in observed_ids},
        "moving_points": int(histogram[252:260].sum())
        if full_content and labeled
        else None,
        "content_seconds": round(time.monotonic() - start, 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--structure-only",
        action="store_true",
        help="Skip scan/label content checks; still check metadata and all file sizes",
    )
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    errors = []
    expected_sequences = [f"{i:02d}" for i in range(22)]
    found = sorted(p.name for p in (root / "sequences").iterdir() if p.is_dir())
    check(found == expected_sequences, f"Unexpected sequence set: {found}", errors)
    print(
        f"Checking dataset at {root}; full content = {not args.structure_only}",
        flush=True,
    )
    sequences = []
    for seq in expected_sequences:
        row = verify_sequence(root, seq, not args.structure_only, errors)
        sequences.append(row)
        print(
            f"Sequence {seq}: {row['scans']} scans, {row['labels']} labels; "
            f"cumulative errors={len(errors)}",
            flush=True,
        )
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(root),
        "full_content_checked": not args.structure_only,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "total_scans": sum(s["scans"] for s in sequences),
        "total_labels": sum(s["labels"] for s in sequences),
        "total_points": sum(s["point_count"] for s in sequences),
        "scan_and_label_bytes": sum(
            s["scan_bytes"] + s["label_bytes"] for s in sequences
        ),
        "sequences": sequences,
        "limits": [
            "Does not establish annotation or pose accuracy",
            "ZIP CRC integrity must be checked separately during extraction",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"{report['status'].upper()}: {report['total_scans']} scans, "
        f"{report['total_labels']} labels. Report: {args.report}",
        flush=True,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
