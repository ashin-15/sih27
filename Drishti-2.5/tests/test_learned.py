from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from drishti.arrays import ByteArray, IntArray, PointArray
from drishti.config import MappingConfig
from drishti.contracts import Mode, ScanFrame, make_frame
from drishti.dataset import DatasetSource
from drishti.ground import GroundClass
from drishti.learned import SemanticPrediction, _checked_digest, remap_frnet_output, sha256_file
from drishti.pipeline import MappingEngine
from drishti.product_result import (
    InProcessProductEvaluator,
    ReceiptStatus,
    semantic_product_result,
)
from drishti.semantics import LEARNING_TO_RAW, decode_semantickitti


class FlatGround:
    method = "flat-test-fixture"

    def segment(self, points: PointArray) -> ByteArray:
        return np.full(len(points), GroundClass.NONGROUND, dtype=np.uint8)


class RecordingPredictor:
    checkpoint_sha256 = "a" * 64
    weights_sha256 = "b" * 64

    def __init__(self) -> None:
        self.seen_ids: list[int] = []

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction:
        self.seen_ids = point_ids.tolist()
        assert points.shape == (len(point_ids), 4)
        semantic = np.where(point_ids == 0, 1, 0).astype(np.uint8)
        return SemanticPrediction(
            semantic,
            np.full(len(points), 0.75, dtype=np.float64),
            np.where(semantic == 0, 2, 0).astype(np.uint8),
        )

    def close(self) -> None:
        pass


def test_frnet_channel_remap_and_raw_inverse() -> None:
    prediction = remap_frnet_output(
        np.array([0, 4, 18, 19], dtype=np.uint8),
        np.array([0.9, 0.8, 0.7, 0.6], dtype=np.float64),
    )
    assert prediction.semantic_id.tolist() == [1, 5, 19, 0]
    assert prediction.unknown_reason.tolist() == [0, 0, 0, 2]
    assert not prediction.semantic_id.flags.writeable
    round_trip = decode_semantickitti(LEARNING_TO_RAW).semantic
    assert round_trip.tolist() == list(range(20))
    with pytest.raises(ValueError, match="classes"):
        remap_frnet_output(np.array([20], dtype=np.uint8), np.array([0.5]))
    with pytest.raises(ValueError, match="scores"):
        remap_frnet_output(np.array([0], dtype=np.uint8), np.array([np.nan]))


def test_checkpoint_digest_guard_rejects_wrong_or_malformed_hash(tmp_path: Path) -> None:
    checkpoint = tmp_path / "weights.npz"
    checkpoint.write_bytes(b"tensor-only-fixture")
    digest = sha256_file(checkpoint)
    assert _checked_digest(checkpoint, digest, "tensor export") == digest
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _checked_digest(checkpoint, "0" * 64, "tensor export")
    with pytest.raises(ValueError, match="64 lowercase hex"):
        _checked_digest(checkpoint, digest.upper(), "tensor export")


def test_learned_mapping_preserves_accepted_ids_and_never_reads_oracle() -> None:
    class TrappedFrame(ScanFrame):
        def __getattribute__(self, name: str) -> object:
            if name == "annotations" and object.__getattribute__(self, "__dict__").get(
                "_trap", False
            ):
                raise AssertionError("learned inference accessed oracle annotations")
            return super().__getattribute__(name)

    points = np.array(
        [[5.01, 0, 0, 0.5], [5.02, 0, 0, 0.5], [101, 0, 0, 0.5]],
        dtype=np.float32,
    )
    labels = decode_semantickitti(np.array([40, 40, 40], dtype=np.uint32))
    ordinary = make_frame(points, annotations=labels)
    frame = TrappedFrame(
        ordinary.sequence,
        ordinary.frame_id,
        ordinary.timestamp_s,
        ordinary.points_sensor,
        ordinary.point_ids,
        ordinary.map_from_sensor,
        ordinary.pose_source,
        ordinary.annotations,
    )
    object.__setattr__(frame, "_trap", True)
    predictor = RecordingPredictor()
    config = MappingConfig()
    result = MappingEngine(
        config, mode=Mode.LEARNED, predictor=predictor, ground=FlatGround()
    ).process(frame)
    assert predictor.seen_ids == [0, 1]
    assert result.observations.point_ids.tolist() == [0, 1]
    assert result.observations.semantic.tolist() == [1, 0]
    assert result.observations.semantic_unknown_reason.tolist() == [0, 2]
    assert result.accounting.outside_roi == 1
    assert result.accounting.projection_collisions == 1
    product = semantic_product_result(
        frame,
        result,
        run_id="fixture",
        code_revision="c" * 64,
        checkpoint_sha256=predictor.checkpoint_sha256,
        weights_sha256=predictor.weights_sha256,
        cell_sizes_cm=config.cell_sizes_cm,
    )
    receipt = InProcessProductEvaluator().receive(frame, product)
    assert receipt.status == ReceiptStatus.ACCEPTED
    assert receipt.schema_version == 2
    assert receipt.stage == "semantic"
    assert not product.point_ids.flags.writeable
    rejected = InProcessProductEvaluator().receive(
        frame, replace(product, model_weights_sha256=None)
    )
    assert rejected.error_code == "semantic-provenance"


def test_learned_input_guards_and_empty_scan() -> None:
    predictor = RecordingPredictor()
    with pytest.raises(ValueError, match="requires a predictor"):
        MappingEngine(MappingConfig(), mode=Mode.LEARNED)
    with pytest.raises(ValueError, match="forbid"):
        MappingEngine(MappingConfig(), mode=Mode.GEOMETRIC, predictor=predictor)
    bad = np.array([[5, 0, 0, np.nan]], dtype=np.float32)
    with pytest.raises(ValueError, match="finite intensity"):
        MappingEngine(
            MappingConfig(), mode=Mode.LEARNED, predictor=predictor, ground=FlatGround()
        ).process(make_frame(bad))
    empty = MappingEngine(
        MappingConfig(), mode=Mode.LEARNED, predictor=predictor, ground=FlatGround()
    ).process(make_frame(np.empty((0, 4), dtype=np.float32)))
    assert empty.accounting.accepted_points == 0
    assert empty.observations.semantic.size == 0


def test_learned_dataset_source_does_not_require_labels(dataset_root: Path) -> None:
    for path in (dataset_root / "sequences/08/labels").glob("*.label"):
        path.unlink()
    source = DatasetSource(dataset_root, "08", mode=Mode.LEARNED)
    frame = next(source.frames(max_frames=1))
    assert frame.annotations is None
