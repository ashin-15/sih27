from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LabelledSample:
    sample_token: str
    sample_data_token: str
    points: Any
    labels: Any
    category_names: dict[int, str]


def load_lidarseg_records(dataroot: str | Path) -> list[dict[str, Any]]:
    path = Path(dataroot) / "v1.0-mini" / "lidarseg.json"
    with path.open("r", encoding="utf-8") as handle:
        records = json.load(handle)
    return records


def load_category_names(dataroot: str | Path) -> dict[int, str]:
    path = Path(dataroot) / "v1.0-mini" / "category.json"
    with path.open("r", encoding="utf-8") as handle:
        records = json.load(handle)
    return {int(record["index"]): str(record["name"]) for record in records if record.get("index") is not None}


def select_sample(nusc: Any, sample_token: str | None = None) -> dict[str, Any]:
    if sample_token:
        return nusc.get("sample", sample_token)
    samples = sorted(nusc.sample, key=lambda sample: int(sample["timestamp"]))
    if not samples:
        raise ValueError("Dataset contains no samples")
    return samples[0]


def load_labelled_sample(
    dataroot: str | Path,
    *,
    sample_token: str | None = None,
    nusc: Any | None = None,
) -> LabelledSample:
    import numpy as np
    from nuscenes.nuscenes import NuScenes

    dataroot = Path(dataroot)
    if nusc is None:
        nusc = NuScenes(version="v1.0-mini", dataroot=str(dataroot), verbose=False)
    sample = select_sample(nusc, sample_token)
    sample_data_token = sample["data"]["LIDAR_TOP"]
    sample_data = nusc.get("sample_data", sample_data_token)
    label_by_sample_data = {record["sample_data_token"]: record for record in load_lidarseg_records(dataroot)}
    label_record = label_by_sample_data.get(sample_data_token)
    if label_record is None:
        raise FileNotFoundError(f"No mini lidarseg record for sample_data token {sample_data_token}")

    point_path = dataroot / sample_data["filename"]
    label_path = dataroot / label_record["filename"]
    raw_points = np.fromfile(point_path, dtype=np.float32)
    if raw_points.size % 5:
        raise ValueError(f"Point file {point_path} does not contain five-float records")
    points = raw_points.reshape(-1, 5)
    labels = np.fromfile(label_path, dtype=np.uint8)
    if points.shape[0] != labels.shape[0]:
        raise ValueError(
            f"Point/label mismatch for {sample_data_token}: {points.shape[0]} points vs {labels.shape[0]} labels"
        )
    return LabelledSample(
        sample_token=sample["token"],
        sample_data_token=sample_data_token,
        points=points,
        labels=labels,
        category_names=load_category_names(dataroot),
    )


def summarize_labelled_sample(sample: LabelledSample) -> dict[str, Any]:
    import numpy as np

    points = sample.points
    labels = sample.labels
    radius = np.linalg.norm(points[:, :2], axis=1)
    histogram = Counter(int(value) for value in labels)
    invalid_points = int(np.sum(~np.isfinite(points[:, :3]).all(axis=1)))
    return {
        "sample_token": sample.sample_token,
        "sample_data_token": sample.sample_data_token,
        "point_count": int(points.shape[0]),
        "label_count": int(labels.shape[0]),
        "invalid_point_count": invalid_points,
        "coordinate_ranges_m": {
            axis: {"min": float(points[:, index].min()), "max": float(points[:, index].max())}
            for index, axis in enumerate(("x", "y", "z"))
        },
        "radial_range_m": {"min": float(radius.min()), "max": float(radius.max())},
        "label_histogram": {
            str(index): {"count": int(count), "name": sample.category_names.get(index, "unknown")}
            for index, count in sorted(histogram.items())
        },
    }
