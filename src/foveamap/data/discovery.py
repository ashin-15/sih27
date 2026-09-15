from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_PATHS = (
    "v1.0-mini/sample.json",
    "v1.0-mini/sample_data.json",
    "v1.0-mini/category.json",
    "v1.0-mini/lidarseg.json",
    "samples/LIDAR_TOP",
    "sweeps/LIDAR_TOP",
    "lidarseg/v1.0-mini",
)


@dataclass(frozen=True)
class DatasetRoot:
    path: Path
    metadata_path: Path
    missing_paths: tuple[Path, ...]


def normalized_slug(path: Path) -> str:
    return "-".join(part for part in path.parts if part).replace("_", "-").lower()


def find_nuscenes_roots(input_root: str | Path = "/kaggle/input") -> list[Path]:
    input_root = Path(input_root)
    if not input_root.exists():
        raise FileNotFoundError(f"Kaggle input root does not exist: {input_root}")
    roots = sorted(path.parent.parent for path in input_root.rglob("v1.0-mini/sample.json"))
    return roots


def validate_dataset_root(path: str | Path) -> DatasetRoot:
    path = Path(path)
    missing = tuple(path / relative for relative in REQUIRED_PATHS if not (path / relative).exists())
    return DatasetRoot(path=path, metadata_path=path / "v1.0-mini", missing_paths=missing)


def discover_dataset_root(
    input_root: str | Path = "/kaggle/input",
    preferred_slug: str = "vyomkeshsharma/nuscenes-mini-complete-with-lidarseg",
) -> DatasetRoot:
    candidates = find_nuscenes_roots(input_root)
    if not candidates:
        raise FileNotFoundError(f"No v1.0-mini dataset found under {input_root}")

    slug_text = preferred_slug.replace("/", "-").replace("_", "-").lower()
    preferred = [path for path in candidates if slug_text in normalized_slug(path)]
    if len(preferred) > 1:
        raise RuntimeError(f"Ambiguous preferred dataset roots: {[str(path) for path in preferred]}")
    if preferred:
        selected = preferred[0]
    elif len(candidates) == 1:
        selected = candidates[0]
    else:
        raise RuntimeError(f"Ambiguous dataset roots: {[str(path) for path in candidates]}")

    root = validate_dataset_root(selected)
    if root.missing_paths:
        missing = ", ".join(str(path) for path in root.missing_paths)
        raise FileNotFoundError(f"Dataset contract is incomplete; missing: {missing}")
    return root
