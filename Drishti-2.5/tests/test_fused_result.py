from dataclasses import replace

import numpy as np
import pytest

from drishti.arrays import immutable
from drishti.config import MappingConfig
from drishti.contracts import make_frame
from drishti.fused_result import finish_fused_receipt, prepare_fused_receipt
from drishti.pipeline import MappingEngine
from drishti.product_result import InProcessProductEvaluator, diagnostic_product_result
from drishti.temporal import TemporalMap


def test_fused_receipt_validates_before_digest_and_binds_current_receipt() -> None:
    config = MappingConfig()
    temporal = TemporalMap(config)
    frame = make_frame(np.array([[5, 0, -1.73, 0.5], [30, 0, 1, 0.8]], np.float32))
    result = MappingEngine(config, temporal=temporal).process(frame)
    draft = prepare_fused_receipt(frame, result, config, temporal.settings)
    product = diagnostic_product_result(
        frame,
        result,
        run_id="test",
        code_revision="c" * 64,
        backend="cpu",
        cell_sizes_cm=config.cell_sizes_cm,
    )
    current = InProcessProductEvaluator().receive(frame, product)
    receipt = finish_fused_receipt(draft, current)
    assert receipt.result_digest != current.result_digest
    assert receipt.receipt_monotonic_ns >= current.receipt_monotonic_ns
    with pytest.raises(ValueError, match="current-receipt"):
        finish_fused_receipt(draft, replace(current, frame_id=current.frame_id + 1))
    assert result.fused is not None
    with pytest.raises(ValueError, match="unsealed-array"):
        prepare_fused_receipt(
            frame,
            replace(result, fused=replace(result.fused, terrain=result.fused.terrain.copy())),
            config,
            temporal.settings,
        )
    bad = immutable(np.full(len(result.fused.level), 1, dtype=np.uint8))
    with pytest.raises(ValueError, match="terrain"):
        prepare_fused_receipt(
            frame,
            replace(result, fused=replace(result.fused, terrain=bad)),
            config,
            temporal.settings,
        )
    changed = replace(result.fused, observations=immutable(result.fused.observations + 1))
    other = prepare_fused_receipt(frame, replace(result, fused=changed), config, temporal.settings)
    assert other.extension_digest != draft.extension_digest


def test_fused_receipt_rejects_future_observations_and_bad_summary() -> None:
    config = MappingConfig()
    temporal = TemporalMap(config)
    frame = make_frame(np.array([[5, 0, -1.73, 0.5]], np.float32))
    result = MappingEngine(config, temporal=temporal).process(frame)
    assert result.fused is not None
    future = replace(result.fused, last_seen_ns=immutable(result.fused.last_seen_ns + 1))
    with pytest.raises(ValueError, match="range"):
        prepare_fused_receipt(frame, replace(result, fused=future), config, temporal.settings)
    bad = replace(result.fused, summary=replace(result.fused.summary, published_cells=0))
    with pytest.raises(ValueError, match="summary"):
        prepare_fused_receipt(frame, replace(result, fused=bad), config, temporal.settings)
