"""In-process FRNet runtime checks; checkpoint and scan tests need local assets."""

import os
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from drishti.frnet_model import (  # noqa: E402
    FRNetSegmentor,
    TorchFRNetPredictor,
    range_interpolation,
    range_interpolation_torch,
)

CHECKPOINT = os.environ.get("DRISHTI_FRNET_CHECKPOINT")
CHECKPOINT_SHA256 = "09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e"
SCAN = os.environ.get("DRISHTI_TEST_SCAN")


def _authors_range_interpolation(points: np.ndarray) -> np.ndarray:
    """Literal port of the authors' RangeInterpolation loop (H=64, W=2048)."""
    height, width = 64, 2048
    fov_up = 3.0 / 180.0 * np.pi
    fov_down = -25.0 / 180.0 * np.pi
    fov = abs(fov_down) + abs(fov_up)
    proj_image = np.full((height, width, 4), -1, dtype=np.float32)
    proj_idx = np.full((height, width), -1, dtype=np.int64)
    depth = np.linalg.norm(points[:, :3], 2, axis=1)
    yaw = -np.arctan2(points[:, 1], points[:, 0])
    pitch = np.arcsin(points[:, 2] / depth)
    proj_x = 0.5 * (yaw / np.pi + 1.0)
    proj_y = 1.0 - (pitch + abs(fov_down)) / fov
    proj_x *= width
    proj_y *= height
    proj_x = np.maximum(0, np.minimum(width - 1, np.floor(proj_x))).astype(np.int64)
    proj_y = np.maximum(0, np.minimum(height - 1, np.floor(proj_y))).astype(np.int64)
    indices = np.arange(depth.shape[0])
    order = np.argsort(depth)[::-1]
    proj_idx[proj_y[order], proj_x[order]] = indices[order]
    proj_image[proj_y[order], proj_x[order]] = points[order]
    proj_mask = (proj_idx > 0).astype(np.int32)
    added = []
    for y in range(height):
        for x in range(width):
            if proj_mask[y, x]:
                continue
            if x - 1 >= 0 and x + 1 < width and proj_mask[y, x - 1] and proj_mask[y, x + 1]:
                mean_points = (proj_image[y, x - 1] + proj_image[y, x + 1]) / 2
                proj_mask[y, x] = 1
                proj_image[y, x] = mean_points
                added.append(mean_points)
    if not added:
        return points
    return np.concatenate((points, np.array(added, dtype=np.float32)), axis=0)


def _synthetic_scan(count: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    azimuth = rng.uniform(-np.pi, np.pi, count)
    elevation = np.deg2rad(rng.uniform(-24.5, 2.5, count))
    distance = rng.uniform(3, 60, count)
    return np.column_stack(
        (
            distance * np.cos(elevation) * np.cos(azimuth),
            distance * np.cos(elevation) * np.sin(azimuth),
            distance * np.sin(elevation),
            rng.uniform(0, 1, count),
        )
    ).astype(np.float32)


@pytest.mark.parametrize("seed", [0, 26053])
def test_vectorized_interpolation_matches_authors_loop(seed: int) -> None:
    points = _synthetic_scan(60_000, seed)
    expected = _authors_range_interpolation(points)
    actual = range_interpolation(points)
    assert len(actual) > len(points)
    np.testing.assert_array_equal(actual, expected)


def test_segmentor_shapes_without_checkpoint() -> None:
    model = FRNetSegmentor().eval()
    points = torch.from_numpy(range_interpolation(_synthetic_scan(4000, 1)))
    with torch.inference_mode():
        logits = model(points)
    assert logits.shape == (len(points), 20)
    assert bool(torch.isfinite(logits).all())


@pytest.mark.skipif(CHECKPOINT is None, reason="set DRISHTI_FRNET_CHECKPOINT")
def test_checkpoint_loads_strictly_and_rejects_wrong_hash() -> None:
    assert CHECKPOINT is not None
    predictor = TorchFRNetPredictor(
        checkpoint=Path(CHECKPOINT), checkpoint_sha256=CHECKPOINT_SHA256
    )
    assert predictor.skipped_training_tensors > 0
    prediction = predictor.predict(_synthetic_scan(5000, 2), np.arange(5000, dtype=np.int64))
    assert prediction.semantic_id.shape == (5000,)
    predictor.close()
    with pytest.raises(ValueError, match="SHA-256"):
        TorchFRNetPredictor(checkpoint=Path(CHECKPOINT), checkpoint_sha256="0" * 64)


@pytest.mark.cuda
@pytest.mark.skipif(CHECKPOINT is None or SCAN is None, reason="set checkpoint and scan paths")
def test_cuda_prediction_agrees_with_cpu_on_real_scan() -> None:
    if not torch.cuda.is_available():
        pytest.skip("CUDA PyTorch build and NVIDIA device required")
    assert CHECKPOINT is not None and SCAN is not None
    points = np.fromfile(SCAN, dtype="<f4").reshape(-1, 4)
    ids = np.arange(len(points), dtype=np.int64)
    results = []
    for device in ("cpu", "cuda"):
        with TorchFRNetPredictor(
            checkpoint=Path(CHECKPOINT), checkpoint_sha256=CHECKPOINT_SHA256, device=device
        ) as predictor:
            results.append(predictor.predict(points, ids))
    cpu, cuda = results
    # Device atan2/arcsin rounding can move a point across a range-image pixel edge, so
    # a handful of points legitimately differ; bound the class agreement and the tail.
    agreement = float(np.mean(cpu.semantic_id == cuda.semantic_id))
    assert agreement >= 0.9999, agreement
    difference = np.abs(cpu.confidence - cuda.confidence)
    assert float(np.quantile(difference, 0.999)) < 2e-3


@pytest.mark.parametrize("seed", [4, 26053])
def test_device_interpolation_agrees_with_numpy_reference(seed: int) -> None:
    points = _synthetic_scan(60_000, seed)
    reference = range_interpolation(points)
    device = range_interpolation_torch(torch.from_numpy(points)).numpy()
    np.testing.assert_array_equal(device[: len(points)], points)
    # Same filled pixels; rare angle-rounding edge cases may add or drop a few points.
    assert abs(len(device) - len(reference)) <= 5
    added_reference = {row.tobytes() for row in reference[len(points) :]}
    added_device = {row.tobytes() for row in device[len(points) :]}
    assert len(added_reference) > 100
    assert len(added_reference & added_device) / len(added_reference) > 0.999


def test_precision_and_interpolation_options_are_guarded() -> None:
    with pytest.raises(ValueError, match="fp16"):
        TorchFRNetPredictor(checkpoint=Path("unused"), checkpoint_sha256="0" * 64, precision="fp16")
    with pytest.raises(ValueError, match="interpolation"):
        TorchFRNetPredictor(
            checkpoint=Path("unused"), checkpoint_sha256="0" * 64, gpu_interpolation=True
        )


@pytest.mark.cuda
@pytest.mark.skipif(CHECKPOINT is None or SCAN is None, reason="set checkpoint and scan paths")
def test_fp16_and_gpu_interpolation_stay_close_to_reference() -> None:
    if not torch.cuda.is_available():
        pytest.skip("CUDA PyTorch build and NVIDIA device required")
    assert CHECKPOINT is not None and SCAN is not None
    points = np.fromfile(SCAN, dtype="<f4").reshape(-1, 4)
    ids = np.arange(len(points), dtype=np.int64)
    settings: list[dict[str, object]] = [
        {},
        {"precision": "fp16"},
        {"gpu_interpolation": True},
    ]
    labels = []
    for extra in settings:
        with TorchFRNetPredictor(
            checkpoint=Path(CHECKPOINT),
            checkpoint_sha256=CHECKPOINT_SHA256,
            device="cuda",
            **extra,  # type: ignore[arg-type]
        ) as predictor:
            labels.append(predictor.predict(points, ids).semantic_id)
    assert float(np.mean(labels[1] == labels[0])) >= 0.995
    assert float(np.mean(labels[2] == labels[0])) >= 0.999
