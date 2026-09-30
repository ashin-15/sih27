"""CPU-reference parity for the optional CUDA candidate and visibility stages."""

from dataclasses import fields
from typing import Any, Literal, cast

import numpy as np
import pytest

from drishti.arrays import ByteArray, IntArray, PointArray, immutable
from drishti.config import MappingConfig
from drishti.contracts import Mode, ScanFrame, make_frame
from drishti.cuda_backend import CudaFramePath
from drishti.ground import GroundClass
from drishti.learned import SemanticPrediction
from drishti.obstacles import ConnectedComponentDetector
from drishti.pipeline import FrameResult, MappingEngine
from drishti.product_result import (
    InProcessProductEvaluator,
    ProductFrameResult,
    ReceiptStatus,
    visibility_product_result,
)
from drishti.tracking import CandidateTracker
from drishti.visibility import CurrentScanVisibility


class NumpyArrayAPI:
    """Run the device code path on NumPy; this is not a CUDA run."""

    def __getattr__(self, name: str) -> Any:
        return getattr(np, name)

    @staticmethod
    def asnumpy(values: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        return values


def _scene(seed: int) -> tuple[np.ndarray[Any, Any], ByteArray, ByteArray]:
    """Ground returns, clustered cars/poles and scattered structure around the sensor."""
    rng = np.random.default_rng(seed)
    ground_xy = rng.uniform(-60, 60, (1500, 2))
    ground_xy = ground_xy[np.hypot(ground_xy[:, 0], ground_xy[:, 1]) > 3.0]
    ground = np.column_stack((ground_xy, np.full(len(ground_xy), -1.73)))
    centers = rng.uniform(-40, 40, (12, 2))
    cars = np.concatenate(
        [
            np.column_stack((c + rng.uniform(-1.0, 1.0, (40, 2)), rng.uniform(-1.6, -0.2, 40)))
            for c in centers
        ]
    )
    poles = np.column_stack((rng.uniform(-30, 30, (60, 2)), rng.uniform(-1.5, 2.0, 60)))
    walls = np.column_stack((rng.uniform(-50, 50, (300, 2)), rng.uniform(-1.0, 3.0, 300)))
    xyz = np.concatenate((ground, cars, poles, walls))
    semantic = np.concatenate(
        (
            rng.choice([9, 11, 17, 0], len(ground), p=[0.7, 0.15, 0.1, 0.05]),
            np.full(len(cars), 1),
            np.full(len(poles), 18),
            rng.choice([13, 15, 0], len(walls)),
        )
    ).astype(np.uint8)
    ground_class = np.concatenate(
        (
            rng.choice([GroundClass.GROUND, GroundClass.UNKNOWN], len(ground), p=[0.95, 0.05]),
            np.full(len(cars) + len(poles) + len(walls), GroundClass.NONGROUND),
        )
    ).astype(np.uint8)
    return xyz, semantic, ground_class


class Authored:
    checkpoint_sha256 = "a" * 64
    weights_sha256 = "b" * 64
    method = "authored-cuda-stage-fixture"

    def __init__(self, semantic: ByteArray, ground: ByteArray) -> None:
        self.semantic = semantic
        self.ground = ground

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction:
        semantic = self.semantic[point_ids]
        return SemanticPrediction(
            immutable(semantic),
            immutable(np.where(semantic == 0, 0.0, 0.8)),
            immutable((semantic == 0).astype(np.uint8) * 2),
        )

    def segment(self, points: PointArray) -> ByteArray:
        return immutable(self.ground[: len(points)].copy())

    def close(self) -> None:
        pass


def _frame(xyz: np.ndarray[Any, Any]) -> ScanFrame:
    points = np.column_stack((xyz, np.full(len(xyz), 0.5))).astype(np.float32)
    pose = np.eye(4)
    pose[:3, 3] = (2.0, -1.0, 0.0)
    return make_frame(points, sequence="cuda-stages", map_from_sensor=pose)


def _run(
    device: Literal["cpu", "cuda"], seed: int
) -> tuple[ScanFrame, FrameResult, ProductFrameResult]:
    xyz, semantic, ground = _scene(seed)
    authored = Authored(semantic, ground)
    engine = MappingEngine(
        MappingConfig(),
        mode=Mode.LEARNED,
        predictor=authored,
        ground=authored,
        detector=ConnectedComponentDetector(device=device),
        tracker=CandidateTracker(),
        visibility=CurrentScanVisibility(device=device),
        device=device,
    )
    frame = _frame(xyz)
    result = engine.process(frame)
    product = visibility_product_result(
        frame,
        result,
        run_id="cuda-stages",
        code_revision="c" * 64,
        checkpoint_sha256="a" * 64,
        weights_sha256="b" * 64,
        cell_sizes_cm=MappingConfig().cell_sizes_cm,
        backend=device,
    )
    receipt = engine.receive_tracking(frame, result, product, InProcessProductEvaluator())
    assert receipt.status == ReceiptStatus.ACCEPTED, receipt.error_code
    return frame, result, product


def _assert_same_evidence(cuda: ProductFrameResult, cpu: ProductFrameResult) -> None:
    assert cuda.backend == "cuda" and cpu.backend == "cpu"
    assert cuda.instances == cpu.instances
    assert cuda.tracks == cpu.tracks
    assert cuda.beam_table is not None and cpu.beam_table is not None
    for name in ("beam_id", "point_id", "origin_map_m", "return_map_m"):
        np.testing.assert_array_equal(getattr(cuda.beam_table, name), getattr(cpu.beam_table, name))
    assert cuda.visibility_summary == cpu.visibility_summary
    for field in fields(cpu.cells):
        np.testing.assert_array_equal(
            getattr(cuda.cells, field.name), getattr(cpu.cells, field.name), err_msg=field.name
        )


@pytest.mark.parametrize("seed", [6, 26053])
def test_device_code_paths_match_cpu_reference_without_gpu(seed: int) -> None:
    _, result, product = _run("cpu", seed)
    assert result.visibility is not None and result.visibility.summary.free_cells > 0
    assert any(item.status == "observed" for item in product.instances)
    detector = object.__new__(ConnectedComponentDetector)
    cast(Any, detector).device = "cpu"
    cast(Any, detector)._xp = NumpyArrayAPI()
    assert detector.detect(result.observations, product.scan_timestamp_ns) == result.instances
    visibility = CurrentScanVisibility()
    cast(Any, visibility)._xp = NumpyArrayAPI()
    frame = _frame(_scene(seed)[0])
    device_evidence = visibility.compute(
        result.observations,
        result.snapshot,
        result.instances,
        frame.map_from_sensor,
        MappingConfig(),
        frame.deskew_status,
    )
    for field in fields(device_evidence):
        expected = getattr(result.visibility, field.name)
        actual = getattr(device_evidence, field.name)
        if isinstance(expected, np.ndarray):
            np.testing.assert_array_equal(actual, expected, err_msg=field.name)
        else:
            assert actual == expected


@pytest.mark.cuda
@pytest.mark.parametrize("seed", [6, 26053])
def test_cuda_candidate_tracking_and_visibility_match_cpu(seed: int) -> None:
    if not CudaFramePath.available():
        pytest.skip("working NVIDIA CUDA device and CuPy required")
    _, _, cpu = _run("cpu", seed)
    _, _, cuda = _run("cuda", seed)
    _assert_same_evidence(cuda, cpu)


def test_stage_devices_must_match_engine() -> None:
    with pytest.raises(ValueError, match="engine device"):
        MappingEngine(
            MappingConfig(),
            mode=Mode.LEARNED,
            predictor=Authored(np.zeros(0, np.uint8), np.zeros(0, np.uint8)),
            detector=ConnectedComponentDetector(),
            device="cuda",
        )
    with pytest.raises(ValueError, match="device"):
        ConnectedComponentDetector(device=cast(Any, "tpu"))
    with pytest.raises(ValueError, match="device"):
        CurrentScanVisibility(device=cast(Any, "tpu"))
