"""Version 1 complete-result contract and synchronous same-process evaluator.

The current engine can populate a diagnostic result with explicit unknown evidence.
Only a later complete producer may set stage to ``complete``.
"""

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import IntEnum, StrEnum
from time import monotonic_ns
from typing import Literal

import numpy as np

from drishti.arrays import BoolArray, ByteArray, FloatArray, IntArray, immutable
from drishti.contracts import Accounting, ScanFrame
from drishti.learned import FRNET_CLASS_MAP_VERSION, FRNET_REVISION
from drishti.pipeline import FrameResult

SCHEMA_VERSION = 1
SEMANTIC_SCHEMA_VERSION = 2
RELEASE_POINT_CAP = 130_000
COORDINATE_FRAME = "map-x-forward-y-left-z-up"
UNITS = "metre-nanosecond"


class Occupancy(IntEnum):
    UNKNOWN = 0
    OCCUPIED = 1
    OBSERVED_FREE = 2
    STALE = 3
    AMBIGUOUS = 4


class EvidenceSource(IntEnum):
    NONE = 0
    CURRENT_SCAN = 1
    TEMPORAL_FUSION = 2


class UnknownReason(IntEnum):
    NONE = 0
    NO_MODEL = 1
    INSUFFICIENT_EVIDENCE = 2


class ReceiptStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class InstanceEvidence:
    instance_id: int
    semantic_id: int
    semantic_confidence: float
    center_m: tuple[float, float, float]
    bounds_min_m: tuple[float, float, float]
    bounds_max_m: tuple[float, float, float]
    point_ids: tuple[int, ...]
    observed_ns: int
    uncertainty_m: float | None
    status: Literal["observed", "ambiguous"]


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
class BeamProof:
    beam_id: int
    point_id: int
    origin_map_m: tuple[float, float, float]
    return_map_m: tuple[float, float, float]


@dataclass(frozen=True)
class CellEvidence:
    cell_sizes_cm: tuple[int, ...]
    level: IntArray
    indices: IntArray
    occupancy: ByteArray
    semantic_id: ByteArray
    semantic_support: IntArray
    last_observed_ns: IntArray
    source: ByteArray
    ray_support: IntArray
    obstacle_support: IntArray
    uncertainty: FloatArray
    conflict: BoolArray
    free_beam_id: IntArray


@dataclass(frozen=True)
class ProductDiagnostics:
    load_ms: float | None
    ground_ms: float
    model_ms: float | None
    detector_ms: float | None
    association_ms: float | None
    visibility_ms: float | None
    fusion_ms: float | None
    transfer_ms: float | None
    queue_depth: int
    queue_age_ms: float
    dropped_scans: int
    invalid_scans: int
    map_cells: int
    track_count: int
    process_rss_bytes: int | None
    device_memory_bytes: int | None
    device_memory_status: Literal["unavailable", "sampled"]


@dataclass(frozen=True)
class ProductFrameResult:
    schema_version: int
    stage: Literal["diagnostic", "semantic", "complete"]
    run_id: str
    sequence_id: str
    frame_id: int
    scan_timestamp_ns: int
    scheduled_arrival_ns: int | None
    source_scan_digest: str
    config_digest: str
    code_revision: str
    backend: Literal["cpu", "cuda"]
    checkpoint_sha256: str | None
    accounting: Accounting
    point_ids: IntArray
    semantic_id: ByteArray
    semantic_confidence: FloatArray
    semantic_support: ByteArray
    semantic_unknown_reason: ByteArray
    motion_state: ByteArray
    motion_confidence: FloatArray
    pose_map_from_sensor: FloatArray
    pose_source: str
    pose_quality: Literal["unverified", "verified", "degraded"]
    calibration_id: str | None
    calibration_digest: str | None
    coordinate_frame: str
    units: str
    allow_overlapping_instance_support: bool
    instances: tuple[InstanceEvidence, ...]
    tracks: tuple[TrackEvidence, ...]
    beams: tuple[BeamProof, ...]
    cells: CellEvidence
    diagnostics: ProductDiagnostics
    model_source_revision: str | None = None
    model_weights_sha256: str | None = None
    model_class_map_version: str | None = None


@dataclass(frozen=True)
class ProductReceipt:
    schema_version: int
    run_id: str
    sequence_id: str
    frame_id: int
    result_digest: str | None
    receipt_monotonic_ns: int
    validation_duration_ns: int
    status: ReceiptStatus
    error_code: str | None
    stage: Literal["diagnostic", "semantic", "complete"]


def source_scan_digest(frame: ScanFrame) -> str:
    """Hash the input identity and buffers without consulting oracle annotations."""
    digest = hashlib.sha256()
    digest.update(frame.sequence.encode("utf-8"))
    digest.update(frame.frame_id.to_bytes(8, "little", signed=False))
    digest.update(np.float64(frame.timestamp_s).tobytes())
    digest.update(frame.points_sensor.tobytes(order="C"))
    digest.update(frame.point_ids.tobytes(order="C"))
    digest.update(frame.map_from_sensor.tobytes(order="C"))
    return digest.hexdigest()


def _canonical(value: object) -> object:
    if isinstance(value, np.ndarray):
        if value.dtype.byteorder not in ("<", "=", "|"):
            raise ValueError("array byte order must be native little endian")
        if not value.flags.c_contiguous:
            raise ValueError("arrays must be C contiguous")
        return {
            "dtype": value.dtype.str.replace(">", "<").replace("=", "<"),
            "shape": list(value.shape),
            "hex": value.tobytes(order="C").hex(),
        }
    if isinstance(value, ProductFrameResult) and value.schema_version == SCHEMA_VERSION:
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in fields(value)
            if field.name
            not in ("model_source_revision", "model_weights_sha256", "model_class_map_version")
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, IntEnum):
        return int(value)
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite scalar cannot be digested")
    return value


def canonical_result_digest(result: ProductFrameResult) -> str:
    """SHA-256 of canonical UTF-8 JSON, sorted keys, compact separators, array bytes as hex."""
    encoded = json.dumps(
        _canonical(result),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: str | None) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def diagnostic_product_result(
    frame: ScanFrame,
    result: FrameResult,
    *,
    run_id: str,
    code_revision: str,
    backend: Literal["cpu", "cuda"],
    cell_sizes_cm: tuple[int, ...],
    scheduled_arrival_ns: int | None = None,
) -> ProductFrameResult:
    """Adapt the existing single-frame path without promoting geometry into perception."""
    count = result.accounting.accepted_points
    cells = result.snapshot
    cell_count = len(cells.level)
    timestamp_ns = round(frame.timestamp_s * 1_000_000_000)
    return ProductFrameResult(
        schema_version=SCHEMA_VERSION,
        stage="diagnostic",
        run_id=run_id,
        sequence_id=frame.sequence,
        frame_id=frame.frame_id,
        scan_timestamp_ns=timestamp_ns,
        scheduled_arrival_ns=scheduled_arrival_ns,
        source_scan_digest=source_scan_digest(frame),
        config_digest=cells.config_digest,
        code_revision=code_revision,
        backend=backend,
        checkpoint_sha256=None,
        accounting=result.accounting,
        point_ids=result.observations.point_ids,
        semantic_id=immutable(np.zeros(count, dtype=np.uint8)),
        semantic_confidence=immutable(np.zeros(count, dtype=np.float64)),
        semantic_support=immutable(np.zeros(count, dtype=np.uint8)),
        semantic_unknown_reason=immutable(np.full(count, UnknownReason.NO_MODEL, dtype=np.uint8)),
        motion_state=immutable(np.zeros(count, dtype=np.uint8)),
        motion_confidence=immutable(np.zeros(count, dtype=np.float64)),
        pose_map_from_sensor=frame.map_from_sensor,
        pose_source=frame.pose_source.value,
        pose_quality="unverified",
        calibration_id=None,
        calibration_digest=None,
        coordinate_frame=COORDINATE_FRAME,
        units=UNITS,
        allow_overlapping_instance_support=False,
        instances=(),
        tracks=(),
        beams=(),
        cells=CellEvidence(
            cell_sizes_cm=cell_sizes_cm,
            level=cells.level,
            indices=cells.indices,
            occupancy=immutable(
                np.where(cells.ambiguous, Occupancy.AMBIGUOUS, Occupancy.UNKNOWN).astype(np.uint8)
            ),
            semantic_id=immutable(np.zeros(cell_count, dtype=np.uint8)),
            semantic_support=immutable(np.zeros(cell_count, dtype=np.int64)),
            last_observed_ns=immutable(np.full(cell_count, timestamp_ns, dtype=np.int64)),
            source=immutable(np.full(cell_count, EvidenceSource.CURRENT_SCAN, dtype=np.uint8)),
            ray_support=immutable(np.zeros(cell_count, dtype=np.int64)),
            obstacle_support=immutable(np.zeros(cell_count, dtype=np.int64)),
            uncertainty=immutable(np.full(cell_count, -1.0, dtype=np.float64)),
            conflict=cells.ambiguous,
            free_beam_id=immutable(np.full(cell_count, -1, dtype=np.int64)),
        ),
        diagnostics=ProductDiagnostics(
            load_ms=None,
            ground_ms=result.timings.ground_ms,
            model_ms=None,
            detector_ms=None,
            association_ms=None,
            visibility_ms=None,
            fusion_ms=None,
            transfer_ms=None,
            queue_depth=0,
            queue_age_ms=0.0,
            dropped_scans=0,
            invalid_scans=0,
            map_cells=cell_count,
            track_count=0,
            process_rss_bytes=None,
            device_memory_bytes=None,
            device_memory_status="unavailable",
        ),
    )


def semantic_product_result(
    frame: ScanFrame,
    result: FrameResult,
    *,
    run_id: str,
    code_revision: str,
    checkpoint_sha256: str,
    weights_sha256: str,
    cell_sizes_cm: tuple[int, ...],
    scheduled_arrival_ns: int | None = None,
) -> ProductFrameResult:
    """Publish semantic evidence without temporal, object or free-space claims."""
    if result.snapshot.mode.value != "learned":
        raise ValueError("semantic product result requires learned mapping mode")
    baseline = diagnostic_product_result(
        frame,
        result,
        run_id=run_id,
        code_revision=code_revision,
        backend="cpu",
        cell_sizes_cm=cell_sizes_cm,
        scheduled_arrival_ns=scheduled_arrival_ns,
    )
    cells = result.snapshot
    cell_support = np.take_along_axis(
        cells.semantic_evidence,
        cells.semantic[:, None],
        axis=1,
    ).reshape(-1)
    semantic = result.observations.semantic
    return replace(
        baseline,
        schema_version=SEMANTIC_SCHEMA_VERSION,
        stage="semantic",
        checkpoint_sha256=checkpoint_sha256,
        semantic_id=semantic,
        semantic_confidence=result.observations.semantic_confidence,
        semantic_support=immutable((semantic != 0).astype(np.uint8)),
        semantic_unknown_reason=result.observations.semantic_unknown_reason,
        cells=replace(
            baseline.cells,
            semantic_id=cells.semantic,
            semantic_support=immutable(cell_support.astype(np.int64)),
        ),
        diagnostics=replace(baseline.diagnostics, model_ms=result.timings.model_ms),
        model_source_revision=FRNET_REVISION,
        model_weights_sha256=weights_sha256,
        model_class_map_version=FRNET_CLASS_MAP_VERSION,
    )


class InProcessProductEvaluator:
    """Validate actual buffers and return an ordered receipt after all checks."""

    def __init__(self) -> None:
        self._sequence: str | None = None
        self._last_frame = -1
        self._last_timestamp = -1
        self._track_births: dict[int, int] = {}

    def receive(self, frame: ScanFrame, result: ProductFrameResult) -> ProductReceipt:
        started_ns = monotonic_ns()
        try:
            self._validate(frame, result)
            digest = canonical_result_digest(result)
        except ValueError as exc:
            completed_ns = monotonic_ns()
            return ProductReceipt(
                result.schema_version,
                result.run_id,
                result.sequence_id,
                result.frame_id,
                None,
                completed_ns,
                completed_ns - started_ns,
                ReceiptStatus.REJECTED,
                str(exc),
                result.stage,
            )
        self._sequence = result.sequence_id
        self._last_frame = result.frame_id
        self._last_timestamp = result.scan_timestamp_ns
        self._track_births.update({track.track_id: track.birth_ns for track in result.tracks})
        completed_ns = monotonic_ns()
        return ProductReceipt(
            result.schema_version,
            result.run_id,
            result.sequence_id,
            result.frame_id,
            digest,
            completed_ns,
            completed_ns - started_ns,
            ReceiptStatus.ACCEPTED,
            None,
            result.stage,
        )

    def _validate(self, frame: ScanFrame, result: ProductFrameResult) -> None:
        if type(result.schema_version) is not int or result.schema_version not in (
            SCHEMA_VERSION,
            SEMANTIC_SCHEMA_VERSION,
        ):
            raise ValueError("unsupported-schema")
        if result.stage not in ("diagnostic", "semantic", "complete"):
            raise ValueError("invalid-stage")
        if result.stage == "semantic" and result.schema_version != SEMANTIC_SCHEMA_VERSION:
            raise ValueError("unsupported-schema")
        if result.stage != "semantic" and result.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported-schema")
        if (
            not isinstance(result.run_id, str)
            or not result.run_id
            or not isinstance(result.sequence_id, str)
            or not result.sequence_id
            or not _is_sha256(result.code_revision)
        ):
            raise ValueError("missing-provenance")
        if (
            type(result.frame_id) is not int
            or type(result.scan_timestamp_ns) is not int
            or result.backend not in ("cpu", "cuda")
            or type(result.allow_overlapping_instance_support) is not bool
        ):
            raise ValueError("invalid-result-type")
        if (
            result.sequence_id != frame.sequence
            or result.frame_id != frame.frame_id
            or result.scan_timestamp_ns != round(frame.timestamp_s * 1_000_000_000)
            or result.source_scan_digest != source_scan_digest(frame)
        ):
            raise ValueError("input-identity-mismatch")
        if self._sequence is not None and result.sequence_id != self._sequence:
            raise ValueError("sequence-owner-mismatch")
        if result.frame_id <= self._last_frame or result.scan_timestamp_ns <= self._last_timestamp:
            raise ValueError("nonmonotonic-frame")
        if result.scheduled_arrival_ns is not None and (
            type(result.scheduled_arrival_ns) is not int or result.scheduled_arrival_ns < 0
        ):
            raise ValueError("invalid-arrival")
        if result.accounting.input_points != len(frame.point_ids):
            raise ValueError("input-count-mismatch")
        if result.stage == "complete" and result.accounting.input_points > RELEASE_POINT_CAP:
            raise ValueError("above-release-point-cap")
        if (
            not _is_sha256(result.config_digest)
            or result.coordinate_frame != COORDINATE_FRAME
            or result.units != UNITS
        ):
            raise ValueError("invalid-coordinate-contract")
        if result.pose_source != frame.pose_source.value or not np.array_equal(
            result.pose_map_from_sensor, frame.map_from_sensor
        ):
            raise ValueError("pose-mismatch")
        if result.pose_quality not in ("unverified", "verified", "degraded"):
            raise ValueError("pose-quality")
        if result.stage == "complete" and (
            not _is_sha256(result.checkpoint_sha256)
            or not isinstance(result.calibration_id, str)
            or not result.calibration_id
            or not _is_sha256(result.calibration_digest)
        ):
            raise ValueError("incomplete-provenance")
        if result.stage == "diagnostic" and result.checkpoint_sha256 is not None:
            raise ValueError("diagnostic-checkpoint")
        if result.stage == "semantic" and (
            not _is_sha256(result.checkpoint_sha256)
            or not _is_sha256(result.model_weights_sha256)
            or result.model_source_revision != FRNET_REVISION
            or result.model_class_map_version != FRNET_CLASS_MAP_VERSION
            or result.diagnostics.model_ms is None
        ):
            raise ValueError("semantic-provenance")
        if result.stage != "semantic" and any(
            value is not None
            for value in (
                result.model_source_revision,
                result.model_weights_sha256,
                result.model_class_map_version,
            )
        ):
            raise ValueError("unexpected-model-provenance")
        _validate_arrays(result)
        _validate_points(frame, result)
        _validate_objects(result, self._track_births)
        _validate_cells(frame, result)
        _validate_diagnostics(result.diagnostics, result)


def _validate_arrays(value: object) -> None:
    if isinstance(value, np.ndarray):
        owner: object = value
        while isinstance(owner, np.ndarray) and owner.base is not None:
            if owner.flags.writeable:
                raise ValueError("unsealed-array")
            owner = owner.base
        if value.flags.writeable or not isinstance(owner, bytes):
            raise ValueError("unsealed-array")
        if not value.flags.c_contiguous or value.dtype.byteorder not in ("<", "=", "|"):
            raise ValueError("noncanonical-array")
    elif is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            _validate_arrays(getattr(value, field.name))
    elif isinstance(value, tuple):
        for item in value:
            _validate_arrays(item)


def _validate_points(frame: ScanFrame, result: ProductFrameResult) -> None:
    count = result.accounting.accepted_points
    specs = (
        (result.point_ids, np.int64),
        (result.semantic_id, np.uint8),
        (result.semantic_confidence, np.float64),
        (result.semantic_support, np.uint8),
        (result.semantic_unknown_reason, np.uint8),
        (result.motion_state, np.uint8),
        (result.motion_confidence, np.float64),
    )
    if any(values.shape != (count,) or values.dtype != dtype for values, dtype in specs):
        raise ValueError("point-shape-dtype")
    input_positions = {int(point_id): index for index, point_id in enumerate(frame.point_ids)}
    positions = [input_positions.get(int(point_id), -1) for point_id in result.point_ids]
    if any(index < 0 for index in positions) or any(
        later <= earlier for earlier, later in zip(positions, positions[1:], strict=False)
    ):
        raise ValueError("point-id-alignment")
    if np.any(result.semantic_id > 19) or np.any(result.motion_state > 2):
        raise ValueError("point-class-range")
    for values in (result.semantic_confidence, result.motion_confidence):
        if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
            raise ValueError("point-confidence-range")
    if np.any(result.semantic_support > 2) or np.any(result.semantic_unknown_reason > 2):
        raise ValueError("point-support-range")
    if np.any((result.semantic_id == 0) & (result.semantic_unknown_reason == 0)):
        raise ValueError("unknown-reason-missing")
    if np.any((result.semantic_id != 0) & (result.semantic_support == 0)):
        raise ValueError("unsupported-semantic")
    if result.stage == "diagnostic" and (
        np.any(result.semantic_id) or np.any(result.motion_state) or np.any(result.semantic_support)
    ):
        raise ValueError("diagnostic-claims")
    if result.stage == "semantic" and (
        np.any(result.motion_state)
        or np.any(result.motion_confidence)
        or np.any(result.semantic_support != (result.semantic_id != 0))
    ):
        raise ValueError("semantic-only-claims")


def _validate_objects(result: ProductFrameResult, track_births: dict[int, int]) -> None:
    accepted = set(result.point_ids.tolist())
    instance_ids: set[int] = set()
    used_support: set[int] = set()
    for instance in result.instances:
        if instance.instance_id < 0 or instance.instance_id in instance_ids:
            raise ValueError("instance-id")
        instance_ids.add(instance.instance_id)
        if not set(instance.point_ids) <= accepted or len(set(instance.point_ids)) != len(
            instance.point_ids
        ):
            raise ValueError("instance-support")
        if not result.allow_overlapping_instance_support and used_support.intersection(
            instance.point_ids
        ):
            raise ValueError("instance-support-overlap")
        used_support.update(instance.point_ids)
        if (
            not 0 <= instance.semantic_id <= 19
            or not math.isfinite(instance.semantic_confidence)
            or not 0 <= instance.semantic_confidence <= 1
        ):
            raise ValueError("instance-class")
        if instance.status not in ("observed", "ambiguous") or (
            instance.uncertainty_m is not None
            and (not math.isfinite(instance.uncertainty_m) or instance.uncertainty_m < 0)
        ):
            raise ValueError("instance-status")
        if not 0 <= instance.observed_ns <= result.scan_timestamp_ns:
            raise ValueError("instance-time")
        if any(
            not math.isfinite(value)
            for value in (*instance.center_m, *instance.bounds_min_m, *instance.bounds_max_m)
        ) or any(
            low > center or center > high
            for low, center, high in zip(
                instance.bounds_min_m, instance.center_m, instance.bounds_max_m, strict=True
            )
        ):
            raise ValueError("instance-geometry")
    track_ids: set[int] = set()
    for track in result.tracks:
        if track.track_id < 0 or track.track_id in track_ids:
            raise ValueError("track-id")
        track_ids.add(track.track_id)
        if track.track_id in track_births and track_births[track.track_id] != track.birth_ns:
            raise ValueError("track-id-reused")
        if track.instance_id is not None and track.instance_id not in instance_ids:
            raise ValueError("track-instance")
        if track.lifecycle not in ("tentative", "confirmed", "occluded", "expired"):
            raise ValueError("track-lifecycle")
        if not 0 <= track.birth_ns <= track.last_observed_ns <= result.scan_timestamp_ns:
            raise ValueError("track-time")
        if any(
            frame_id < 0 or frame_id > result.frame_id for frame_id in track.supporting_frame_ids
        ):
            raise ValueError("track-frame-support")
        if track.velocity_world_mps is not None and len(track.velocity_world_mps) != 3:
            raise ValueError("track-velocity")
        if track.velocity_world_mps is None and track.velocity_covariance is not None:
            raise ValueError("track-velocity")
        if track.velocity_world_mps is not None and (
            len(track.supporting_frame_ids) < 2
            or track.velocity_covariance is None
            or len(track.velocity_covariance) != 9
            or not all(
                math.isfinite(v) for v in (*track.velocity_world_mps, *track.velocity_covariance)
            )
        ):
            raise ValueError("track-velocity")
        if (
            not math.isfinite(track.association_confidence)
            or not 0 <= track.association_confidence <= 1
        ):
            raise ValueError("track-confidence")
    if result.stage in ("diagnostic", "semantic") and (
        result.instances or result.tracks or result.beams
    ):
        raise ValueError("partial-result-claims")


def _validate_cells(frame: ScanFrame, result: ProductFrameResult) -> None:
    cells = result.cells
    n = len(cells.level)
    specs = (
        (cells.level, (n,), np.int64),
        (cells.indices, (n, 2), np.int64),
        (cells.occupancy, (n,), np.uint8),
        (cells.semantic_id, (n,), np.uint8),
        (cells.semantic_support, (n,), np.int64),
        (cells.last_observed_ns, (n,), np.int64),
        (cells.source, (n,), np.uint8),
        (cells.ray_support, (n,), np.int64),
        (cells.obstacle_support, (n,), np.int64),
        (cells.uncertainty, (n,), np.float64),
        (cells.conflict, (n,), np.bool_),
        (cells.free_beam_id, (n,), np.int64),
    )
    if any(values.shape != shape or values.dtype != dtype for values, shape, dtype in specs):
        raise ValueError("cell-shape-dtype")
    sizes = cells.cell_sizes_cm
    if not sizes or sizes[0] != 5 or any(size <= 0 or size % 5 for size in sizes):
        raise ValueError("cell-size")
    if any(larger % smaller for smaller, larger in zip(sizes, sizes[1:], strict=False)):
        raise ValueError("cell-size")
    if np.any(cells.level < 0) or np.any(cells.level >= len(sizes)):
        raise ValueError("cell-level")
    if np.any(cells.occupancy > max(Occupancy)) or np.any(cells.semantic_id > 19):
        raise ValueError("cell-class-range")
    if np.any(cells.semantic_support < 0):
        raise ValueError("cell-semantic-support")
    if (
        np.any(cells.source > max(EvidenceSource))
        or np.any(cells.ray_support < 0)
        or np.any(cells.obstacle_support < 0)
    ):
        raise ValueError("cell-evidence-range")
    if not np.isfinite(cells.uncertainty).all() or np.any(cells.uncertainty < -1):
        raise ValueError("cell-uncertainty")
    if np.any(cells.last_observed_ns < -1) or np.any(
        cells.last_observed_ns > result.scan_timestamp_ns
    ):
        raise ValueError("cell-time")
    keys: set[tuple[int, int, int]] = set()
    for level, xy in zip(cells.level.tolist(), cells.indices.tolist(), strict=True):
        key = (level, xy[0], xy[1])
        if key in keys:
            raise ValueError("cell-overlap")
        keys.add(key)
    for level, x, y in keys:
        for coarser in range(level + 1, len(sizes)):
            ratio = sizes[coarser] // sizes[level]
            if (coarser, x // ratio, y // ratio) in keys:
                raise ValueError("cell-overlap")
    proof_ids = {beam.beam_id for beam in result.beams}
    if len(proof_ids) != len(result.beams):
        raise ValueError("beam-id")
    accepted = set(result.point_ids.tolist())
    point_positions = {int(point_id): index for index, point_id in enumerate(frame.point_ids)}
    for beam in result.beams:
        if (
            beam.beam_id < 0
            or beam.point_id not in accepted
            or not all(math.isfinite(value) for value in (*beam.origin_map_m, *beam.return_map_m))
        ):
            raise ValueError("beam-support")
        if not np.allclose(beam.origin_map_m, frame.map_from_sensor[:3, 3], rtol=0, atol=1e-6):
            raise ValueError("beam-origin-mismatch")
        source_point = frame.points_sensor[point_positions[beam.point_id], :3].astype(np.float64)
        expected_return = (
            frame.map_from_sensor[:3, :3] @ source_point + frame.map_from_sensor[:3, 3]
        )
        if not np.allclose(expected_return, beam.return_map_m, rtol=0, atol=1e-6):
            raise ValueError("beam-return-mismatch")
    beams = {beam.beam_id: beam for beam in result.beams}
    occupied_keys: dict[int, set[tuple[int, int]]] = {}
    if np.any(cells.occupancy == Occupancy.OBSERVED_FREE):
        selected = [point_positions[int(point_id)] for point_id in result.point_ids]
        xyz_sensor = frame.points_sensor[selected, :3].astype(np.float64)
        xyz_map = xyz_sensor @ frame.map_from_sensor[:3, :3].T + frame.map_from_sensor[:3, 3]
        for level, width_cm in enumerate(sizes):
            xy_index = np.floor(xyz_map[:, :2] / (width_cm / 100)).astype(np.int64)
            occupied_keys[level] = set(map(tuple, xy_index.tolist()))
    for level, xy, occupancy, ray_count, beam_id in zip(
        cells.level,
        cells.indices,
        cells.occupancy,
        cells.ray_support,
        cells.free_beam_id,
        strict=True,
    ):
        if occupancy == Occupancy.OBSERVED_FREE:
            if ray_count < 1 or int(beam_id) not in proof_ids:
                raise ValueError("unsupported-free")
            beam = beams[int(beam_id)]
            width_m = sizes[int(level)] / 100
            low = xy.astype(np.float64) * width_m
            high = low + width_m
            if tuple(xy.tolist()) in occupied_keys[int(level)]:
                raise ValueError("unsupported-free")
            start = np.asarray(beam.origin_map_m[:2])
            return_xy = np.asarray(beam.return_map_m[:2])
            if np.all((return_xy >= low) & (return_xy < high)):
                raise ValueError("unsupported-free")
            delta = return_xy - start
            if not _segment_crosses_open_cell(start, delta, low, high):
                raise ValueError("unsupported-free")
        elif beam_id != -1:
            raise ValueError("unexpected-free-proof")
    if result.stage in ("diagnostic", "semantic") and np.any(
        (cells.occupancy != Occupancy.UNKNOWN) & (cells.occupancy != Occupancy.AMBIGUOUS)
    ):
        raise ValueError("diagnostic-occupancy")


def _segment_crosses_open_cell(
    start: FloatArray, delta: FloatArray, low: FloatArray, high: FloatArray
) -> bool:
    """Require beam travel through the cell interior before its return."""
    enter = 0.0
    exit_ = 1.0
    for axis in range(2):
        if delta[axis] == 0:
            if not low[axis] < start[axis] < high[axis]:
                return False
            continue
        first = (low[axis] - start[axis]) / delta[axis]
        second = (high[axis] - start[axis]) / delta[axis]
        enter = max(enter, min(first, second))
        exit_ = min(exit_, max(first, second))
    return enter < exit_ and enter < 1 and exit_ > 0


def _validate_diagnostics(value: ProductDiagnostics, result: ProductFrameResult) -> None:
    for field in fields(value):
        item = getattr(value, field.name)
        if (
            field.name.endswith("_ms")
            and item is not None
            and (not math.isfinite(item) or item < 0)
        ):
            raise ValueError("invalid-timing")
    if min(value.queue_depth, value.dropped_scans, value.invalid_scans) < 0:
        raise ValueError("invalid-counter")
    if value.map_cells != len(result.cells.level) or value.track_count != len(result.tracks):
        raise ValueError("state-size-mismatch")
    if value.process_rss_bytes is not None and value.process_rss_bytes < 0:
        raise ValueError("invalid-memory")
    if value.device_memory_status not in ("unavailable", "sampled") or (
        value.device_memory_bytes is not None and value.device_memory_bytes < 0
    ):
        raise ValueError("invalid-device-memory")
    if value.device_memory_status == "sampled" and value.device_memory_bytes is None:
        raise ValueError("missing-device-sample")
