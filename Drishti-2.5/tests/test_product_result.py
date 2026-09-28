from dataclasses import replace

import numpy as np

from drishti.arrays import immutable
from drishti.config import MappingConfig
from drishti.contracts import Accounting, Mode, ScanFrame, make_frame
from drishti.pipeline import MappingEngine
from drishti.product_result import (
    InProcessProductEvaluator,
    Occupancy,
    ProductFrameResult,
    ReceiptStatus,
    canonical_result_digest,
    diagnostic_product_result,
    source_scan_digest,
)
from drishti.semantics import decode_semantickitti


def _result() -> tuple[ScanFrame, ProductFrameResult]:
    points = np.array([[5.01, 0.01, -1.73, 0.2], [8.01, 1.01, 0.5, 0.8]], dtype=np.float32)
    frame = make_frame(points)
    config = MappingConfig()
    mapped = MappingEngine(config).process(frame)
    product = diagnostic_product_result(
        frame,
        mapped,
        run_id="fixture",
        code_revision="a" * 64,
        backend="cpu",
        cell_sizes_cm=config.cell_sizes_cm,
    )
    return frame, product


def test_diagnostic_product_receipt_and_digest_are_stable() -> None:
    frame, product = _result()
    evaluator = InProcessProductEvaluator()
    receipt = evaluator.receive(frame, product)
    assert receipt.status == ReceiptStatus.ACCEPTED
    assert receipt.stage == "diagnostic"
    assert receipt.error_code is None
    assert receipt.result_digest == canonical_result_digest(product)
    assert receipt.result_digest != canonical_result_digest(replace(product, run_id="other"))
    assert receipt.validation_duration_ns >= 0
    assert np.all(product.semantic_id == 0)
    assert np.all(product.cells.occupancy != Occupancy.OBSERVED_FREE)
    assert evaluator.receive(frame, product).error_code == "nonmonotonic-frame"


def test_schema_one_digest_keeps_t002_canonical_payload() -> None:
    _, product = _result()
    normalized = replace(product, diagnostics=replace(product.diagnostics, ground_ms=0.0))
    assert canonical_result_digest(normalized) == (
        "0ce7c3368f492f5aee76f613984294e2ea5fbecdc7ab7c70d551d1ec4af4bfa6"
    )


def test_product_evaluator_rejects_unsealed_misaligned_and_unsupported_claims() -> None:
    frame, product = _result()

    def error(candidate: ProductFrameResult) -> str | None:
        return InProcessProductEvaluator().receive(frame, candidate).error_code

    assert error(replace(product, schema_version=2)) == "unsupported-schema"
    assert error(replace(product, point_ids=np.array([0, 1], dtype=np.int64))) == "unsealed-array"
    assert error(replace(product, point_ids=immutable(np.array([1, 0], dtype=np.int64)))) == (
        "point-id-alignment"
    )
    assert error(replace(product, semantic_id=immutable(np.array([1, 0], dtype=np.uint8)))) == (
        "unsupported-semantic"
    )
    assert error(replace(product, pose_source="unknown")) == "pose-mismatch"
    assert error(replace(product, source_scan_digest="0" * 64)) == "input-identity-mismatch"

    cells = product.cells
    duplicated = replace(
        cells,
        level=immutable(np.full(len(cells.level), cells.level[0], dtype=np.int64)),
        indices=immutable(np.repeat(cells.indices[:1], len(cells.level), axis=0)),
    )
    assert error(replace(product, cells=duplicated)) == "cell-overlap"

    free = replace(
        cells,
        occupancy=immutable(np.full(len(cells.level), Occupancy.OBSERVED_FREE, dtype=np.uint8)),
        ray_support=immutable(np.ones(len(cells.level), dtype=np.int64)),
    )
    complete = replace(
        product,
        stage="complete",
        checkpoint_sha256="b" * 64,
        calibration_id="fixture",
        calibration_digest="c" * 64,
        cells=free,
    )
    assert error(complete) == "unsupported-free"


def test_rejection_does_not_advance_sequence_and_oracle_labels_do_not_enter_diagnostic() -> None:
    frame, product = _result()
    evaluator = InProcessProductEvaluator()
    rejected = evaluator.receive(frame, replace(product, schema_version=2))
    assert rejected.status == ReceiptStatus.REJECTED
    assert rejected.result_digest is None
    assert evaluator.receive(frame, product).status == ReceiptStatus.ACCEPTED

    annotated = make_frame(
        frame.points_sensor,
        annotations=decode_semantickitti(np.array([10, 50], dtype=np.uint32)),
    )
    config = MappingConfig()
    oracle_result = MappingEngine(config, mode=Mode.ORACLE).process(annotated)
    assert np.any(oracle_result.observations.semantic != 0)
    diagnostic = diagnostic_product_result(
        annotated,
        oracle_result,
        run_id="oracle-fixture",
        code_revision="a" * 64,
        backend="cpu",
        cell_sizes_cm=config.cell_sizes_cm,
    )
    assert np.all(diagnostic.semantic_id == 0)
    assert InProcessProductEvaluator().receive(annotated, diagnostic).status == (
        ReceiptStatus.ACCEPTED
    )


def test_complete_result_rejects_approved_point_cap_without_truncation() -> None:
    _, product = _result()
    points = np.zeros((130_001, 4), dtype=np.float32)
    frame = make_frame(points)
    over_cap = replace(
        product,
        stage="complete",
        source_scan_digest=source_scan_digest(frame),
        checkpoint_sha256="b" * 64,
        calibration_id="fixture",
        calibration_digest="c" * 64,
        accounting=Accounting(130_001, 0, 0, 0, 130_001, 0, 130_001, 0, 0),
    )
    receipt = InProcessProductEvaluator().receive(frame, over_cap)
    assert receipt.status == ReceiptStatus.REJECTED
    assert receipt.error_code == "above-release-point-cap"


def test_complete_result_schema_accepts_aligned_prediction_without_release_claim() -> None:
    frame, product = _result()
    complete = replace(
        product,
        stage="complete",
        checkpoint_sha256="b" * 64,
        calibration_id="fixture",
        calibration_digest="c" * 64,
        semantic_id=immutable(np.array([1, 0], dtype=np.uint8)),
        semantic_confidence=immutable(np.array([0.8, 0.0], dtype=np.float64)),
        semantic_support=immutable(np.array([1, 0], dtype=np.uint8)),
        semantic_unknown_reason=immutable(np.array([0, 2], dtype=np.uint8)),
    )
    receipt = InProcessProductEvaluator().receive(frame, complete)
    assert receipt.status == ReceiptStatus.ACCEPTED
    assert receipt.stage == "complete"
    assert receipt.result_digest == canonical_result_digest(complete)
