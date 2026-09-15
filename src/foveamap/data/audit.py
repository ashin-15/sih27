from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


STANDARD_TABLES = (
    "attribute",
    "calibrated_sensor",
    "category",
    "ego_pose",
    "instance",
    "log",
    "map",
    "sample",
    "sample_annotation",
    "sample_data",
    "scene",
    "sensor",
    "visibility",
)


def _load_table(dataroot: Path, name: str) -> list[dict[str, Any]]:
    path = dataroot / "v1.0-mini" / f"{name}.json"
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list):
        raise TypeError(f"{path} does not contain a JSON list")
    return value


def count_files(directory: Path, suffix: str = ".bin") -> int:
    if not directory.exists():
        return 0
    return sum(1 for entry in os.scandir(directory) if entry.is_file() and entry.name.endswith(suffix))


def validate_label_values(labels: Iterable[int], valid_indexes: set[int]) -> dict[str, Any]:
    values = set(int(value) for value in labels)
    invalid = sorted(values - valid_indexes)
    return {
        "unique_values": sorted(values),
        "invalid_values": invalid,
        "valid": not invalid,
    }


def audit_nuscenes_mini(
    dataroot: str | Path,
    *,
    max_point_pairs: int | None = None,
    expected_scenes: int = 10,
    expected_samples: int = 404,
    expected_lidarseg_records: int = 404,
) -> dict[str, Any]:
    import numpy as np
    from nuscenes.nuscenes import NuScenes

    dataroot = Path(dataroot)
    metadata_root = dataroot / "v1.0-mini"
    lidarseg_root = dataroot / "lidarseg" / "v1.0-mini"
    trainval_root = dataroot / "lidarseg" / "v1.0-trainval"

    missing_metadata = [
        f"v1.0-mini/{name}.json" for name in STANDARD_TABLES if not (metadata_root / f"{name}.json").exists()
    ]
    if not (metadata_root / "lidarseg.json").exists():
        missing_metadata.append("v1.0-mini/lidarseg.json")

    nusc = NuScenes(version="v1.0-mini", dataroot=str(dataroot), verbose=False)
    categories = _load_table(dataroot, "category")
    valid_indexes = {int(category["index"]) for category in categories if category.get("index") is not None}
    if not valid_indexes:
        raise ValueError("category.json lacks lidarseg label indexes")

    lidarseg_records = _load_table(dataroot, "lidarseg")
    sample_data_by_token = {record["token"]: record for record in nusc.sample_data}
    lidarseg_by_sample_data = {record["sample_data_token"]: record for record in lidarseg_records}

    lidar_keyframes = []
    for sample in nusc.sample:
        lidar_token = sample.get("data", {}).get("LIDAR_TOP")
        if lidar_token:
            lidar_keyframes.append(sample_data_by_token.get(lidar_token))

    lidar_tokens = {record["token"] for record in lidar_keyframes if record is not None}
    missing_lidar_records = sum(1 for record in lidar_keyframes if record is None)
    non_keyframe_records = sorted(
        record["token"]
        for record in lidar_keyframes
        if record is not None and not record.get("is_key_frame", False)
    )
    non_lidar_records = sorted(
        record["token"]
        for record in lidar_keyframes
        if record is not None and record.get("sensor_modality") != "lidar"
    )
    duplicate_lidarseg_tokens = sorted(
        token for token, count in Counter(record["token"] for record in lidarseg_records).items() if count > 1
    )
    duplicate_sample_data_tokens = sorted(
        token for token, count in Counter(record["sample_data_token"] for record in lidarseg_records).items() if count > 1
    )
    orphan_lidarseg_records = sorted(
        record["sample_data_token"] for record in lidarseg_records if record["sample_data_token"] not in lidar_tokens
    )
    missing_lidarseg_records = sorted(token for token in lidar_tokens if token not in lidarseg_by_sample_data)

    referenced_label_paths = {
        dataroot / record["filename"] for record in lidarseg_records if record["sample_data_token"] in lidar_tokens
    }
    actual_label_paths = {path for path in lidarseg_root.glob("*.bin")}
    orphan_label_files = sorted(path.name for path in actual_label_paths - referenced_label_paths)
    missing_label_files = sorted(path.name for path in referenced_label_paths - actual_label_paths)
    bad_label_directory = sorted(
        record["filename"]
        for record in lidarseg_records
        if Path(record["filename"]).parent != Path("lidarseg/v1.0-mini")
    )

    point_files: list[dict[str, Any]] = []
    for record in lidar_keyframes:
        if record is None:
            continue
        point_path = dataroot / record["filename"]
        label_record = lidarseg_by_sample_data.get(record["token"])
        point_files.append(
            {
                "sample_data_token": record["token"],
                "point_path": point_path,
                "label_path": dataroot / label_record["filename"] if label_record else None,
                "point_exists": point_path.exists(),
                "label_exists": label_record is not None and (dataroot / label_record["filename"]).exists(),
            }
        )

    missing_point_files = [item["sample_data_token"] for item in point_files if not item["point_exists"]]
    empty_files = sorted(
        {
            str(item["point_path"].name)
            for item in point_files
            if item["point_exists"] and item["point_path"].stat().st_size == 0
        }
        | {
            str(item["label_path"].name)
            for item in point_files
            if item["label_path"] is not None and item["label_exists"] and item["label_path"].stat().st_size == 0
        }
    )

    selected_pairs = point_files if max_point_pairs is None else point_files[:max_point_pairs]
    pair_results = []
    mismatch_count = 0
    invalid_label_files = []
    for item in selected_pairs:
        result: dict[str, Any] = {
            "sample_data_token": item["sample_data_token"],
            "point_count": None,
            "label_count": None,
            "point_label_match": None,
            "valid_labels": None,
        }
        if item["point_exists"] and item["label_exists"]:
            point_cloud = np.fromfile(item["point_path"], dtype=np.float32)
            if point_cloud.size % 5:
                result["error"] = "point_cloud_size_not_multiple_of_5"
            else:
                point_count = point_cloud.size // 5
                labels = np.fromfile(item["label_path"], dtype=np.uint8)
                label_validation = validate_label_values((int(value) for value in np.unique(labels)), valid_indexes)
                result.update(
                    {
                        "point_count": int(point_count),
                        "label_count": int(labels.size),
                        "point_label_match": point_count == labels.size,
                        "valid_labels": label_validation["valid"],
                        "unique_label_values": label_validation["unique_values"],
                    }
                )
                mismatch_count += int(point_count != labels.size)
                if not label_validation["valid"]:
                    invalid_label_files.append(item["label_path"].name)
        pair_results.append(result)

    duplicate_label_paths = sorted(
        filename for filename, count in Counter(record["filename"] for record in lidarseg_records).items() if count > 1
    )
    actual_mini_labels = count_files(lidarseg_root)
    ignored_trainval_labels = count_files(trainval_root)

    checks = {
        "all_standard_tables_present": not missing_metadata,
        "lidarseg_mapping_present": (metadata_root / "lidarseg.json").exists(),
        "scene_count_expected": len(nusc.scene) == expected_scenes,
        "sample_count_expected": len(nusc.sample) == expected_samples,
        "lidar_keyframe_count_expected": len(lidar_tokens) == expected_samples,
        "all_samples_have_lidar": missing_lidar_records == 0,
        "all_lidar_records_are_keyframes": not non_keyframe_records,
        "all_lidar_records_have_lidar_modality": not non_lidar_records,
        "lidarseg_record_count_expected": len(lidarseg_records) == expected_lidarseg_records,
        "no_missing_lidarseg_records": not missing_lidarseg_records,
        "no_orphan_lidarseg_records": not orphan_lidarseg_records,
        "mini_label_file_count_expected": actual_mini_labels == expected_lidarseg_records,
        "no_missing_label_files": not missing_label_files,
        "no_orphan_label_files": not orphan_label_files,
        "no_duplicate_lidarseg_tokens": not duplicate_lidarseg_tokens,
        "no_duplicate_sample_data_tokens": not duplicate_sample_data_tokens,
        "no_duplicate_label_paths": not duplicate_label_paths,
        "all_label_paths_in_mini": not bad_label_directory,
        "all_point_files_present": not missing_point_files,
        "no_zero_byte_files": not empty_files,
        "selected_point_label_pairs_match": mismatch_count == 0,
        "selected_labels_are_valid": not invalid_label_files,
    }

    report = {
        "dataroot": str(dataroot),
        "version": "v1.0-mini",
        "expected": {
            "scenes": expected_scenes,
            "samples": expected_samples,
            "lidarseg_records": expected_lidarseg_records,
        },
        "actual": {
            "scenes": len(nusc.scene),
            "samples": len(nusc.sample),
            "lidar_keyframes": len(lidar_tokens),
            "lidarseg_records": len(lidarseg_records),
            "mini_label_files": actual_mini_labels,
            "ignored_trainval_label_files": ignored_trainval_labels,
            "pairs_checked": len(pair_results),
        },
        "category": {
            "count": len(categories),
            "indexed_count": len(valid_indexes),
            "valid_indexes": sorted(valid_indexes),
        },
        "missing_metadata": missing_metadata,
        "non_keyframe_records": non_keyframe_records,
        "non_lidar_records": non_lidar_records,
        "missing_lidarseg_records": missing_lidarseg_records,
        "orphan_lidarseg_records": orphan_lidarseg_records,
        "missing_label_files": missing_label_files,
        "orphan_label_files": orphan_label_files,
        "bad_label_directory": bad_label_directory,
        "missing_point_files": missing_point_files,
        "zero_byte_files": empty_files,
        "duplicate_lidarseg_tokens": duplicate_lidarseg_tokens,
        "duplicate_sample_data_tokens": duplicate_sample_data_tokens,
        "duplicate_label_paths": duplicate_label_paths,
        "point_label_mismatch_count": mismatch_count,
        "invalid_label_files": invalid_label_files,
        "pair_results": pair_results,
        "checks": checks,
        "passed": all(checks.values()),
    }
    return report
