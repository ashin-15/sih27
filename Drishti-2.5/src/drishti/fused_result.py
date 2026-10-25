"""Versioned receipt extension for the complete current diagnostic fused output.

Validate and seal the extension before committing the existing product receipt.
This checks the output contract, not historical free-space or terrain accuracy.
"""

import hashlib
from dataclasses import dataclass
from time import perf_counter_ns

import numpy as np

from drishti.config import MappingConfig
from drishti.contracts import ScanFrame
from drishti.pipeline import FrameResult
from drishti.product_result import ProductReceipt, ReceiptStatus, _feed_raw, _validate_arrays
from drishti.temporal import TEMPORAL_METHOD, TemporalSettings, TerrainState
from drishti.visibility import pack_cells

FUSED_RECEIPT_SCHEMA = "drishti-fused-envelope-v1"


@dataclass(frozen=True)
class FusedReceiptDraft:
    sequence: str
    frame_id: int
    timestamp_ns: int
    config_digest: str
    extension_digest: str


@dataclass(frozen=True)
class FusedReceipt:
    schema: str
    sequence: str
    frame_id: int
    timestamp_ns: int
    config_digest: str
    current_product_digest: str
    extension_digest: str
    result_digest: str
    receipt_monotonic_ns: int
    status: str = "accepted"
    meaning: str = "complete current diagnostic arrays; quality and historical proofs unverified"


def prepare_fused_receipt(
    frame: ScanFrame, result: FrameResult, config: MappingConfig, settings: TemporalSettings
) -> FusedReceiptDraft:
    view = result.fused
    if view is None:
        raise ValueError("fused-contract-missing")
    if (
        result.snapshot.sequence != frame.sequence
        or result.snapshot.frame_id != frame.frame_id
        or result.snapshot.timestamp_s != frame.timestamp_s
        or result.snapshot.config_digest != config.digest
    ):
        raise ValueError("fused-contract-identity")
    _validate_arrays(view)
    n = len(view.level)
    integer = (view.level, view.last_seen_ns, view.observations)
    byte = (view.occupancy, view.terrain, view.flags, view.semantic)
    floating = (
        view.size_m,
        view.ground_height_m,
        view.ground_sigma_m,
        view.obstacle_low_m,
        view.obstacle_high_m,
    )
    if (
        any(a.shape != (n,) or a.dtype != np.int64 for a in integer)
        or any(a.shape != (n,) or a.dtype != np.uint8 for a in byte)
        or any(
            a.shape != (n,) or a.dtype != np.float64 or not np.isfinite(a).all() for a in floating
        )
        or view.indices.shape != (n, 2)
        or view.indices.dtype != np.int64
        or view.centers_xy_m.shape != (n, 2)
        or view.centers_xy_m.dtype != np.float64
        or not np.isfinite(view.centers_xy_m).all()
        or view.ground_valid.shape != (n,)
        or view.ground_valid.dtype != np.bool_
    ):
        raise ValueError("fused-contract-array")
    stamp = round(frame.timestamp_s * 1e9)
    if (
        np.any(view.level < 0)
        or np.any(view.level >= len(config.ratios))
        or np.any(view.terrain > 4)
        or np.any(view.occupancy > 3)
        or np.any(view.flags > 7)
        or np.any(view.semantic > 19)
        or np.any(view.last_seen_ns < 0)
        or np.any(view.last_seen_ns > stamp)
        or np.any(view.observations < 0)
        or np.any(view.ground_sigma_m < -1)
        or (n and np.abs(view.indices).max() >= 1 << 25)
    ):
        raise ValueError("fused-contract-range")
    widths = np.asarray(config.cell_sizes_cm)[view.level] / 100
    if not np.array_equal(view.size_m, widths) or not np.array_equal(
        view.centers_xy_m, (view.indices + 0.5) * widths[:, None]
    ):
        raise ValueError("fused-contract-geometry")
    packed = np.sort(pack_cells(view.level, view.indices))
    if np.any(packed[1:] == packed[:-1]):
        raise ValueError("fused-contract-overlap")
    for level, ratio in enumerate(config.ratios):
        finer = view.indices[view.level == level]
        for coarse in range(level + 1, len(config.ratios)):
            parents = pack_cells(
                np.full(len(finer), coarse, dtype=np.int64),
                finer // (config.ratios[coarse] // ratio),
            )
            if np.isin(parents, packed).any():
                raise ValueError("fused-contract-overlap")
    stale = stamp - view.last_seen_ns > round(settings.stale_after_s * 1e9)
    drivable = view.terrain == TerrainState.DRIVABLE
    valid_ground = (view.ground_sigma_m >= 0) & (view.ground_sigma_m <= settings.valid_sigma_m)
    if (
        not np.array_equal(view.ground_valid, valid_ground)
        or np.any(view.ground_height_m[~view.ground_valid] != 0)
        or np.any((view.terrain == TerrainState.STALE) != stale)
        or np.any((view.occupancy == 3) != stale)
        or np.any(
            drivable
            & (
                ~view.ground_valid
                | ~np.isin(view.semantic, settings.drivable_classes)
                | ((view.flags & 3) != 0)
            )
        )
    ):
        raise ValueError("fused-contract-terrain")
    summary = view.summary
    if (
        summary.method != TEMPORAL_METHOD
        or summary.published_cells != n
        or summary.terrain_counts != tuple(np.bincount(view.terrain, minlength=5))
        or summary.occupancy_counts != tuple(np.bincount(view.occupancy, minlength=4))
        or summary.curb_cells != np.count_nonzero(view.flags & 1)
        or summary.drop_cells != np.count_nonzero(view.flags & 2)
        or summary.overhang_cells != np.count_nonzero(view.flags & 4)
        or summary.allocated_bytes <= 0
    ):
        raise ValueError("fused-contract-summary")
    motion = result.estimated_motion
    if motion is not None:
        _validate_arrays(motion)
        if (
            not np.array_equal(motion.point_ids, result.observations.point_ids)
            or motion.point_state.shape != motion.point_ids.shape
            or motion.point_state.dtype != np.uint8
            or np.any(motion.point_state > 2)
        ):
            raise ValueError("fused-contract-motion")
    if config.foveation_enabled != (result.foveation is not None):
        raise ValueError("fused-contract-foveation")
    digest = hashlib.sha256(FUSED_RECEIPT_SCHEMA.encode())
    _feed_raw(digest, (frame.sequence, frame.frame_id, stamp, config.digest))
    _feed_raw(digest, settings)
    _feed_raw(digest, view)
    _feed_raw(digest, motion)
    _feed_raw(digest, result.foveation)
    return FusedReceiptDraft(
        frame.sequence, frame.frame_id, stamp, config.digest, digest.hexdigest()
    )


def finish_fused_receipt(draft: FusedReceiptDraft, current: ProductReceipt) -> FusedReceipt:
    if (
        current.status != ReceiptStatus.ACCEPTED
        or current.result_digest is None
        or current.sequence_id != draft.sequence
        or current.frame_id != draft.frame_id
    ):
        raise ValueError("fused-contract-current-receipt")
    digest = hashlib.sha256(
        f"{FUSED_RECEIPT_SCHEMA}:{current.result_digest}:{draft.extension_digest}".encode()
    ).hexdigest()
    return FusedReceipt(
        FUSED_RECEIPT_SCHEMA,
        draft.sequence,
        draft.frame_id,
        draft.timestamp_ns,
        draft.config_digest,
        current.result_digest,
        draft.extension_digest,
        digest,
        perf_counter_ns(),
    )
