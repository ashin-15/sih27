from dataclasses import replace

import numpy as np
import pytest

from drishti.arrays import ByteArray, IntArray, PointArray, immutable
from drishti.config import MappingConfig
from drishti.contracts import Mode, make_frame
from drishti.ground import GroundClass
from drishti.learned import SemanticPrediction
from drishti.obstacles import ConnectedComponentDetector, panoptic_raw_labels
from drishti.pipeline import MappingEngine, PointObservations
from drishti.product_result import (
    InProcessProductEvaluator,
    ReceiptStatus,
    candidate_product_result,
)


class Nonground:
    method = "nonground-fixture"

    def segment(self, points: PointArray) -> ByteArray:
        return immutable(np.full(len(points), GroundClass.NONGROUND, dtype=np.uint8))


class Labels:
    checkpoint_sha256 = "a" * 64
    weights_sha256 = "b" * 64

    def close(self) -> None:
        pass

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction:
        labels = np.array([1, 1, 1, 1, 1, 1, 18, 18, 0, 0, 13, 13], dtype=np.uint8)
        selected = labels[point_ids]
        return SemanticPrediction(
            immutable(selected),
            immutable(np.where(selected == 0, 0.0, 0.8)),
            immutable(np.where(selected == 0, 2, 0).astype(np.uint8)),
        )


def _points() -> np.ndarray:
    return np.array(
        [
            [5.0, 0.0, 0.4, 0.5],
            [5.1, 0.0, 0.5, 0.5],
            [5.2, 0.1, 0.6, 0.5],
            [7.0, 0.0, 0.4, 0.5],
            [7.1, 0.0, 0.5, 0.5],
            [7.2, 0.1, 0.6, 0.5],
            [10.0, 0.0, 0.4, 0.5],
            [10.0, 0.0, 0.8, 0.5],
            [12.0, 0.0, 2.0, 0.5],
            [12.1, 0.0, 2.0, 0.5],
            [14.0, 0.0, 1.0, 0.5],
            [14.1, 0.0, 1.1, 0.5],
        ],
        dtype=np.float32,
    )


def test_candidate_components_preserve_thin_unknown_and_wall_support() -> None:
    points = _points()
    labels = Labels().predict(points, np.arange(len(points), dtype=np.int64))
    observations = PointObservations(
        immutable(points),
        immutable(points[:, :3].astype(np.float64)),
        immutable(np.arange(20, 32, dtype=np.int64)),
        immutable(np.full(len(points), GroundClass.NONGROUND, dtype=np.uint8)),
        labels.semantic_id,
        labels.confidence,
        labels.unknown_reason,
        immutable(np.zeros(len(points), dtype=np.uint8)),
        immutable(np.zeros((len(points), 2), dtype=np.int64)),
    )
    candidates = ConnectedComponentDetector().detect(observations, 100)
    assert [(item.semantic_id, item.point_ids) for item in candidates] == [
        (1, (20, 21, 22)),
        (1, (23, 24, 25)),
        (18, (26, 27)),
        (0, (28, 29)),
        (0, (30, 31)),
    ]
    assert [item.status for item in candidates] == [
        "observed",
        "observed",
        "ambiguous",
        "ambiguous",
        "ambiguous",
    ]
    assert all(item.uncertainty_m is None for item in candidates)
    assert candidates[3].bounds_max_m[2] == 2.0
    assert ConnectedComponentDetector().detect(observations, 100) == candidates


def test_candidate_result_on_shared_engine_path_and_evaluator_guards() -> None:
    frame = make_frame(_points(), timestamp_s=1.0)
    engine = MappingEngine(
        MappingConfig(),
        mode=Mode.LEARNED,
        predictor=Labels(),
        ground=Nonground(),
        detector=ConnectedComponentDetector(),
    )
    result = engine.process(frame)
    assert len(result.instances) == 5
    assert result.timings.detector_ms is not None
    raw = panoptic_raw_labels(
        frame.point_ids,
        result.observations.point_ids,
        result.observations.semantic,
        result.instances,
    )
    assert len(raw) == len(frame.point_ids)
    assert (raw[:3] & 0xFFFF).tolist() == [10, 10, 10]
    assert (raw[:3] >> 16).tolist() == [1, 1, 1]
    assert (raw[3:6] >> 16).tolist() == [2, 2, 2]
    assert (raw[6:] >> 16).tolist() == [0] * 6
    product = candidate_product_result(
        frame,
        result,
        run_id="fixture",
        code_revision="c" * 64,
        checkpoint_sha256="a" * 64,
        weights_sha256="b" * 64,
        cell_sizes_cm=engine.config.cell_sizes_cm,
    )
    evaluator = InProcessProductEvaluator()
    first = product.instances[0]
    invalid = replace(
        product, instances=(replace(first, bounds_max_m=(6.0, 1.0, 1.0)), *product.instances[1:])
    )
    rejected = evaluator.receive(frame, invalid)
    assert rejected.status == ReceiptStatus.REJECTED
    assert rejected.error_code == "candidate-bounds"
    assert rejected.result_digest is None
    wrong_class = replace(
        product,
        instances=(replace(first, semantic_id=2), *product.instances[1:]),
    )
    assert evaluator.receive(frame, wrong_class).error_code == "candidate-class-support"
    wrong_support = replace(
        product,
        instances=(replace(first, point_ids=(999,)), *product.instances[1:]),
    )
    assert evaluator.receive(frame, wrong_support).error_code == "instance-support"
    receipt = evaluator.receive(frame, product)
    assert receipt.status == ReceiptStatus.ACCEPTED
    assert receipt.schema_version == 3
    assert receipt.stage == "candidate"
    assert receipt.result_digest is not None
    assert (
        InProcessProductEvaluator().receive(frame, product).result_digest == receipt.result_digest
    )
    assert (
        InProcessProductEvaluator().receive(frame, replace(product, schema_version=2)).error_code
        == "unsupported-schema"
    )
    with pytest.raises(ValueError, match="learned CPU"):
        MappingEngine(MappingConfig(), detector=ConnectedComponentDetector())


def test_projection_loser_remains_obstacle_support() -> None:
    frame = make_frame(
        np.array([[5.0, 0, 0, 0.5], [10.0, 0, 0, 0.5]], dtype=np.float32),
        timestamp_s=1.0,
    )
    result = MappingEngine(
        MappingConfig(),
        mode=Mode.LEARNED,
        predictor=Labels(),
        ground=Nonground(),
        detector=ConnectedComponentDetector(),
    ).process(frame)
    assert result.accounting.projection_collisions == 1
    assert {point_id for item in result.instances for point_id in item.point_ids} == {0, 1}


def test_panoptic_export_preserves_input_order_and_filtered_unknowns() -> None:
    raw = panoptic_raw_labels(
        np.array([20, 21, 22, 23], dtype=np.int64),
        np.array([23, 20], dtype=np.int64),
        np.array([1, 18], dtype=np.uint8),
        (),
    )
    assert raw.tolist() == [80, 0, 0, 10]


def test_empty_candidate_input() -> None:
    observations = PointObservations(
        immutable(np.zeros((0, 4), dtype=np.float32)),
        immutable(np.zeros((0, 3), dtype=np.float64)),
        immutable(np.zeros(0, dtype=np.int64)),
        immutable(np.zeros(0, dtype=np.uint8)),
        immutable(np.zeros(0, dtype=np.uint8)),
        immutable(np.zeros(0, dtype=np.float64)),
        immutable(np.zeros(0, dtype=np.uint8)),
        immutable(np.zeros(0, dtype=np.uint8)),
        immutable(np.zeros((0, 2), dtype=np.int64)),
    )
    assert ConnectedComponentDetector().detect(observations, 0) == ()


def test_partial_thin_near_far_and_invalid_candidate_evidence() -> None:
    points = np.array(
        [
            [5.0, 0.0, 0.3],  # sparse person
            [5.1, 1.0, 0.2],
            [5.2, 1.0, 0.3],  # raised curb
            [5.0, 2.0, 2.2],
            [5.2, 2.0, 2.2],  # overhang
            [6.0, 0.0, 0.5],
            [6.1, 0.0, 0.5],
            [6.2, 0.0, 0.5],  # touching car
            [6.3, 0.0, 0.5],
            [6.4, 0.0, 0.5],
            [6.5, 0.0, 0.5],
            [45.0, 0.0, 0.5],
            [45.1, 0.0, 0.5],
            [45.2, 0.0, 0.5],  # far car
        ],
        dtype=np.float64,
    )
    labels = np.array([6, 11, 11, 0, 0, *([1] * 9)], dtype=np.uint8)
    ground = np.full(len(points), GroundClass.NONGROUND, dtype=np.uint8)
    observations = PointObservations(
        immutable(np.column_stack((points, np.full(len(points), 0.5))).astype(np.float32)),
        immutable(points),
        immutable(np.arange(len(points), dtype=np.int64)),
        immutable(ground),
        immutable(labels),
        immutable(np.where(labels == 0, 0.0, 0.8).astype(np.float64)),
        immutable(np.where(labels == 0, 2, 0).astype(np.uint8)),
        immutable(np.zeros(len(points), dtype=np.uint8)),
        immutable(np.zeros((len(points), 2), dtype=np.int64)),
    )
    candidates = ConnectedComponentDetector().detect(observations, 0)
    assert [(item.semantic_id, item.point_ids, item.status) for item in candidates] == [
        (6, (0,), "ambiguous"),
        (0, (1, 2), "ambiguous"),
        (0, (3, 4), "ambiguous"),
        (1, (5, 6, 7, 8, 9, 10), "observed"),
        (1, (11, 12, 13), "observed"),
    ]
    assert candidates[2].bounds_min_m[2] == 2.2
    assert candidates[4].bounds_min_m[0] == 45.0
    invalid = replace(observations, points_map_m=immutable(np.full((len(points), 3), np.nan)))
    with pytest.raises(ValueError, match="invalid detector observations"):
        ConnectedComponentDetector().detect(invalid, 0)
    invalid_ground = replace(
        observations, ground=immutable(np.full(len(points), 255, dtype=np.uint8))
    )
    with pytest.raises(ValueError, match="invalid detector observations"):
        ConnectedComponentDetector().detect(invalid_ground, 0)
