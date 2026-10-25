"""Versioned product-result contracts and synchronous same-process evaluator.

The current engine can populate diagnostic and staged learned results with
explicit evidence. The G0 adapter may set stage to ``complete`` only after the
candidate, tracking, visibility and temporal payloads are present.
"""

import hashlib
import json
import math
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import IntEnum, StrEnum
from functools import lru_cache
from json.encoder import encode_basestring_ascii
from time import monotonic_ns
from typing import Any, Literal

import numpy as np
from numpy.typing import NDArray

from drishti.arrays import BoolArray, ByteArray, FloatArray, IntArray, immutable
from drishti.contracts import Accounting, ScanFrame
from drishti.learned import FRNET_CLASS_MAP_VERSION, FRNET_REVISION
from drishti.obstacles import InstanceEvidence
from drishti.pipeline import FrameResult
from drishti.release_contract import (
    D005_VERSION,
    DEFAULT_D005,
    G0_CONTRACT_VERSION,
    ResourceLimits,
)
from drishti.temporal import FusedMapSummary, FusedOccupancy, TerrainState
from drishti.tracking import (
    ASSOCIATION_METHOD,
    MAX_TRACK_ID,
    MAX_TRACKS,
    TrackingSummary,
    eligible,
)
from drishti.tracking import (
    TrackEvidence as TrackEvidence,
)
from drishti.visibility import (
    GROUND_SEMANTIC_IDS,
    MAX_FREE_CELLS,
    VISIBILITY_METHOD,
    VisibilitySettings,
    VisibilitySummary,
    corridor_start_fraction,
    pack_cells,
)
from drishti.visibility import (
    Occupancy as Occupancy,
)

SCHEMA_VERSION = 1
SEMANTIC_SCHEMA_VERSION = 2
CANDIDATE_SCHEMA_VERSION = 3
TRACKING_SCHEMA_VERSION = 4
VISIBILITY_SCHEMA_VERSION = 5
COMPLETE_SCHEMA_VERSION = 6
RELEASE_POINT_CAP = 130_000
COORDINATE_FRAME = "map-x-forward-y-left-z-up"
UNITS = "metre-nanosecond"
TRACKED_STAGES = ("tracking", "visibility", "complete")
LEARNED_STAGES = ("semantic", "candidate", "tracking", "visibility", "complete")
type Stage = Literal["diagnostic", "semantic", "candidate", "tracking", "visibility", "complete"]


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
class BeamProof:
    beam_id: int
    point_id: int
    origin_map_m: tuple[float, float, float]
    return_map_m: tuple[float, float, float]


@dataclass(frozen=True)
class BeamTable:
    """Schema-5 columnar beam proofs; every beam starts at the one frame sensor origin."""

    beam_id: IntArray
    point_id: IntArray
    origin_map_m: FloatArray
    return_map_m: FloatArray


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
class FusedCellEvidence:
    """Version-6 fused cells copied from the sequence-owned temporal map view."""

    cell_sizes_cm: tuple[int, ...]
    level: IntArray
    indices: IntArray
    centers_xy_m: FloatArray
    size_m: FloatArray
    ground_height_m: FloatArray
    ground_sigma_m: FloatArray
    ground_valid: BoolArray
    occupancy: ByteArray
    terrain: ByteArray
    flags: ByteArray
    semantic_id: ByteArray
    obstacle_low_m: FloatArray
    obstacle_high_m: FloatArray
    last_seen_ns: IntArray
    observations: IntArray
    summary: FusedMapSummary


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
    swap_delta_bytes: int | None = None
    receipt_bytes: int | None = None
    audit_bytes: int | None = None
    disk_free_bytes: int | None = None


@dataclass(frozen=True)
class ProductFrameResult:
    schema_version: int
    stage: Stage
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
    tracking_summary: TrackingSummary | None = None
    visibility_summary: VisibilitySummary | None = None
    beam_table: BeamTable | None = None
    fused: FusedCellEvidence | None = None
    complete_contract_version: str | None = None
    d005_version: str | None = None
    resource_limits: ResourceLimits | None = None


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
    stage: Stage
    deep_audit: bool = True


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
    if isinstance(value, ProductFrameResult):
        # Fields added by later schemas stay out of earlier digests, preserving them exactly.
        excluded = _result_excluded_fields(value)
        payload: dict[str, object] = {}
        for field in fields(value):
            if field.name in excluded:
                continue
            current = getattr(value, field.name)
            payload[field.name] = (
                _canonical_diagnostics(current, include_resource_fields=False)
                if field.name == "diagnostics" and value.schema_version < COMPLETE_SCHEMA_VERSION
                else _canonical(current)
            )
        return payload
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        # Fast path for flat int/str tuples (support IDs); canonical JSON is identical.
        if all(type(item) is int or type(item) is str for item in value):
            return list(value)
        return [_canonical(item) for item in value]
    if isinstance(value, IntEnum):
        return int(value)
    if isinstance(value, StrEnum):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite scalar cannot be digested")
    return value


@lru_cache(maxsize=32)
def _raw_fields(cls: type[Any]) -> tuple[tuple[str, bytes], ...]:
    """Cache only immutable field names, never frame values or array buffers."""
    return tuple((field.name, f"{field.name}=".encode()) for field in fields(cls))


def _result_excluded_fields(value: ProductFrameResult) -> set[str]:
    excluded: set[str] = set()
    if value.schema_version < COMPLETE_SCHEMA_VERSION:
        excluded.update(("fused", "complete_contract_version", "d005_version", "resource_limits"))
    if value.schema_version < VISIBILITY_SCHEMA_VERSION:
        excluded.update(("visibility_summary", "beam_table"))
    if value.schema_version < TRACKING_SCHEMA_VERSION:
        excluded.add("tracking_summary")
    if value.schema_version == SCHEMA_VERSION:
        excluded.update(
            ("model_source_revision", "model_weights_sha256", "model_class_map_version")
        )
    return excluded


def _canonical_diagnostics(value: ProductDiagnostics, *, include_resource_fields: bool) -> object:
    excluded: set[str] = set()
    if not include_resource_fields:
        excluded.update(("swap_delta_bytes", "receipt_bytes", "audit_bytes", "disk_free_bytes"))
    return {
        field.name: _canonical(getattr(value, field.name))
        for field in fields(value)
        if field.name not in excluded
    }


def _feed_raw(digest: Any, value: object, *, include_resource_fields: bool = True) -> None:
    """Typed, length-prefixed stream: array headers then raw bytes, no hex or JSON bodies."""
    kind = type(value)
    if kind is int:
        digest.update(f"S{value};".encode())
    elif isinstance(value, float) and kind is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite scalar cannot be digested")
        digest.update(f"S{value!r};".encode())
    elif isinstance(value, str) and kind is str:
        digest.update(b"S" + encode_basestring_ascii(value).encode() + b";")
    elif value is None:
        digest.update(b"Snull;")
    elif kind is bool:
        digest.update(b"Strue;" if value else b"Sfalse;")
    elif isinstance(value, ProductFrameResult):
        excluded = _result_excluded_fields(value)
        digest.update(f"D{type(value).__name__}{{".encode())
        for name, prefix in _raw_fields(type(value)):
            if name in excluded:
                continue
            digest.update(prefix)
            _feed_raw(
                digest,
                getattr(value, name),
                include_resource_fields=value.schema_version >= COMPLETE_SCHEMA_VERSION,
            )
        digest.update(b"}")
    elif isinstance(value, ProductDiagnostics):
        digest.update(f"D{type(value).__name__}{{".encode())
        for name, prefix in _raw_fields(type(value)):
            if not include_resource_fields and name in {
                "swap_delta_bytes",
                "receipt_bytes",
                "audit_bytes",
                "disk_free_bytes",
            }:
                continue
            digest.update(prefix)
            _feed_raw(
                digest,
                getattr(value, name),
                include_resource_fields=include_resource_fields,
            )
        digest.update(b"}")
    elif isinstance(value, np.ndarray):
        if value.dtype.byteorder not in ("<", "=", "|"):
            raise ValueError("array byte order must be native little endian")
        if not value.flags.c_contiguous:
            raise ValueError("arrays must be C contiguous")
        header = f"A{value.dtype.str.replace('=', '<')}{list(value.shape)}:{value.nbytes};"
        digest.update(header.encode())
        if value.size:
            digest.update(memoryview(value.reshape(-1)).cast("B"))
    elif is_dataclass(value) and not isinstance(value, type):
        digest.update(f"D{type(value).__name__}{{".encode())
        for name, prefix in _raw_fields(type(value)):
            digest.update(prefix)
            _feed_raw(
                digest,
                getattr(value, name),
                include_resource_fields=include_resource_fields,
            )
        digest.update(b"}")
    elif isinstance(value, tuple):
        digest.update(f"T{len(value)}[".encode())
        if value and all(type(item) is int for item in value):
            digest.update(b"i")
            digest.update(np.asarray(value, dtype=np.int64).tobytes())
        else:
            for item in value:
                _feed_raw(digest, item, include_resource_fields=include_resource_fields)
        digest.update(b"]")
    else:
        scalar = value if type(value) in (int, str, bool) or value is None else _canonical(value)
        digest.update(b"S")
        digest.update(json.dumps(scalar, allow_nan=False, sort_keys=True).encode())
        digest.update(b";")


def canonical_result_digest(result: ProductFrameResult) -> str:
    """SHA-256 identifying a result.

    Schemas 1 to 4 keep the frozen canonical form: UTF-8 JSON, sorted keys, compact
    separators, array bytes as hex. Schema 5 hashes a typed, length-prefixed stream of the
    raw array bytes in field order (``drishti-raw-digest-v1``), which is much cheaper.
    """
    if result.schema_version >= VISIBILITY_SCHEMA_VERSION:
        raw = hashlib.sha256(b"drishti-raw-digest-v1\n")
        _feed_raw(raw, result)
        return raw.hexdigest()
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
    backend: Literal["cpu", "cuda"] = "cpu",
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
        backend=backend,
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


def candidate_product_result(
    frame: ScanFrame,
    result: FrameResult,
    *,
    run_id: str,
    code_revision: str,
    checkpoint_sha256: str,
    weights_sha256: str,
    cell_sizes_cm: tuple[int, ...],
    backend: Literal["cpu", "cuda"] = "cpu",
    scheduled_arrival_ns: int | None = None,
) -> ProductFrameResult:
    """Publish observed candidate support without tracks or occupancy claims."""
    if result.timings.detector_ms is None:
        raise ValueError("candidate product result requires detector timing")
    semantic = semantic_product_result(
        frame,
        result,
        run_id=run_id,
        code_revision=code_revision,
        checkpoint_sha256=checkpoint_sha256,
        weights_sha256=weights_sha256,
        cell_sizes_cm=cell_sizes_cm,
        backend=backend,
        scheduled_arrival_ns=scheduled_arrival_ns,
    )
    return replace(
        semantic,
        schema_version=CANDIDATE_SCHEMA_VERSION,
        stage="candidate",
        instances=result.instances,
        diagnostics=replace(semantic.diagnostics, detector_ms=result.timings.detector_ms),
    )


def tracking_product_result(
    frame: ScanFrame,
    result: FrameResult,
    *,
    run_id: str,
    code_revision: str,
    checkpoint_sha256: str,
    weights_sha256: str,
    cell_sizes_cm: tuple[int, ...],
    backend: Literal["cpu", "cuda"] = "cpu",
    scheduled_arrival_ns: int | None = None,
) -> ProductFrameResult:
    """Publish bounded association evidence with explicitly unknown metric motion."""
    if result.tracking is None or result.timings.association_ms is None:
        raise ValueError("tracking product result requires a prepared tracker transition")
    baseline = candidate_product_result(
        frame,
        result,
        run_id=run_id,
        code_revision=code_revision,
        checkpoint_sha256=checkpoint_sha256,
        weights_sha256=weights_sha256,
        cell_sizes_cm=cell_sizes_cm,
        backend=backend,
        scheduled_arrival_ns=scheduled_arrival_ns,
    )
    return replace(
        baseline,
        schema_version=TRACKING_SCHEMA_VERSION,
        stage="tracking",
        tracks=result.tracking.tracks,
        tracking_summary=result.tracking.summary,
        diagnostics=replace(
            baseline.diagnostics,
            association_ms=result.timings.association_ms,
            track_count=len(result.tracking.tracks),
        ),
    )


def visibility_product_result(
    frame: ScanFrame,
    result: FrameResult,
    *,
    run_id: str,
    code_revision: str,
    checkpoint_sha256: str,
    weights_sha256: str,
    cell_sizes_cm: tuple[int, ...],
    backend: Literal["cpu", "cuda"] = "cpu",
    scheduled_arrival_ns: int | None = None,
) -> ProductFrameResult:
    """Publish current-scan occupied, observed-free and unknown evidence with tracks."""
    visibility = result.visibility
    if visibility is None or result.timings.visibility_ms is None:
        raise ValueError("visibility product result requires current-scan visibility evidence")
    baseline = tracking_product_result(
        frame,
        result,
        run_id=run_id,
        code_revision=code_revision,
        checkpoint_sha256=checkpoint_sha256,
        weights_sha256=weights_sha256,
        cell_sizes_cm=cell_sizes_cm,
        backend=backend,
        scheduled_arrival_ns=scheduled_arrival_ns,
    )
    cells = baseline.cells
    free = len(visibility.free_level)
    total = len(cells.level) + free
    observed = result.observations
    beam_ids = np.unique(visibility.free_beam_point_id)
    by_id = np.argsort(observed.point_ids, kind="stable")
    rows = by_id[np.searchsorted(observed.point_ids[by_id], beam_ids)]
    table = BeamTable(
        beam_id=immutable(beam_ids.astype(np.int64)),
        point_id=immutable(beam_ids.astype(np.int64)),
        origin_map_m=immutable(np.asarray(frame.map_from_sensor[:3, 3], dtype=np.float64)),
        return_map_m=immutable(np.ascontiguousarray(observed.points_map_m[rows])),
    )
    timestamp_ns = baseline.scan_timestamp_ns
    return replace(
        baseline,
        schema_version=VISIBILITY_SCHEMA_VERSION,
        stage="visibility",
        beam_table=table,
        cells=replace(
            cells,
            level=_extend(cells.level, visibility.free_level),
            indices=immutable(np.concatenate((cells.indices, visibility.free_indices))),
            occupancy=_extend(
                visibility.occupancy, np.full(free, Occupancy.OBSERVED_FREE, dtype=np.uint8)
            ),
            semantic_id=_extend(cells.semantic_id, np.zeros(free, dtype=np.uint8)),
            semantic_support=_extend(cells.semantic_support, np.zeros(free, dtype=np.int64)),
            last_observed_ns=immutable(np.full(total, timestamp_ns, dtype=np.int64)),
            source=immutable(np.full(total, EvidenceSource.CURRENT_SCAN, dtype=np.uint8)),
            ray_support=_extend(cells.ray_support, visibility.free_ray_support),
            obstacle_support=_extend(visibility.obstacle_support, np.zeros(free, dtype=np.int64)),
            uncertainty=immutable(np.full(total, -1.0, dtype=np.float64)),
            conflict=_extend(cells.conflict, np.zeros(free, dtype=np.bool_)),
            free_beam_id=_extend(cells.free_beam_id, visibility.free_beam_point_id),
        ),
        diagnostics=replace(
            baseline.diagnostics,
            visibility_ms=result.timings.visibility_ms,
            map_cells=total,
        ),
        visibility_summary=visibility.summary,
    )


def complete_product_result(
    frame: ScanFrame,
    result: FrameResult,
    *,
    run_id: str,
    code_revision: str,
    checkpoint_sha256: str,
    weights_sha256: str,
    cell_sizes_cm: tuple[int, ...],
    calibration_id: str,
    calibration_digest: str,
    backend: Literal["cpu", "cuda"] = "cpu",
    pose_quality: Literal["verified", "degraded"] = "verified",
    scheduled_arrival_ns: int | None = None,
    resource_limits: ResourceLimits | None = None,
    process_rss_bytes: int | None = None,
    device_memory_bytes: int | None = None,
    device_memory_status: Literal["unavailable", "sampled"] = "unavailable",
    swap_delta_bytes: int | None = None,
    receipt_bytes: int | None = None,
    audit_bytes: int | None = None,
    disk_free_bytes: int | None = None,
) -> ProductFrameResult:
    """Build the frozen G0 result from the shared complete execution path.

    The producer must have executed candidates, tracking, current-scan
    visibility and temporal fusion. This function only adapts those already
    computed immutable values; it does not manufacture missing evidence.
    """
    if result.fused is None:
        raise ValueError("complete product result requires temporal fusion")
    if result.visibility is None or result.tracking is None:
        raise ValueError("complete product result requires visibility and tracking")
    if result.timings.temporal_ms is None:
        raise ValueError("complete product result requires fusion timing")
    baseline = visibility_product_result(
        frame,
        result,
        run_id=run_id,
        code_revision=code_revision,
        checkpoint_sha256=checkpoint_sha256,
        weights_sha256=weights_sha256,
        cell_sizes_cm=cell_sizes_cm,
        backend=backend,
        scheduled_arrival_ns=scheduled_arrival_ns,
    )
    fused = result.fused
    diagnostics = replace(
        baseline.diagnostics,
        fusion_ms=result.timings.temporal_ms,
        map_cells=len(fused.level),
        process_rss_bytes=process_rss_bytes,
        device_memory_bytes=device_memory_bytes,
        device_memory_status=device_memory_status,
        swap_delta_bytes=swap_delta_bytes,
        receipt_bytes=receipt_bytes,
        audit_bytes=audit_bytes,
        disk_free_bytes=disk_free_bytes,
    )
    return replace(
        baseline,
        schema_version=COMPLETE_SCHEMA_VERSION,
        stage="complete",
        pose_quality=pose_quality,
        calibration_id=calibration_id,
        calibration_digest=calibration_digest,
        fused=FusedCellEvidence(
            cell_sizes_cm=cell_sizes_cm,
            level=fused.level,
            indices=fused.indices,
            centers_xy_m=fused.centers_xy_m,
            size_m=fused.size_m,
            ground_height_m=fused.ground_height_m,
            ground_sigma_m=fused.ground_sigma_m,
            ground_valid=fused.ground_valid,
            occupancy=fused.occupancy,
            terrain=fused.terrain,
            flags=fused.flags,
            semantic_id=fused.semantic,
            obstacle_low_m=fused.obstacle_low_m,
            obstacle_high_m=fused.obstacle_high_m,
            last_seen_ns=fused.last_seen_ns,
            observations=fused.observations,
            summary=fused.summary,
        ),
        complete_contract_version=G0_CONTRACT_VERSION,
        d005_version=D005_VERSION,
        resource_limits=DEFAULT_D005.resources if resource_limits is None else resource_limits,
        diagnostics=diagnostics,
    )


def _extend[Scalar: np.generic](
    current: NDArray[Scalar], added: NDArray[np.generic]
) -> NDArray[Scalar]:
    return immutable(np.concatenate((current, added.astype(current.dtype))))


class InProcessProductEvaluator:
    """Validate actual buffers and return an ordered receipt after all checks.

    Every receipt runs the light contract checks: provenance, sealed arrays, shapes and
    ranges, point alignment, cell nonoverlap, tracking lifecycle, visibility summary and
    proof references. ``audit_every`` sets how often the deep geometric re-verification
    also runs (candidate bounds from raw points, beam and corridor geometry, conflict
    margin, point-to-cell reconstruction): 1 audits every accepted frame, N every N-th
    starting with the first, 0 never. Receipts record whether they were deeply audited.
    """

    def __init__(self, *, audit_every: int = 1) -> None:
        if type(audit_every) is not int or audit_every < 0:
            raise ValueError("audit_every must be a nonnegative integer")
        self.audit_every = audit_every
        self._accepted = 0
        self._sequence: str | None = None
        self._last_frame = -1
        self._last_timestamp = -1
        self._track_births: dict[int, int] = {}
        self._tracking_previous: dict[int, TrackEvidence] = {}
        self._tracking_misses: dict[int, int] = {}
        self._tracking_classes: dict[int, int] = {}
        self._tracking_high_id = 0
        self._tracking_capacity: int | None = None
        self._last_stage: str | None = None

    def receive(self, frame: ScanFrame, result: ProductFrameResult) -> ProductReceipt:
        started_ns = monotonic_ns()
        deep = self.audit_every > 0 and self._accepted % self.audit_every == 0
        try:
            self._validate(frame, result, deep)
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
                deep,
            )
        if result.stage in TRACKED_STAGES:
            instance_classes = {item.instance_id: item.semantic_id for item in result.instances}
            self._tracking_classes = {
                track.track_id: (
                    instance_classes[track.instance_id]
                    if track.instance_id is not None
                    else self._tracking_classes[track.track_id]
                )
                for track in result.tracks
                if track.lifecycle != "expired"
            }
            self._tracking_misses = {
                track.track_id: (
                    self._tracking_misses.get(track.track_id, 0) + 1
                    if track.lifecycle == "occluded"
                    else 0
                )
                for track in result.tracks
                if track.lifecycle != "expired"
            }
            self._tracking_previous = {
                track.track_id: track for track in result.tracks if track.lifecycle != "expired"
            }
            self._tracking_high_id = max(
                self._tracking_high_id, max((t.track_id for t in result.tracks), default=0)
            )
            assert result.tracking_summary is not None
            self._tracking_capacity = result.tracking_summary.capacity
            self._track_births = {
                track.track_id: track.birth_ns for track in self._tracking_previous.values()
            }
        self._last_stage = result.stage
        self._sequence = result.sequence_id
        self._last_frame = result.frame_id
        self._last_timestamp = result.scan_timestamp_ns
        if result.stage not in TRACKED_STAGES:
            self._track_births.update({track.track_id: track.birth_ns for track in result.tracks})
        self._accepted += 1
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
            deep,
        )

    def _validate(self, frame: ScanFrame, result: ProductFrameResult, deep: bool = True) -> None:
        if type(result.schema_version) is not int or result.schema_version not in (
            SCHEMA_VERSION,
            SEMANTIC_SCHEMA_VERSION,
            CANDIDATE_SCHEMA_VERSION,
            TRACKING_SCHEMA_VERSION,
            VISIBILITY_SCHEMA_VERSION,
            COMPLETE_SCHEMA_VERSION,
        ):
            raise ValueError("unsupported-schema")
        if result.stage not in (*LEARNED_STAGES, "diagnostic", "complete"):
            raise ValueError("invalid-stage")
        stage_schemas = {
            "diagnostic": SCHEMA_VERSION,
            "semantic": SEMANTIC_SCHEMA_VERSION,
            "candidate": CANDIDATE_SCHEMA_VERSION,
            "tracking": TRACKING_SCHEMA_VERSION,
            "visibility": VISIBILITY_SCHEMA_VERSION,
            "complete": COMPLETE_SCHEMA_VERSION,
        }
        if result.schema_version != stage_schemas[result.stage]:
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
        if result.stage == "complete" and result.pose_quality == "unverified":
            raise ValueError("incomplete-pose-quality")
        if result.stage == "complete" and (
            result.complete_contract_version != G0_CONTRACT_VERSION
            or result.d005_version != D005_VERSION
            or result.resource_limits is None
            or result.fused is None
            or result.tracking_summary is None
            or result.visibility_summary is None
            or result.beam_table is None
        ):
            raise ValueError("incomplete-complete-result")
        if result.stage == "diagnostic" and result.checkpoint_sha256 is not None:
            raise ValueError("diagnostic-checkpoint")
        if result.stage in LEARNED_STAGES and (
            not _is_sha256(result.checkpoint_sha256)
            or not _is_sha256(result.model_weights_sha256)
            or result.model_source_revision != FRNET_REVISION
            or result.model_class_map_version != FRNET_CLASS_MAP_VERSION
            or result.diagnostics.model_ms is None
        ):
            raise ValueError("semantic-provenance")
        if result.stage not in LEARNED_STAGES and any(
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
        _validate_objects(frame, result, self._track_births, deep)
        _validate_cells(frame, result, deep)
        if result.stage == "complete":
            assert result.fused is not None
            assert result.resource_limits is not None
            _validate_fused_cells(result.fused, result)
            _validate_resource_limits(result)
        _validate_diagnostics(result.diagnostics, result)
        if (
            self._last_stage
            and self._last_stage != result.stage
            and (self._last_stage in TRACKED_STAGES or result.stage in TRACKED_STAGES)
        ):
            raise ValueError("tracking-stage-change")
        if result.stage in TRACKED_STAGES:
            self._validate_tracking(result)
        elif result.tracking_summary is not None:
            raise ValueError("unexpected-tracking-summary")
        if result.stage in ("visibility", "complete"):
            _validate_visibility(frame, result, deep)
        elif result.visibility_summary is not None or result.beam_table is not None:
            raise ValueError("unexpected-visibility-summary")

    def _validate_tracking(self, result: ProductFrameResult) -> None:
        summary = result.tracking_summary
        if (
            summary is None
            or summary.method != ASSOCIATION_METHOD
            or type(summary.capacity) is not int
            or not 1 <= summary.capacity <= MAX_TRACKS
            or (self._tracking_capacity is not None and summary.capacity != self._tracking_capacity)
            or result.diagnostics.association_ms is None
            or (result.beams and result.stage not in ("visibility", "complete"))
            or result.allow_overlapping_instance_support
        ):
            raise ValueError("tracking-contract")
        instances = {item.instance_id: item for item in result.instances if eligible(item)}
        if (
            type(summary.eligible_candidates) is not int
            or type(summary.frame_gap) is not int
            or not isinstance(summary.rejected_instance_ids, tuple)
            or any(type(value) is not int for value in summary.rejected_instance_ids)
            or summary.eligible_candidates != len(instances)
            or summary.frame_gap
            != (result.frame_id - self._last_frame - 1 if self._last_frame >= 0 else 0)
            or summary.rejected_instance_ids != tuple(sorted(set(summary.rejected_instance_ids)))
        ):
            raise ValueError("tracking-summary")
        current = {track.track_id: track for track in result.tracks}
        if (
            tuple(current) != tuple(sorted(current))
            or not self._tracking_previous.keys() <= current.keys()
        ):
            raise ValueError("tracking-id-order-or-disappearance")
        assigned: set[int] = set()
        next_id = self._tracking_high_id + 1
        live = 0
        for track in result.tracks:
            if (
                type(track.track_id) is not int
                or type(track.birth_ns) is not int
                or type(track.last_observed_ns) is not int
                or (track.instance_id is not None and type(track.instance_id) is not int)
                or not isinstance(track.supporting_frame_ids, tuple)
                or any(type(value) is not int for value in track.supporting_frame_ids)
                or not 1 <= track.track_id <= MAX_TRACK_ID
                or track.velocity_world_mps is not None
                or track.velocity_covariance is not None
                or not 1 <= len(track.supporting_frame_ids) <= 2
                or tuple(sorted(set(track.supporting_frame_ids))) != track.supporting_frame_ids
            ):
                raise ValueError("tracking-evidence")
            previous = self._tracking_previous.get(track.track_id)
            observed = track.instance_id is not None
            if observed:
                if track.instance_id not in instances or track.instance_id in assigned:
                    raise ValueError("tracking-instance-assignment")
                assigned.add(track.instance_id)
                if (
                    track.last_observed_ns != result.scan_timestamp_ns
                    or instances[track.instance_id].observed_ns != result.scan_timestamp_ns
                    or track.supporting_frame_ids[-1] != result.frame_id
                ):
                    raise ValueError("tracking-observation-time")
            elif track.association_confidence != 0:
                raise ValueError("tracking-missing-confidence")
            if previous is None:
                if (
                    track.track_id != next_id
                    or not observed
                    or track.lifecycle != "tentative"
                    or track.birth_ns != result.scan_timestamp_ns
                    or track.supporting_frame_ids != (result.frame_id,)
                    or track.association_confidence != 0
                ):
                    raise ValueError("tracking-birth-or-reused-id")
                next_id += 1
            else:
                if track.birth_ns != previous.birth_ns:
                    raise ValueError("tracking-birth-changed")
                if observed:
                    assert track.instance_id is not None
                    if (
                        instances[track.instance_id].semantic_id
                        != self._tracking_classes[track.track_id]
                        or result.scan_timestamp_ns - previous.last_observed_ns > 1_000_000_000
                    ):
                        raise ValueError("tracking-class-or-time-gate")
                    if track.lifecycle != "confirmed" or track.supporting_frame_ids != (
                        *previous.supporting_frame_ids[-1:],
                        result.frame_id,
                    ):
                        raise ValueError("tracking-confirmation")
                else:
                    misses = self._tracking_misses[track.track_id] + 1
                    expected = (
                        "expired"
                        if previous.lifecycle == "tentative" or misses >= 3
                        else "occluded"
                    )
                    if (
                        track.lifecycle != expected
                        or track.supporting_frame_ids != previous.supporting_frame_ids
                        or track.last_observed_ns != previous.last_observed_ns
                    ):
                        raise ValueError("tracking-expiry")
            live += track.lifecycle != "expired"
        rejected = set(summary.rejected_instance_ids)
        if (
            live > summary.capacity
            or len(result.tracks) > 2 * summary.capacity
            or rejected & assigned
            or rejected | assigned != instances.keys()
            or (rejected and live != summary.capacity)
        ):
            raise ValueError("tracking-capacity-accounting")


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
        for name, _ in _raw_fields(type(value)):
            item = getattr(value, name)
            if type(item) not in (int, float, str, bool) and item is not None:
                _validate_arrays(item)
    elif isinstance(value, tuple):
        for item in value:
            # Plain scalars and beam proofs (ints and float triples) cannot hold arrays.
            if type(item) not in (int, float, str, bool, BeamProof) and item is not None:
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
    # Every accepted ID must exist in the input and keep strictly increasing input order.
    order = np.argsort(frame.point_ids, kind="stable")
    sorted_ids = frame.point_ids[order]
    found = np.searchsorted(sorted_ids, result.point_ids)
    clipped = np.minimum(found, max(len(sorted_ids) - 1, 0))
    if len(result.point_ids) and (
        not len(sorted_ids)
        or np.any(sorted_ids[clipped] != result.point_ids)
        or np.any(np.diff(order[clipped]) <= 0)
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
    if result.stage in LEARNED_STAGES and (
        np.any(result.motion_state)
        or np.any(result.motion_confidence)
        or np.any(result.semantic_support != (result.semantic_id != 0))
    ):
        raise ValueError("semantic-only-claims")


def _validate_objects(
    frame: ScanFrame, result: ProductFrameResult, track_births: dict[int, int], deep: bool = True
) -> None:
    accepted = set(result.point_ids.tolist())
    input_positions: dict[int, int] = {}
    accepted_positions: dict[int, int] = {}
    if deep and result.stage in ("candidate", *TRACKED_STAGES):
        input_positions = {int(p): index for index, p in enumerate(frame.point_ids)}
        accepted_positions = {int(p): index for index, p in enumerate(result.point_ids)}
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
        if result.stage in ("candidate", *TRACKED_STAGES):
            if not instance.point_ids or instance.point_ids != tuple(sorted(instance.point_ids)):
                raise ValueError("candidate-support-order")
            if instance.instance_id != len(instance_ids) - 1:
                raise ValueError("candidate-id-order")
            if instance.uncertainty_m is not None or (
                instance.status == "observed"
                and (instance.semantic_id == 0 or len(instance.point_ids) < 3)
            ):
                raise ValueError("candidate-ambiguity")
            if not deep:
                continue
            source_positions = [input_positions[point_id] for point_id in instance.point_ids]
            source = frame.points_sensor[source_positions, :3].astype(np.float64)
            mapped = source @ frame.map_from_sensor[:3, :3].T + frame.map_from_sensor[:3, 3]
            if not np.allclose(
                mapped.min(axis=0), instance.bounds_min_m, rtol=0, atol=1e-6
            ) or not np.allclose(mapped.max(axis=0), instance.bounds_max_m, rtol=0, atol=1e-6):
                raise ValueError("candidate-bounds")
            positions = [accepted_positions[point_id] for point_id in instance.point_ids]
            if instance.semantic_id and np.any(
                result.semantic_id[positions] != instance.semantic_id
            ):
                raise ValueError("candidate-class-support")
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
    if result.stage == "candidate" and (result.tracks or result.beams):
        raise ValueError("candidate-temporal-claims")


def _validate_cells(frame: ScanFrame, result: ProductFrameResult, deep: bool = True) -> None:
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
    if n and int(np.abs(cells.indices).max()) >= 1 << 25:
        raise ValueError("cell-index")
    packed = pack_cells(cells.level, cells.indices)
    ordered_packed = np.sort(packed)
    if np.any(ordered_packed[1:] == ordered_packed[:-1]):
        raise ValueError("cell-overlap")
    for level in range(len(sizes)):
        finer = cells.indices[cells.level == level]
        for coarser in range(level + 1, len(sizes)):
            ratio = sizes[coarser] // sizes[level]
            parents = pack_cells(np.full(len(finer), coarser, dtype=np.int64), finer // ratio)
            if len(parents):
                positions = np.searchsorted(ordered_packed, parents)
                valid = positions < n
                if np.any(ordered_packed[positions[valid]] == parents[valid]):
                    raise ValueError("cell-overlap")
    beam_ids, beam_points, origins, returns = _beam_columns(result)
    if len(np.unique(beam_ids)) != len(beam_ids):
        raise ValueError("beam-id")
    if len(beam_ids):
        if (
            np.any(beam_ids < 0)
            or origins.shape != (len(beam_ids), 3)
            or returns.shape != (len(beam_ids), 3)
            or not np.isin(beam_points, result.point_ids).all()
            or not np.isfinite(origins).all()
            or not np.isfinite(returns).all()
        ):
            raise ValueError("beam-support")
        if not np.allclose(origins, frame.map_from_sensor[:3, 3], rtol=0, atol=1e-6):
            raise ValueError("beam-origin-mismatch")
    point_positions = {int(p): index for index, p in enumerate(frame.point_ids)} if deep else {}
    if len(beam_ids) and deep:
        source = frame.points_sensor[[point_positions[int(p)] for p in beam_points], :3]
        expected = (
            source.astype(np.float64) @ frame.map_from_sensor[:3, :3].T
            + frame.map_from_sensor[:3, 3]
        )
        if not np.allclose(expected, returns, rtol=0, atol=1e-6):
            raise ValueError("beam-return-mismatch")
    free = cells.occupancy == Occupancy.OBSERVED_FREE
    if np.any(~free & (cells.free_beam_id != -1)):
        raise ValueError("unexpected-free-proof")
    if np.any(free):
        rows = np.flatnonzero(free)
        proof = cells.free_beam_id[rows]
        if np.any(cells.ray_support[rows] < 1) or not np.isin(proof, beam_ids).all():
            raise ValueError("unsupported-free")
    if np.any(free) and deep:
        rows = np.flatnonzero(free)
        proof = cells.free_beam_id[rows]
        selected = [point_positions[int(point_id)] for point_id in result.point_ids]
        xyz_sensor = frame.points_sensor[selected, :3].astype(np.float64)
        xyz_map = xyz_sensor @ frame.map_from_sensor[:3, :3].T + frame.map_from_sensor[:3, 3]
        free_level = cells.level[rows]
        indices = cells.indices[rows]
        for current, width_cm in enumerate(sizes):
            xy_index = np.floor(xyz_map[:, :2] / (width_cm / 100)).astype(np.int64)
            at_level = free_level == current
            occupied = pack_cells(np.full(len(xy_index), current, dtype=np.int64), xy_index)
            if np.any(np.isin(pack_cells(free_level[at_level], indices[at_level]), occupied)):
                raise ValueError("unsupported-free")
        order = np.argsort(beam_ids)
        beam_rows = order[np.searchsorted(beam_ids[order], proof)]
        width_m = np.asarray(sizes, dtype=np.float64)[free_level] / 100
        low = indices.astype(np.float64) * width_m[:, None]
        high = low + width_m[:, None]
        start = origins[beam_rows, :2]
        return_xy = returns[beam_rows, :2]
        if np.any(np.all((return_xy >= low) & (return_xy < high), axis=1)):
            raise ValueError("unsupported-free")
        if not np.all(_segments_cross_open_cells(start, return_xy - start, low, high)):
            raise ValueError("unsupported-free")
    if result.stage in ("diagnostic", "semantic", "candidate", "tracking") and np.any(
        (cells.occupancy != Occupancy.UNKNOWN) & (cells.occupancy != Occupancy.AMBIGUOUS)
    ):
        raise ValueError("diagnostic-occupancy")


def _beam_columns(
    result: ProductFrameResult,
) -> tuple[IntArray, IntArray, FloatArray, FloatArray]:
    """Beam IDs, point IDs, origins (B, 3) and returns (B, 3) from either representation."""
    table = result.beam_table
    if table is None:
        if not result.beams:
            empty = np.empty(0, dtype=np.int64)
            return empty, empty, np.empty((0, 3)), np.empty((0, 3))
        origins = np.array([beam.origin_map_m for beam in result.beams], dtype=np.float64)
        returns = np.array([beam.return_map_m for beam in result.beams], dtype=np.float64)
        return (
            np.array([beam.beam_id for beam in result.beams], dtype=np.int64),
            np.array([beam.point_id for beam in result.beams], dtype=np.int64),
            origins.reshape(len(result.beams), -1),
            returns.reshape(len(result.beams), -1),
        )
    count = len(table.beam_id)
    if (
        table.beam_id.shape != (count,)
        or table.beam_id.dtype != np.int64
        or table.point_id.shape != (count,)
        or table.point_id.dtype != np.int64
        or table.origin_map_m.shape != (3,)
        or table.origin_map_m.dtype != np.float64
        or table.return_map_m.shape != (count, 3)
        or table.return_map_m.dtype != np.float64
    ):
        raise ValueError("beam-table-shape")
    origins = np.broadcast_to(table.origin_map_m, (count, 3))
    return table.beam_id, table.point_id, origins, table.return_map_m


def _segments_cross_open_cells(
    start: FloatArray, delta: FloatArray, low: FloatArray, high: FloatArray
) -> BoolArray:
    """Row-wise ``_segment_crosses_open_cell`` for (M, 2) arrays, with identical arithmetic."""
    enter = np.zeros(len(start), dtype=np.float64)
    exit_ = np.ones(len(start), dtype=np.float64)
    valid = np.ones(len(start), dtype=np.bool_)
    for axis in range(2):
        still = delta[:, axis] == 0
        inside = (low[:, axis] < start[:, axis]) & (start[:, axis] < high[:, axis])
        valid &= ~still | inside
        step = np.where(still, 1.0, delta[:, axis])
        first = (low[:, axis] - start[:, axis]) / step
        second = (high[:, axis] - start[:, axis]) / step
        enter = np.where(still, enter, np.maximum(enter, np.minimum(first, second)))
        exit_ = np.where(still, exit_, np.minimum(exit_, np.maximum(first, second)))
    return np.asarray(valid & (enter < exit_) & (enter < 1) & (exit_ > 0), dtype=np.bool_)


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


def _validate_visibility(frame: ScanFrame, result: ProductFrameResult, deep: bool = True) -> None:
    """Check current-scan occupancy against the payload's own returns, proofs and candidates."""
    summary = result.visibility_summary
    cells = result.cells
    if (
        summary is None
        or result.beam_table is None
        or result.beams
        or summary.method != VISIBILITY_METHOD
        or type(summary.max_free_cells) is not int
        or not 1 <= summary.max_free_cells <= MAX_FREE_CELLS
        or any(
            type(value) is not float or not math.isfinite(value) or value <= 0
            for value in (summary.tau_free_m, summary.corridor_max_m, summary.conflict_margin_m)
        )
        or summary.deskew_status != frame.deskew_status
    ):
        raise ValueError("visibility-contract")
    occupancy = cells.occupancy
    free = occupancy == Occupancy.OBSERVED_FREE
    counters = (
        summary.qualifying_beams,
        summary.free_cells,
        summary.occupied_cells,
        summary.ambiguous_cells,
        summary.unknown_cells,
        summary.rejected_free_cells,
    )
    if (
        any(type(value) is not int or value < 0 for value in counters)
        or summary.free_cells != np.count_nonzero(free)
        or summary.occupied_cells != np.count_nonzero(occupancy == Occupancy.OCCUPIED)
        or summary.ambiguous_cells != np.count_nonzero(occupancy == Occupancy.AMBIGUOUS)
        or summary.unknown_cells != np.count_nonzero(occupancy == Occupancy.UNKNOWN)
        or summary.free_cells > summary.max_free_cells
        or (summary.rejected_free_cells > 0 and summary.free_cells != summary.max_free_cells)
        or len(_beam_columns(result)[0]) > summary.qualifying_beams
    ):
        raise ValueError("visibility-summary")
    if (
        np.any(occupancy == Occupancy.STALE)
        or np.any(cells.source != EvidenceSource.CURRENT_SCAN)
        or np.any(cells.last_observed_ns != result.scan_timestamp_ns)
        or np.any(cells.uncertainty != -1)
    ):
        raise ValueError("visibility-temporal-claims")
    if (
        np.any((occupancy == Occupancy.OCCUPIED) & (cells.obstacle_support < 1))
        or np.any((occupancy == Occupancy.UNKNOWN) & (cells.obstacle_support != 0))
        or np.any(free & ((cells.obstacle_support != 0) | cells.conflict))
        or np.any(free & ((cells.semantic_id != 0) | (cells.semantic_support != 0)))
        or np.any(~free & (cells.ray_support != 0))
    ):
        raise ValueError("visibility-occupancy-support")
    if not deep:
        return

    # Deep audit: recompute each accepted return's owning listed cell with the mapping rule.
    input_positions = {int(point_id): index for index, point_id in enumerate(frame.point_ids)}
    selected = [input_positions[int(point_id)] for point_id in result.point_ids]
    xyz = (
        frame.points_sensor[selected, :3].astype(np.float64) @ frame.map_from_sensor[:3, :3].T
        + frame.map_from_sensor[:3, 3]
    )
    n = len(selected)
    base = np.floor(xyz[:, :2] / 0.05).astype(np.int64)
    listed = pack_cells(cells.level, cells.indices)
    order = np.argsort(listed)
    ordered = listed[order]
    point_cell = np.full(n, -1, dtype=np.int64)
    sizes = cells.cell_sizes_cm
    for level, size in enumerate(sizes):
        if not len(ordered):
            break
        keys = pack_cells(np.full(n, level, dtype=np.int64), base // (size // sizes[0]))
        where = np.minimum(np.searchsorted(ordered, keys), len(ordered) - 1)
        hit = (ordered[where] == keys) & (point_cell < 0)
        point_cell[hit] = order[where[hit]]
    if np.any(point_cell < 0) or np.any(free[point_cell]):
        raise ValueError("visibility-point-cell")
    returns = np.bincount(point_cell, minlength=len(listed))
    if np.any(~free & (returns == 0)) or np.any(cells.obstacle_support > returns):
        raise ValueError("visibility-unsupported-cell")
    accepted_positions = {int(point_id): index for index, point_id in enumerate(result.point_ids)}
    support = [accepted_positions[p] for item in result.instances for p in item.point_ids]
    supported = occupancy[point_cell[support]]
    if np.any((supported != Occupancy.OCCUPIED) & (supported != Occupancy.AMBIGUOUS)):
        raise ValueError("visibility-candidate-cell")

    if not np.any(free):
        return
    settings = VisibilitySettings(
        summary.tau_free_m, summary.corridor_max_m, summary.conflict_margin_m
    )
    origin = frame.map_from_sensor[:3, 3]
    rows = np.flatnonzero(free)
    beam_ids, beam_points, _, beam_returns = _beam_columns(result)
    order = np.argsort(beam_ids)
    used = order[np.searchsorted(beam_ids[order], cells.free_beam_id[rows])]
    proof_semantic = result.semantic_id[[accepted_positions[int(p)] for p in beam_points[used]]]
    if (
        np.any(beam_ids[used] != beam_points[used])
        or not np.isin(proof_semantic, GROUND_SEMANTIC_IDS).all()
    ):
        raise ValueError("visibility-beam")
    returned = beam_returns[used]
    fraction = corridor_start_fraction(origin, returned, settings)
    width_m = np.asarray(sizes, dtype=np.float64)[cells.level[rows]] / 100
    low = cells.indices[rows].astype(np.float64) * width_m[:, None]
    high = low + width_m[:, None]
    start = origin[:2] + fraction[:, None] * (returned[:, :2] - origin[:2])
    if not np.isfinite(fraction).all() or not np.all(
        _segments_cross_open_cells(start, returned[:, :2] - start, low, high)
    ):
        raise ValueError("visibility-corridor")

    # Any non-ground-semantic or candidate-supporting return inside the margin forbids free.
    margin = summary.conflict_margin_m
    conflict = ~np.isin(result.semantic_id, GROUND_SEMANTIC_IDS)
    conflict[support] = True
    conflict_xy = xyz[conflict, :2]
    if not len(conflict_xy):
        return
    buckets = np.floor(conflict_xy / margin).astype(np.int64)
    first = np.floor((low - margin) / margin).astype(np.int64)
    last = np.floor((high + margin) / margin).astype(np.int64)
    if max(np.abs(buckets).max(), np.abs(first).max(), np.abs(last).max()) >= 1 << 24:
        raise ValueError("visibility-contract")
    packed = pack_cells(np.zeros(len(buckets), dtype=np.int64), buckets)
    by_bucket = np.argsort(packed)
    sorted_keys = packed[by_bucket]
    span = int((last - first).max()) + 1
    for dx in range(span):
        for dy in range(span):
            bucket = first + (dx, dy)
            valid = np.all(bucket <= last, axis=1)
            key = pack_cells(np.zeros(len(bucket), dtype=np.int64), bucket)
            lower = np.searchsorted(sorted_keys, key, side="left")
            counts = np.where(valid, np.searchsorted(sorted_keys, key, side="right") - lower, 0)
            total = int(counts.sum())
            if not total:
                continue
            cell = np.repeat(np.arange(len(bucket)), counts)
            offset = np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)
            points = conflict_xy[by_bucket[np.repeat(lower, counts) + offset]]
            gap = np.maximum(np.maximum(low[cell] - points, points - high[cell]), 0)
            if np.any(np.hypot(gap[:, 0], gap[:, 1]) < margin):
                raise ValueError("visibility-margin")


def _validate_fused_cells(value: FusedCellEvidence, result: ProductFrameResult) -> None:
    """Validate the complete-result temporal map without trusting its summary."""
    n = len(value.level)
    specs = (
        (value.level, (n,), np.int64),
        (value.indices, (n, 2), np.int64),
        (value.centers_xy_m, (n, 2), np.float64),
        (value.size_m, (n,), np.float64),
        (value.ground_height_m, (n,), np.float64),
        (value.ground_sigma_m, (n,), np.float64),
        (value.ground_valid, (n,), np.bool_),
        (value.occupancy, (n,), np.uint8),
        (value.terrain, (n,), np.uint8),
        (value.flags, (n,), np.uint8),
        (value.semantic_id, (n,), np.uint8),
        (value.obstacle_low_m, (n,), np.float64),
        (value.obstacle_high_m, (n,), np.float64),
        (value.last_seen_ns, (n,), np.int64),
        (value.observations, (n,), np.int64),
    )
    if any(array.shape != shape or array.dtype != dtype for array, shape, dtype in specs):
        raise ValueError("fused-cell-shape-dtype")
    sizes = value.cell_sizes_cm
    if sizes != result.cells.cell_sizes_cm or not sizes or sizes[0] != 5:
        raise ValueError("fused-cell-size")
    if any(size <= 0 or size % 5 for size in sizes) or any(
        larger % smaller for smaller, larger in zip(sizes, sizes[1:], strict=False)
    ):
        raise ValueError("fused-cell-size")
    if np.any(value.level < 0) or np.any(value.level >= len(sizes)):
        raise ValueError("fused-cell-level")
    if np.any(value.occupancy > max(FusedOccupancy)) or np.any(value.terrain > max(TerrainState)):
        raise ValueError("fused-cell-state")
    if np.any(value.semantic_id > 19) or np.any(value.observations < 0):
        raise ValueError("fused-cell-range")
    if (
        not np.isfinite(value.centers_xy_m).all()
        or not np.isfinite(value.size_m).all()
        or not np.isfinite(value.ground_height_m).all()
        or not np.isfinite(value.ground_sigma_m).all()
        or not np.isfinite(value.obstacle_low_m).all()
        or not np.isfinite(value.obstacle_high_m).all()
        or np.any(value.size_m <= 0)
        or np.any(value.ground_sigma_m < -1)
        or np.any(value.last_seen_ns < -1)
        or np.any(value.last_seen_ns > result.scan_timestamp_ns)
    ):
        raise ValueError("fused-cell-values")
    expected_size = np.asarray(sizes, dtype=np.float64)[value.level] / 100
    expected_centers = (value.indices.astype(np.float64) + 0.5) * expected_size[:, None]
    if not np.array_equal(value.size_m, expected_size) or not np.allclose(
        value.centers_xy_m, expected_centers, rtol=0, atol=1e-12
    ):
        raise ValueError("fused-cell-geometry")
    packed = pack_cells(value.level, value.indices)
    ordered = np.sort(packed)
    if np.any(ordered[1:] == ordered[:-1]):
        raise ValueError("fused-cell-overlap")
    for level in range(len(sizes)):
        finer = value.indices[value.level == level]
        for coarser in range(level + 1, len(sizes)):
            ratio = sizes[coarser] // sizes[level]
            parents = pack_cells(np.full(len(finer), coarser, dtype=np.int64), finer // ratio)
            if len(parents):
                positions = np.searchsorted(ordered, parents)
                valid = positions < n
                if np.any(ordered[positions[valid]] == parents[valid]):
                    raise ValueError("fused-cell-overlap")
    summary = value.summary
    if (
        summary.method != "rolling-kalman-logodds-v1"
        or summary.published_cells != n
        or summary.allocated_bytes <= 0
        or summary.curb_cells != int(np.count_nonzero(value.flags & 1))
        or summary.drop_cells != int(np.count_nonzero(value.flags & 2))
        or summary.overhang_cells != int(np.count_nonzero(value.flags & 4))
        or summary.terrain_counts
        != tuple(int(item) for item in np.bincount(value.terrain, minlength=len(TerrainState)))
        or summary.occupancy_counts
        != tuple(int(item) for item in np.bincount(value.occupancy, minlength=len(FusedOccupancy)))
    ):
        raise ValueError("fused-summary")


def _validate_resource_limits(result: ProductFrameResult) -> None:
    limits = result.resource_limits
    if limits is None:
        raise ValueError("missing-resource-contract")
    diagnostics = result.diagnostics
    if result.accounting.input_points > limits.max_points:
        raise ValueError("above-resource-point-cap")
    if diagnostics.map_cells > limits.max_map_cells:
        raise ValueError("resource-map-cap")
    if diagnostics.track_count > limits.max_tracks:
        raise ValueError("resource-track-cap")
    if diagnostics.queue_depth > limits.max_queue_depth:
        raise ValueError("resource-queue-cap")
    if diagnostics.queue_age_ms > limits.max_queue_age_ms:
        raise ValueError("resource-queue-age")
    for value, ceiling, code in (
        (diagnostics.process_rss_bytes, limits.max_process_rss_bytes, "resource-rss-cap"),
        (diagnostics.device_memory_bytes, limits.max_device_memory_bytes, "resource-device-cap"),
        (diagnostics.swap_delta_bytes, limits.max_swap_delta_bytes, "resource-swap-cap"),
        (diagnostics.receipt_bytes, limits.max_receipt_bytes, "resource-receipt-cap"),
        (diagnostics.audit_bytes, limits.max_audit_bytes, "resource-audit-cap"),
    ):
        if value is not None and value > ceiling:
            raise ValueError(code)
    if (
        diagnostics.disk_free_bytes is not None
        and diagnostics.disk_free_bytes < limits.min_disk_free_bytes
    ):
        raise ValueError("resource-disk-reserve")


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
    expected_cells = (
        len(result.fused.level)
        if result.stage == "complete" and result.fused
        else len(result.cells.level)
    )
    if value.map_cells != expected_cells or value.track_count != len(result.tracks):
        raise ValueError("state-size-mismatch")
    if result.stage in ("candidate", *TRACKED_STAGES) and value.detector_ms is None:
        raise ValueError("missing-detector-time")
    if result.stage in ("visibility", "complete") and value.visibility_ms is None:
        raise ValueError("visibility-time")
    if result.stage not in ("visibility", "complete") and value.visibility_ms is not None:
        raise ValueError("visibility-time")
    if result.stage == "complete" and value.fusion_ms is None:
        raise ValueError("missing-fusion-time")
    if value.process_rss_bytes is not None and value.process_rss_bytes < 0:
        raise ValueError("invalid-memory")
    if value.device_memory_status not in ("unavailable", "sampled") or (
        value.device_memory_bytes is not None and value.device_memory_bytes < 0
    ):
        raise ValueError("invalid-device-memory")
    if value.device_memory_status == "sampled" and value.device_memory_bytes is None:
        raise ValueError("missing-device-sample")
    for name in ("swap_delta_bytes", "receipt_bytes", "audit_bytes", "disk_free_bytes"):
        sample = getattr(value, name)
        if sample is not None and sample < 0:
            raise ValueError("invalid-resource-sample")
