"""G0 release-contract values and D-005 gate checks.

The values in this module make the current G0 implementation reviewable and
machine-checkable. They do not turn unavailable independent labels or target
hardware measurements into evidence. A caller must keep a gate in
``NOT_VERIFIED`` when its required population or resource sample is absent.
"""

import math
from dataclasses import dataclass
from typing import Literal

G0_CONTRACT_VERSION = "drishti-g0-v1"
D005_VERSION = "d005-v0.2"
D005_STATUS: Literal["implementation-candidate", "approved"] = "approved"


@dataclass(frozen=True)
class SemanticThresholds:
    """The semantic rules proposed by D-005 sheet v0.1."""

    overall_miou_floor: float = 0.65
    per_class_iou_floor: float = 0.10
    supported_range_miou_floors: tuple[float, float, float] = (0.60, 0.45, 0.20)
    unknown_overall_ceiling: float = 0.01
    unknown_range_ceiling: float = 0.02
    minimum_labeled_points: tuple[int, int, int] = (1_000_000, 250_000, 100_000)
    minimum_class_support: tuple[int, int, int] = (1_000, 1_000, 100)
    minimum_supported_classes: tuple[int, int, int] = (10, 10, 5)

    def __post_init__(self) -> None:
        if not 0 < self.overall_miou_floor <= 1:
            raise ValueError("overall_miou_floor must lie in (0, 1]")
        if not 0 < self.per_class_iou_floor <= 1:
            raise ValueError("per_class_iou_floor must lie in (0, 1]")
        if len(self.supported_range_miou_floors) != 3 or any(
            not 0 < value <= 1 for value in self.supported_range_miou_floors
        ):
            raise ValueError("supported range floors must contain three values in (0, 1]")
        if not 0 <= self.unknown_overall_ceiling <= 1 or not 0 <= self.unknown_range_ceiling <= 1:
            raise ValueError("unknown ceilings must lie in [0, 1]")
        for name, values in (
            ("minimum_labeled_points", self.minimum_labeled_points),
            ("minimum_class_support", self.minimum_class_support),
            ("minimum_supported_classes", self.minimum_supported_classes),
        ):
            if len(values) != 3 or any(type(value) is not int or value <= 0 for value in values):
                raise ValueError(f"{name} must contain three positive integers")


@dataclass(frozen=True)
class TrafficObstacleThresholds:
    """Approved AC-002 traffic-participant targets from the current sheet."""

    thing_pq_floor: float = 0.65
    per_class_recall_floor: float = 0.70
    near_recall_floor: float = 0.90
    middle_recall_floor: float = 0.85
    far_recall_floor: float = 0.70
    small_recall_floor: float = 0.85
    medium_recall_floor: float = 0.90
    large_recall_floor: float = 0.90
    unmatched_candidates_per_100_scans_ceiling: int = 100
    minimum_per_class_instances: int = 100
    minimum_range_instances: int = 100
    minimum_size_instances: int = 100

    def __post_init__(self) -> None:
        for name in (
            "thing_pq_floor",
            "per_class_recall_floor",
            "near_recall_floor",
            "middle_recall_floor",
            "far_recall_floor",
            "small_recall_floor",
            "medium_recall_floor",
            "large_recall_floor",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must lie in [0, 1]")
        for name in (
            "unmatched_candidates_per_100_scans_ceiling",
            "minimum_per_class_instances",
            "minimum_range_instances",
            "minimum_size_instances",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class EvidenceThresholds:
    """Frozen fixture rules plus explicit placeholders for unapproved gates."""

    unsupported_free_cells_max: int = 0
    false_free_rate_ceiling: float | None = None
    stale_after_s: float = 2.0
    recovery_frames: int | None = None
    terrain_iou_floor: float | None = None
    false_drivable_rate_ceiling: float | None = None
    static_velocity_error_m: float | None = None
    moving_velocity_error_m: float | None = None

    def __post_init__(self) -> None:
        if type(self.unsupported_free_cells_max) is not int or self.unsupported_free_cells_max < 0:
            raise ValueError("unsupported_free_cells_max must be a nonnegative integer")
        if self.stale_after_s <= 0 or not math.isfinite(self.stale_after_s):
            raise ValueError("stale_after_s must be finite and positive")
        if self.recovery_frames is not None and (
            type(self.recovery_frames) is not int or self.recovery_frames < 0
        ):
            raise ValueError("recovery_frames must be a nonnegative integer or None")
        for name in (
            "false_free_rate_ceiling",
            "terrain_iou_floor",
            "false_drivable_rate_ceiling",
            "static_velocity_error_m",
            "moving_velocity_error_m",
        ):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative or None")


@dataclass(frozen=True)
class ResourceLimits:
    """Initial host-derived resource ceilings for the G0 release contract.

    The selected host inventory is 15.6 GiB system RAM and 6,141 MiB GPU
    memory. These ceilings intentionally leave headroom for the operating
    system and driver. They are implementation values until the product owner
    accepts them against a controlled full-path pilot.
    """

    max_points: int = 130_000
    max_process_rss_bytes: int = 12 * 1024**3
    max_device_memory_bytes: int = 5_500 * 1024**2
    max_swap_delta_bytes: int = 0
    max_map_cells: int = 262_144
    max_tracks: int = 512
    max_queue_depth: int = 2
    max_queue_age_ms: float = 100.0
    max_receipt_bytes: int = 2 * 1024**2
    max_audit_bytes: int = 8 * 1024**2
    min_disk_free_bytes: int = 10 * 1024**3

    def __post_init__(self) -> None:
        for name in (
            "max_points",
            "max_process_rss_bytes",
            "max_device_memory_bytes",
            "max_map_cells",
            "max_tracks",
            "max_queue_depth",
            "max_receipt_bytes",
            "max_audit_bytes",
            "min_disk_free_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.max_swap_delta_bytes) is not int or self.max_swap_delta_bytes < 0:
            raise ValueError("max_swap_delta_bytes must be a nonnegative integer")
        if not math.isfinite(self.max_queue_age_ms) or self.max_queue_age_ms <= 0:
            raise ValueError("max_queue_age_ms must be finite and positive")


@dataclass(frozen=True)
class D005Thresholds:
    """Versioned G0 threshold bundle.

    ``None`` means that the required independent labels or motion reference
    are not available yet. Such a row is reportable but cannot pass a release
    gate.
    """

    version: str = D005_VERSION
    status: Literal["implementation-candidate", "approved"] = D005_STATUS
    semantic: SemanticThresholds = SemanticThresholds()
    traffic_obstacles: TrafficObstacleThresholds = TrafficObstacleThresholds()
    evidence: EvidenceThresholds = EvidenceThresholds()
    resources: ResourceLimits = ResourceLimits()

    @property
    def unresolved(self) -> tuple[str, ...]:
        unresolved = [
            "independent semantic range set",
            "wider-obstacle labels and gates",
            "held-out false-free ceiling",
            "terrain quality gate",
            "motion quality gate",
            "controlled full-path resource pilot",
        ]
        if self.evidence.false_free_rate_ceiling is not None:
            unresolved.remove("held-out false-free ceiling")
        if self.evidence.terrain_iou_floor is not None:
            unresolved.remove("terrain quality gate")
        if self.evidence.static_velocity_error_m is not None:
            unresolved.remove("motion quality gate")
        return tuple(unresolved)


DEFAULT_D005 = D005Thresholds()


@dataclass(frozen=True)
class GateCheck:
    status: Literal["passed", "failed", "not-verified"]
    failures: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def check_semantic_metrics(
    *,
    overall_miou: float,
    per_class_iou: tuple[float, ...],
    supported_range_miou: tuple[float | None, ...],
    unknown_overall: float,
    unknown_by_range: tuple[float, ...],
    thresholds: SemanticThresholds = DEFAULT_D005.semantic,
) -> GateCheck:
    """Evaluate the blocking semantic rows without rounding or averaging failures away."""
    missing: list[str] = []
    failures: list[str] = []
    if len(per_class_iou) != 19:
        missing.append("19 per-class IoUs")
    if len(supported_range_miou) != 3 or len(unknown_by_range) != 3:
        missing.append("three range strata")
    values = (overall_miou, unknown_overall, *per_class_iou, *unknown_by_range)
    if not all(math.isfinite(value) for value in values):
        missing.append("finite semantic metrics")
    if any(value is not None and not math.isfinite(value) for value in supported_range_miou):
        missing.append("finite supported-range metrics")
    if not missing:
        if overall_miou < thresholds.overall_miou_floor:
            failures.append("overall-mIoU")
        if any(value < thresholds.per_class_iou_floor for value in per_class_iou):
            failures.append("per-class-IoU")
        for index, (value, floor) in enumerate(
            zip(supported_range_miou, thresholds.supported_range_miou_floors, strict=True)
        ):
            if value is None:
                missing.append(f"supported-range-mIoU[{index}]")
            elif value < floor:
                failures.append(f"supported-range-mIoU[{index}]")
        if unknown_overall > thresholds.unknown_overall_ceiling:
            failures.append("overall-unknown-coverage")
        if any(value > thresholds.unknown_range_ceiling for value in unknown_by_range):
            failures.append("range-unknown-coverage")
    if missing:
        return GateCheck("not-verified", tuple(failures), tuple(missing))
    return GateCheck("failed" if failures else "passed", tuple(failures))


def check_traffic_metrics(
    *,
    thing_pq: float,
    per_class_recall: tuple[float, ...],
    range_recall: tuple[float, ...],
    size_recall: tuple[float, ...],
    per_class_support: tuple[int, ...],
    range_support: tuple[int, ...],
    size_support: tuple[int, ...],
    unmatched_candidates_per_100_scans: float,
    thresholds: TrafficObstacleThresholds = DEFAULT_D005.traffic_obstacles,
) -> GateCheck:
    """Evaluate the approved AC-002 traffic-participant rows."""
    missing: list[str] = []
    failures: list[str] = []
    if len(per_class_recall) != 8 or len(per_class_support) != 8:
        missing.append("eight traffic classes")
    if len(range_recall) != 3 or len(range_support) != 3:
        missing.append("three traffic ranges")
    if len(size_recall) != 3 or len(size_support) != 3:
        missing.append("three traffic size strata")
    values = (
        thing_pq,
        unmatched_candidates_per_100_scans,
        *per_class_recall,
        *range_recall,
        *size_recall,
    )
    if not all(math.isfinite(value) for value in values):
        missing.append("finite traffic metrics")
    if not missing:
        if thing_pq < thresholds.thing_pq_floor:
            failures.append("thing-PQ")
        if any(support < thresholds.minimum_per_class_instances for support in per_class_support):
            missing.append("per-class traffic support")
        if any(support < thresholds.minimum_range_instances for support in range_support):
            missing.append("range traffic support")
        if any(support < thresholds.minimum_size_instances for support in size_support):
            missing.append("size traffic support")
        if (
            unmatched_candidates_per_100_scans
            > thresholds.unmatched_candidates_per_100_scans_ceiling
        ):
            failures.append("unmatched-candidates")
        if not any(
            support < thresholds.minimum_per_class_instances for support in per_class_support
        ):
            if any(value < thresholds.per_class_recall_floor for value in per_class_recall):
                failures.append("per-class-recall")
        range_floors = (
            thresholds.near_recall_floor,
            thresholds.middle_recall_floor,
            thresholds.far_recall_floor,
        )
        if not any(support < thresholds.minimum_range_instances for support in range_support):
            if any(value < floor for value, floor in zip(range_recall, range_floors, strict=True)):
                failures.append("range-recall")
        size_floors = (
            thresholds.small_recall_floor,
            thresholds.medium_recall_floor,
            thresholds.large_recall_floor,
        )
        if not any(support < thresholds.minimum_size_instances for support in size_support):
            if any(value < floor for value, floor in zip(size_recall, size_floors, strict=True)):
                failures.append("size-recall")
    if missing:
        return GateCheck("not-verified", tuple(failures), tuple(missing))
    return GateCheck("failed" if failures else "passed", tuple(failures))


def check_evidence_metrics(
    *,
    unsupported_free_cells: int,
    false_free_rate: float | None = None,
    terrain_iou: float | None = None,
    false_drivable_rate: float | None = None,
    static_velocity_error_m: float | None = None,
    moving_velocity_error_m: float | None = None,
    thresholds: EvidenceThresholds = DEFAULT_D005.evidence,
) -> GateCheck:
    """Check deterministic free-space safety and any currently frozen evidence rows."""
    failures: list[str] = []
    missing: list[str] = []
    if unsupported_free_cells > thresholds.unsupported_free_cells_max:
        failures.append("unsupported-free-cells")
    for name, value, limit in (
        ("false-free-rate", false_free_rate, thresholds.false_free_rate_ceiling),
        ("terrain-IoU", terrain_iou, thresholds.terrain_iou_floor),
        ("false-drivable-rate", false_drivable_rate, thresholds.false_drivable_rate_ceiling),
        ("static-velocity-error", static_velocity_error_m, thresholds.static_velocity_error_m),
        ("moving-velocity-error", moving_velocity_error_m, thresholds.moving_velocity_error_m),
    ):
        if limit is None or value is None:
            missing.append(name)
        elif not math.isfinite(value):
            missing.append(f"finite-{name}")
        elif name in {"false-free-rate", "false-drivable-rate"} and value > limit:
            failures.append(name)
        elif name == "terrain-IoU" and value < limit:
            failures.append(name)
        elif name.endswith("velocity-error") and value > limit:
            failures.append(name)
    if missing:
        return GateCheck("not-verified", tuple(failures), tuple(missing))
    return GateCheck("failed" if failures else "passed", tuple(failures))


def check_resource_sample(
    *,
    process_rss_bytes: int | None,
    device_memory_bytes: int | None,
    swap_delta_bytes: int | None,
    map_cells: int,
    track_count: int,
    queue_depth: int,
    queue_age_ms: float,
    receipt_bytes: int | None = None,
    audit_bytes: int | None = None,
    disk_free_bytes: int | None = None,
    limits: ResourceLimits = DEFAULT_D005.resources,
    backend: Literal["cpu", "cuda"] = "cpu",
) -> GateCheck:
    """Check one resource sample against the versioned ceilings."""
    missing: list[str] = []
    failures: list[str] = []
    if process_rss_bytes is None:
        missing.append("process-rss")
    elif process_rss_bytes > limits.max_process_rss_bytes:
        failures.append("process-rss")
    if backend == "cuda":
        if device_memory_bytes is None:
            missing.append("device-memory")
        elif device_memory_bytes > limits.max_device_memory_bytes:
            failures.append("device-memory")
    if swap_delta_bytes is None:
        missing.append("swap-delta")
    elif swap_delta_bytes > limits.max_swap_delta_bytes:
        failures.append("swap-delta")
    if map_cells > limits.max_map_cells:
        failures.append("map-cells")
    if track_count > limits.max_tracks:
        failures.append("tracks")
    if queue_depth > limits.max_queue_depth:
        failures.append("queue-depth")
    if queue_age_ms > limits.max_queue_age_ms:
        failures.append("queue-age")
    if receipt_bytes is None:
        missing.append("receipt-bytes")
    elif receipt_bytes > limits.max_receipt_bytes:
        failures.append("receipt-bytes")
    if audit_bytes is None:
        missing.append("audit-bytes")
    elif audit_bytes > limits.max_audit_bytes:
        failures.append("audit-bytes")
    if disk_free_bytes is None:
        missing.append("disk-free")
    elif disk_free_bytes < limits.min_disk_free_bytes:
        failures.append("disk-free")
    if missing:
        return GateCheck("not-verified", tuple(failures), tuple(missing))
    return GateCheck("failed" if failures else "passed", tuple(failures))
