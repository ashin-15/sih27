"""Bounded sequence association of observed thing candidates, with unknown motion."""

import math
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from drishti.obstacles import MAX_CANDIDATES, InstanceEvidence

MAX_TRACKS = 512
MAX_TRACK_ID = 2**63 - 1
ASSOCIATION_METHOD = "map-center-prediction-greedy-v1"


@dataclass(frozen=True)
class TrackEvidence:
    track_id: int
    instance_id: int | None
    birth_ns: int
    last_observed_ns: int
    lifecycle: Literal["tentative", "confirmed", "occluded", "expired"]
    velocity_world_mps: tuple[float, float, float] | None
    velocity_covariance: tuple[float, ...] | None
    association_confidence: float
    supporting_frame_ids: tuple[int, ...]


@dataclass(frozen=True)
class TrackingSummary:
    method: str
    capacity: int
    eligible_candidates: int
    rejected_instance_ids: tuple[int, ...]
    frame_gap: int


@dataclass(frozen=True)
class _TrackState:
    evidence: TrackEvidence
    observation: InstanceEvidence
    previous_center: tuple[float, float, float] | None
    previous_ns: int | None
    misses: int


@dataclass(frozen=True)
class TrackingUpdate:
    sequence: str
    frame_id: int
    timestamp_ns: int
    tracks: tuple[TrackEvidence, ...]
    summary: TrackingSummary
    _states: tuple[_TrackState, ...]
    _next_id: int


def eligible(instance: InstanceEvidence) -> bool:
    return 1 <= instance.semantic_id <= 8 and instance.status == "observed"


class CandidateTracker:
    """Prepare a deterministic transition; the caller commits only accepted evidence."""

    def __init__(self, capacity: int = MAX_TRACKS) -> None:
        if type(capacity) is not int or not 1 <= capacity <= MAX_TRACKS:
            raise ValueError(f"track capacity must be between 1 and {MAX_TRACKS}")
        self.capacity = capacity
        self._sequence: str | None = None
        self._frame_id = -1
        self._timestamp_ns = -1
        self._next_id = 1
        self._states: tuple[_TrackState, ...] = ()
        self._pending: TrackingUpdate | None = None

    def prepare(
        self,
        sequence: str,
        frame_id: int,
        timestamp_ns: int,
        instances: tuple[InstanceEvidence, ...],
    ) -> TrackingUpdate:
        if self._pending is not None:
            raise ValueError("settle the pending tracker transition first")
        if not sequence or (self._sequence is not None and sequence != self._sequence):
            raise ValueError("use a new tracker for each sequence")
        if (
            type(frame_id) is not int
            or type(timestamp_ns) is not int
            or frame_id <= self._frame_id
            or timestamp_ns <= self._timestamp_ns
        ):
            raise ValueError("tracker requires increasing nonnegative frame IDs and timestamps")
        if len(instances) > MAX_CANDIDATES:
            raise ValueError("tracker candidate capacity exceeded")
        seen: set[int] = set()
        for item in instances:
            if (
                item.instance_id in seen
                or item.instance_id < 0
                or item.observed_ns != timestamp_ns
                or len(item.center_m) != 3
                or len(item.bounds_min_m) != 3
                or len(item.bounds_max_m) != 3
                or not all(
                    math.isfinite(v)
                    for v in (*item.center_m, *item.bounds_min_m, *item.bounds_max_m)
                )
                or any(
                    lo > c or c > hi
                    for lo, c, hi in zip(
                        item.bounds_min_m, item.center_m, item.bounds_max_m, strict=True
                    )
                )
            ):
                raise ValueError("invalid tracker candidate identity, time or geometry")
            seen.add(item.instance_id)
        candidates = {item.instance_id: item for item in instances if eligible(item)}
        available = set(candidates)
        states: list[_TrackState] = []
        evidence: list[TrackEvidence] = []
        for state in self._states:
            match = self._match(state, candidates, available, timestamp_ns)
            old = state.evidence
            if match is not None:
                item, confidence = match
                available.remove(item.instance_id)
                updated = replace(
                    old,
                    instance_id=item.instance_id,
                    last_observed_ns=timestamp_ns,
                    lifecycle="confirmed",
                    association_confidence=confidence,
                    supporting_frame_ids=(*old.supporting_frame_ids[-1:], frame_id),
                )
                states.append(
                    _TrackState(updated, item, state.observation.center_m, old.last_observed_ns, 0)
                )
            else:
                misses = state.misses + 1
                expired = old.lifecycle == "tentative" or misses >= 3
                updated = replace(
                    old,
                    instance_id=None,
                    lifecycle="expired" if expired else "occluded",
                    association_confidence=0.0,
                )
                if not expired:
                    states.append(replace(state, evidence=updated, misses=misses))
            evidence.append(updated)
        next_id = self._next_id
        rejected: list[int] = []
        for instance_id in sorted(available):
            if len(states) >= self.capacity:
                rejected.append(instance_id)
                continue
            if next_id > MAX_TRACK_ID:
                raise ValueError("tracker ID capacity exceeded")
            item = candidates[instance_id]
            born = TrackEvidence(
                next_id,
                instance_id,
                timestamp_ns,
                timestamp_ns,
                "tentative",
                None,
                None,
                0.0,
                (frame_id,),
            )
            next_id += 1
            states.append(_TrackState(born, item, None, None, 0))
            evidence.append(born)
        update = TrackingUpdate(
            sequence,
            frame_id,
            timestamp_ns,
            tuple(evidence),
            TrackingSummary(
                ASSOCIATION_METHOD,
                self.capacity,
                len(candidates),
                tuple(rejected),
                frame_id - self._frame_id - 1 if self._frame_id >= 0 else 0,
            ),
            tuple(states),
            next_id,
        )
        self._pending = update
        return update

    @staticmethod
    def _match(
        state: _TrackState,
        candidates: dict[int, InstanceEvidence],
        available: set[int],
        timestamp_ns: int,
    ) -> tuple[InstanceEvidence, float] | None:
        dt = (timestamp_ns - state.evidence.last_observed_ns) / 1e9
        if dt > 1.0:
            return None
        displacement = np.zeros(3, dtype=np.float64)
        if state.previous_center is not None and state.previous_ns is not None:
            duration = (state.evidence.last_observed_ns - state.previous_ns) / 1e9
            velocity = (np.asarray(state.observation.center_m) - state.previous_center) / duration
            speed = float(np.linalg.norm(velocity))
            displacement = velocity * min(1.0, 30.0 / speed) * dt if speed else displacement
        center = np.asarray(state.observation.center_m) + displacement
        low = np.asarray(state.observation.bounds_min_m) + displacement - 0.75
        high = np.asarray(state.observation.bounds_max_m) + displacement + 0.75
        radius = min(5.0, 1.5 + 30.0 * dt)
        best: tuple[float, int] | None = None
        for instance_id in available:
            item = candidates[instance_id]
            if item.semantic_id != state.observation.semantic_id:
                continue
            distance = math.dist(center, item.center_m)
            if (
                distance <= radius
                and np.all(np.asarray(item.bounds_max_m) >= low)
                and np.all(np.asarray(item.bounds_min_m) <= high)
            ):
                key = (distance, instance_id)
                if best is None or key < best:
                    best = key
        return None if best is None else (candidates[best[1]], max(0.0, 1.0 - best[0] / radius))

    def commit(self, update: TrackingUpdate) -> None:
        if update is not self._pending:
            raise ValueError("foreign or already settled tracker transition")
        self._sequence = update.sequence
        self._frame_id = update.frame_id
        self._timestamp_ns = update.timestamp_ns
        self._states = update._states
        self._next_id = update._next_id
        self._pending = None

    def discard(self, update: TrackingUpdate) -> None:
        if update is not self._pending:
            raise ValueError("foreign or already settled tracker transition")
        self._pending = None
