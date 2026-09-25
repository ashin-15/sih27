from dataclasses import replace

import numpy as np
import pytest

from drishti.config import MappingConfig
from drishti.contracts import make_frame
from drishti.output import DIAGNOSTIC_PAYLOAD_SCHEMA, InProcessFrameConsumer
from drishti.pipeline import MappingEngine


def test_inprocess_receipt_covers_current_result_and_rejects_mismatch() -> None:
    points = np.array([[5.01, 0.01, -1.73, 0.2], [5.02, 0.01, 0.5, 0.8]], dtype=np.float32)
    frame = make_frame(points)
    result = MappingEngine(MappingConfig()).process(frame)
    consumer = InProcessFrameConsumer()
    receipt = consumer.receive(frame, result)
    assert receipt.schema == DIAGNOSTIC_PAYLOAD_SCHEMA
    assert receipt.map_digest == result.snapshot.digest
    assert receipt.accepted_points == 2
    assert len(receipt.result_digest) == 64
    with pytest.raises(ValueError, match="identity"):
        consumer.receive(frame, replace(result, snapshot=replace(result.snapshot, frame_id=1)))
    with pytest.raises(ValueError, match="point-aligned"):
        consumer.receive(
            frame,
            replace(
                result,
                observations=replace(result.observations, point_ids=np.array([], dtype=np.int64)),
            ),
        )
