import hashlib
import json
import math
import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Literal

from drishti.contracts import PoseSource


@dataclass(frozen=True)
class MappingConfig:
    cell_sizes_cm: tuple[int, ...] = (5, 10, 50)
    radii_m: tuple[float, ...] = (10.0, 25.0, 100.0)
    footprint: Literal["radial", "square"] = "radial"
    max_points: int = 150_000
    max_abs_coordinate_m: float = 1_000_000.0
    max_abs_height_m: float = 10_000.0
    min_range_m: float = 0.05
    sensor_height_m: float = 1.73
    ground_min_range_m: float = 2.7
    projection_rows: int = 64
    projection_columns: int = 1024
    fov_down_deg: float = -24.8
    fov_up_deg: float = 2.0
    ambiguous_ground_span_m: float = 0.5
    frame_budget_ms: float = 100.0

    def __post_init__(self) -> None:
        if not isinstance(self.cell_sizes_cm, tuple) or not isinstance(self.radii_m, tuple):
            raise ValueError("resolutions and radii must be immutable tuples")
        if not 1 <= len(self.cell_sizes_cm) <= 8 or len(self.cell_sizes_cm) != len(self.radii_m):
            raise ValueError("provide one radius per resolution, with 1 to 8 levels")
        if self.cell_sizes_cm[0] != 5:
            raise ValueError("the base lattice must be 5 cm")
        if any(type(size) is not int or size <= 0 for size in self.cell_sizes_cm):
            raise ValueError("cell sizes must be positive integer centimetres")
        for fine, coarse in zip(self.cell_sizes_cm, self.cell_sizes_cm[1:], strict=False):
            if coarse <= fine or coarse % fine:
                raise ValueError("consecutive cell sizes must increase by integer ratios")
        if any(not math.isfinite(radius) or radius <= 0 for radius in self.radii_m):
            raise ValueError("radii must be finite and positive")
        if any(a >= b for a, b in zip(self.radii_m, self.radii_m[1:], strict=False)):
            raise ValueError("radii must be strictly increasing")
        if self.footprint not in ("radial", "square"):
            raise ValueError("footprint must be radial or square")
        for name in ("max_points", "projection_rows", "projection_columns"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in (
            "max_abs_coordinate_m",
            "max_abs_height_m",
            "min_range_m",
            "sensor_height_m",
            "ground_min_range_m",
            "ambiguous_ground_span_m",
            "frame_budget_ms",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not -90 < self.fov_down_deg < self.fov_up_deg < 90:
            raise ValueError("projection FOV must be ordered within (-90, 90) degrees")
        if self.ground_min_range_m >= self.radii_m[-1]:
            raise ValueError("ground minimum range must be below the map radius")
        if self.max_abs_coordinate_m > 1e9 or self.radii_m[-1] > self.max_abs_coordinate_m:
            raise ValueError("coordinate bounds exceed the supported local lattice")
        height_cm = math.ceil(self.max_abs_height_m * 100)
        if height_cm >= 2**31 or self.max_points * height_cm**2 >= 2**63:
            raise ValueError("configured height and point bounds overflow fixed-point statistics")
        if self.projection_rows * self.projection_columns > 4_194_304:
            raise ValueError("projection capacity exceeds 4,194,304 pixels")

    @property
    def ratios(self) -> tuple[int, ...]:
        return tuple(size // self.cell_sizes_cm[0] for size in self.cell_sizes_cm)

    @property
    def digest(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, allow_nan=False).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RunConfig:
    dataset_root: Path
    artifact_root: Path
    mapping_config: Path
    comparison_config: Path
    pose_source: PoseSource = PoseSource.SLAM


def load_config(path: Path | None = None) -> MappingConfig:
    if path is None:
        return MappingConfig()
    with path.open("rb") as stream:
        values = tomllib.load(stream)
    unknown = set(values) - {field.name for field in fields(MappingConfig)}
    if unknown:
        raise ValueError(f"unknown configuration options: {sorted(unknown)}")
    for name in ("cell_sizes_cm", "radii_m"):
        if name in values:
            if not isinstance(values[name], list):
                raise ValueError(f"{name} must be a TOML array")
            values[name] = tuple(values[name])
    try:
        return MappingConfig(**values)
    except TypeError as exc:
        raise ValueError(f"invalid configuration: {exc}") from exc


def load_run_config(path: Path) -> RunConfig:
    preset_path = path.expanduser()
    with preset_path.open("rb") as stream:
        values = tomllib.load(stream)
    unknown = set(values) - {field.name for field in fields(RunConfig)}
    if unknown:
        raise ValueError(f"unknown run configuration options: {sorted(unknown)}")
    for name in ("dataset_root", "artifact_root", "mapping_config", "comparison_config"):
        value = values.get(name)
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a TOML string path")
        values[name] = preset_path.parent / value
    try:
        return RunConfig(**values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid run configuration: {exc}") from exc
