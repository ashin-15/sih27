"""Bounded diagnostic map-frame displacement estimates from observed associations.

These estimates use visible candidate centres, not object ground truth. They
are uncalibrated and remain separate from the frozen unknown-motion receipts.
"""

import math
from dataclasses import dataclass

import numpy as np

from drishti.arrays import ByteArray, IntArray, immutable
from drishti.obstacles import InstanceEvidence
from drishti.semantics import Motion
from drishti.tracking import MAX_TRACKS, TrackEvidence

MOTION_METHOD = "observed-map-center-displacement-v1"


@dataclass(frozen=True)
class MotionSettings:
    minimum_span_s: float = 0.2
    stationary_max_mps: float = 0.2
    moving_min_mps: float = 0.8

    def __post_init__(self) -> None:
        if (
            not all(
                math.isfinite(x)
                for x in (self.minimum_span_s, self.stationary_max_mps, self.moving_min_mps)
            )
            or self.minimum_span_s <= 0
            or not 0 <= self.stationary_max_mps < self.moving_min_mps
        ):
            raise ValueError("invalid motion estimation thresholds")


@dataclass(frozen=True)
class MotionEstimate:
    track_id: int
    instance_id: int | None
    state: int
    velocity_map_mps: tuple[float, float, float] | None
    observations: int
    span_s: float
    reason: str


@dataclass(frozen=True)
class MotionView:
    method: str
    settings: MotionSettings
    point_ids: IntArray
    point_state: ByteArray
    estimates: tuple[MotionEstimate, ...]


@dataclass(frozen=True)
class _Observation:
    frame_id: int
    timestamp_ns: int
    center_m: tuple[float, float, float]


class MotionEstimator:
    """One sequence, at most three observations per track, unknown after any gap."""

    def __init__(self, settings: MotionSettings | None = None) -> None:
        self.settings = MotionSettings() if settings is None else settings
        self._sequence: str | None = None
        self._frame_id = -1
        self._timestamp_ns = -1
        self._history: dict[int, tuple[_Observation, ...]] = {}

    def update(
        self,
        sequence: str,
        frame_id: int,
        timestamp_ns: int,
        point_ids: IntArray,
        instances: tuple[InstanceEvidence, ...],
        tracks: tuple[TrackEvidence, ...],
        *,
        pose_valid: bool = True,
    ) -> MotionView:
        if not sequence or (self._sequence is not None and sequence != self._sequence):
            raise ValueError("use a new motion estimator for each sequence")
        if (
            type(frame_id) is not int
            or type(timestamp_ns) is not int
            or frame_id <= self._frame_id
            or timestamp_ns <= self._timestamp_ns
        ):
            raise ValueError("motion requires increasing nonnegative frame IDs and timestamps")
        if (
            point_ids.ndim != 1
            or point_ids.dtype != np.int64
            or np.any(point_ids < 0)
            or len(np.unique(point_ids)) != len(point_ids)
            or len(tracks) > 2 * MAX_TRACKS
            or sum(t.lifecycle != "expired" for t in tracks) > MAX_TRACKS
            or any(type(t.track_id) is not int or t.track_id < 1 for t in tracks)
            or len({t.track_id for t in tracks}) != len(tracks)
        ):
            raise ValueError("invalid motion point IDs or track capacity")
        candidates = {item.instance_id: item for item in instances}
        if len(candidates) != len(instances):
            raise ValueError("duplicate motion candidate")
        order = np.argsort(point_ids)
        ordered_ids = point_ids[order]
        states = np.full(len(point_ids), Motion.UNKNOWN, dtype=np.uint8)
        history: dict[int, tuple[_Observation, ...]] = {}
        estimates = []
        claimed = np.zeros(len(point_ids), dtype=np.bool_)
        for track in tracks:
            old = self._history.get(track.track_id, ())
            item = candidates.get(track.instance_id) if track.instance_id is not None else None
            state = Motion.UNKNOWN
            velocity = None
            span = 0.0
            reason = "unobserved"
            current: tuple[_Observation, ...] = ()
            if item is not None and track.lifecycle in ("tentative", "confirmed") and pose_valid:
                support = np.asarray(item.point_ids, dtype=np.int64)
                found = np.searchsorted(ordered_ids, support)
                if (
                    np.any(found >= len(point_ids))
                    or not np.array_equal(ordered_ids[found], support)
                    or len(np.unique(support)) != len(support)
                ):
                    raise ValueError("invalid motion candidate support")
                positions = order[found]
                if (
                    item.observed_ns != timestamp_ns
                    or track.last_observed_ns != timestamp_ns
                    or not all(math.isfinite(value) for value in item.center_m)
                    or len(item.center_m) != 3
                    or claimed[positions].any()
                ):
                    raise ValueError("invalid motion candidate support, center or timestamp")
                claimed[positions] = True
                if old and old[-1].frame_id != frame_id - 1:
                    old = ()
                current = (*old[-2:], _Observation(frame_id, timestamp_ns, item.center_m))
                span = (timestamp_ns - current[0].timestamp_ns) / 1e9
                reason = "insufficient-history"
                if len(current) == 3 and span >= self.settings.minimum_span_s:
                    first = current[0].center_m
                    velocity = (
                        (item.center_m[0] - first[0]) / span,
                        (item.center_m[1] - first[1]) / span,
                        (item.center_m[2] - first[2]) / span,
                    )
                    speed = math.sqrt(sum(v * v for v in velocity))
                    state = (
                        Motion.MOVING
                        if speed > self.settings.moving_min_mps
                        else Motion.STATIONARY
                        if speed < self.settings.stationary_max_mps
                        else Motion.UNKNOWN
                    )
                    reason = "estimated" if state != Motion.UNKNOWN else "threshold-band"
                history[track.track_id] = current
                states[positions] = state
            elif not pose_valid:
                reason = "pose-unverified"
            estimates.append(
                MotionEstimate(
                    track.track_id,
                    track.instance_id,
                    int(state),
                    velocity,
                    len(current),
                    span,
                    reason,
                )
            )
        self._sequence = sequence
        self._frame_id, self._timestamp_ns = frame_id, timestamp_ns
        self._history = history
        return MotionView(
            MOTION_METHOD, self.settings, immutable(point_ids), immutable(states), tuple(estimates)
        )
