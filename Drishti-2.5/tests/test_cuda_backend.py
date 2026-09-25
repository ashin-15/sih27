"""Parity checks run on a CUDA host; the CPU path is always exercised elsewhere."""

import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import pytest

from drishti.config import MappingConfig
from drishti.contracts import Mode, make_frame
from drishti.cuda_backend import CudaFramePath
from drishti.mapping import aggregate_cells
from drishti.pipeline import MappingEngine
from drishti.projection import project
from drishti.semantics import decode_semantickitti


class NumpyArrayAPI:
    """Check device algorithm arithmetic without treating this as a CUDA run."""

    def __getattr__(self, name: str) -> Any:
        return getattr(np, name)

    @staticmethod
    def asnumpy(values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        return values


@pytest.mark.parametrize("footprint", ["square", "radial"])
@pytest.mark.parametrize("oracle", [False, True])
def test_device_array_algorithm_matches_cpu_reference_without_gpu(
    footprint: Literal["square", "radial"], oracle: bool
) -> None:
    rng = np.random.default_rng(26053)
    points = np.column_stack(
        (
            rng.uniform(-80, 80, (2000, 2)),
            rng.uniform(-2, 2, 2000),
            rng.uniform(0, 1, 2000),
        )
    ).astype(np.float32)
    points[0, :3] = (-0.05, -0.05, -1.73)
    points[1, :3] = (5.01, 0.01, -1.73)
    points[2, :3] = points[1, :3]
    point_ids = np.arange(len(points), dtype=np.int64)
    xyz_map_m = points[:, :3].astype(np.float64)
    sensor_xy_m = np.array([0.05, -0.05], dtype=np.float64)
    ground = rng.integers(0, 3, len(points), dtype=np.uint8)
    semantic = (
        rng.integers(0, 20, len(points), dtype=np.uint8)
        if oracle
        else np.zeros(len(points), dtype=np.uint8)
    )
    motion = (
        rng.integers(0, 3, len(points), dtype=np.uint8)
        if oracle
        else np.zeros(len(points), dtype=np.uint8)
    )
    config = MappingConfig(footprint=footprint)
    backend = object.__new__(CudaFramePath)
    cast(Any, backend).cp = NumpyArrayAPI()
    expected_image = project(points, point_ids, config)
    actual_image = backend.project(points, point_ids, config)
    np.testing.assert_array_equal(actual_image.point_ids, expected_image.point_ids)
    np.testing.assert_array_equal(actual_image.ranges_m, expected_image.ranges_m)
    assert actual_image.collisions == expected_image.collisions
    assert actual_image.outside_fov == expected_image.outside_fov
    intensity = points[:, 3].astype(np.float64)
    mode = Mode.ORACLE if oracle else Mode.GEOMETRIC
    pose_source = make_frame(points).pose_source
    expected, expected_inverse = aggregate_cells(
        xyz_map_m,
        sensor_xy_m,
        ground,
        semantic,
        motion,
        intensity,
        config=config,
        sequence="array-api-reference",
        frame_id=0,
        timestamp_s=0.0,
        mode=mode,
        pose_source=pose_source,
        ground_method="test-fixture",
    )
    actual, actual_inverse = backend.aggregate_cells(
        xyz_map_m,
        sensor_xy_m,
        ground,
        semantic,
        motion,
        intensity,
        config=config,
        sequence="array-api-reference",
        frame_id=0,
        timestamp_s=0.0,
        mode=mode,
        pose_source=pose_source,
        ground_method="test-fixture",
    )
    np.testing.assert_array_equal(actual_inverse, expected_inverse)
    assert actual.digest == expected.digest


@pytest.mark.cuda
@pytest.mark.parametrize("mode", [Mode.GEOMETRIC, Mode.ORACLE])
def test_cuda_frame_path_matches_cpu_on_boundary_and_tie_fixture(mode: Mode) -> None:
    if not CudaFramePath.available():
        pytest.skip("working NVIDIA CUDA device and CuPy required")
    points = np.array(
        [
            [5.01, 0.01, -1.73, 0.2],
            [5.01, 0.01, -1.73, 0.8],
            [-5.01, -0.01, -1.70, 0.3],
            [-5.01, -0.01, -0.90, 0.5],
            [30.01, 0.01, 0.20, np.nan],
            [30.11, 0.01, -0.20, 0.9],
        ],
        dtype=np.float32,
    )
    annotations = (
        decode_semantickitti(np.array([0, 10, 81, 252, 40, 50], dtype=np.uint32))
        if mode == Mode.ORACLE
        else None
    )
    frame = make_frame(points, annotations=annotations)
    config = MappingConfig()
    cpu = MappingEngine(config, mode=mode).process(frame)
    cuda = MappingEngine(config, mode=mode, device="cuda").process(frame)
    assert cuda.accounting == cpu.accounting
    np.testing.assert_array_equal(cuda.observations.cell_indices, cpu.observations.cell_indices)
    np.testing.assert_array_equal(cuda.range_image.point_ids, cpu.range_image.point_ids)
    np.testing.assert_allclose(
        cuda.range_image.ranges_m, cpu.range_image.ranges_m, rtol=1e-12, atol=1e-12
    )
    for field in fields(cpu.snapshot):
        actual = getattr(cuda.snapshot, field.name)
        expected = getattr(cpu.snapshot, field.name)
        if isinstance(expected, np.ndarray) and expected.dtype.kind == "f":
            np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
        elif isinstance(expected, np.ndarray):
            np.testing.assert_array_equal(actual, expected)
        else:
            assert actual == expected


@pytest.mark.cuda
def test_cuda_cli_replay_matches_cpu_dataset_digests(dataset_root: Path, tmp_path: Path) -> None:
    if not CudaFramePath.available():
        pytest.skip("working NVIDIA CUDA device and CuPy required")
    from drishti.cli import main

    digests = []
    for device in ("cpu", "cuda"):
        output = tmp_path / device
        assert (
            main(
                [
                    "replay",
                    "--dataset",
                    str(dataset_root),
                    "--sequence",
                    "08",
                    "--output",
                    str(output),
                    "--max-frames",
                    "2",
                    "--device",
                    device,
                ]
            )
            == 0
        )
        digests.append(
            [
                json.loads(line)["map_digest"]
                for line in (output / "frames.jsonl").read_text().splitlines()
            ]
        )
    assert digests[0] == digests[1]
