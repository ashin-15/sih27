"""Synchronous receipt for the current in-memory frame result.

This is a diagnostic consumer for the implemented single-frame slice. The first-release
machine-output schema and consumer remain open product decisions.
"""

import hashlib
import json
from dataclasses import asdict, dataclass

import numpy as np

from drishti.contracts import ScanFrame
from drishti.pipeline import FrameResult

DIAGNOSTIC_PAYLOAD_SCHEMA = "drishti-current-frame-v1"


@dataclass(frozen=True)
class FrameReceipt:
    schema: str
    sequence: str
    frame_id: int
    timestamp_s: float
    map_digest: str
    result_digest: str
    accepted_points: int
    cells: int


class InProcessFrameConsumer:
    """Acknowledge an entire current result only after inspecting its payload."""

    def receive(self, frame: ScanFrame, result: FrameResult) -> FrameReceipt:
        snapshot = result.snapshot
        observations = result.observations
        accounting = result.accounting
        if (
            snapshot.sequence != frame.sequence
            or snapshot.frame_id != frame.frame_id
            or snapshot.timestamp_s != frame.timestamp_s
            or snapshot.pose_source != frame.pose_source
        ):
            raise ValueError("frame result identity does not match its input scan")
        accepted = accounting.accepted_points
        if (
            len(observations.point_ids) != accepted
            or len(observations.points_sensor) != accepted
            or len(observations.points_map_m) != accepted
            or len(observations.ground) != accepted
            or len(observations.semantic) != accepted
            or len(observations.motion) != accepted
            or len(observations.cell_indices) != accepted
            or int(snapshot.point_count.sum()) != accepted
        ):
            raise ValueError("frame result payload is not point-aligned")
        if int(np.count_nonzero(result.range_image.valid)) != accounting.projected_points:
            raise ValueError("range image does not match point accounting")

        map_digest = snapshot.digest
        digest = hashlib.sha256()
        digest.update(DIAGNOSTIC_PAYLOAD_SCHEMA.encode())
        digest.update(map_digest.encode())
        for name, values in (
            ("points_sensor", observations.points_sensor),
            ("points_map_m", observations.points_map_m),
            ("point_ids", observations.point_ids),
            ("ground", observations.ground),
            ("semantic", observations.semantic),
            ("motion", observations.motion),
            ("cell_indices", observations.cell_indices),
            ("range_m", result.range_image.ranges_m),
            ("range_ids", result.range_image.point_ids),
        ):
            if values.flags.writeable:
                raise ValueError(f"frame result {name} must be immutable")
            digest.update(name.encode())
            digest.update(str(values.dtype).encode())
            digest.update(str(values.shape).encode())
            digest.update(values.tobytes())
        digest.update(json.dumps(asdict(accounting), sort_keys=True).encode())
        digest.update(str(result.range_image.collisions).encode())
        digest.update(str(result.range_image.outside_fov).encode())
        return FrameReceipt(
            schema=DIAGNOSTIC_PAYLOAD_SCHEMA,
            sequence=frame.sequence,
            frame_id=frame.frame_id,
            timestamp_s=frame.timestamp_s,
            map_digest=map_digest,
            result_digest=digest.hexdigest(),
            accepted_points=accepted,
            cells=len(snapshot.point_count),
        )
