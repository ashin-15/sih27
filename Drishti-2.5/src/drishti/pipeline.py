from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING, Literal

import numpy as np

from drishti.arrays import ByteArray, FloatArray, IntArray, PointArray, immutable
from drishti.config import MappingConfig
from drishti.contracts import Accounting, Mode, ScanFrame
from drishti.cuda_backend import CudaFramePath
from drishti.geometry import transform_points
from drishti.ground import GroundClass, GroundSegmenter, PatchworkGround
from drishti.learned import SemanticPredictor
from drishti.mapping import MapSnapshot, aggregate_cells
from drishti.obstacles import InstanceEvidence, ObstacleDetector
from drishti.projection import RangeImage, project
from drishti.tracking import CandidateTracker, TrackingUpdate

if TYPE_CHECKING:
    from drishti.product_result import (
        InProcessProductEvaluator,
        ProductFrameResult,
        ProductReceipt,
    )


@dataclass(frozen=True)
class PointObservations:
    points_sensor: PointArray
    points_map_m: FloatArray
    point_ids: IntArray
    ground: ByteArray
    semantic: ByteArray
    semantic_confidence: FloatArray
    semantic_unknown_reason: ByteArray
    motion: ByteArray
    cell_indices: IntArray


@dataclass(frozen=True)
class StageTimings:
    preprocess_ms: float
    model_ms: float | None
    ground_ms: float
    projection_ms: float
    mapping_ms: float
    total_ms: float
    detector_ms: float | None = None
    association_ms: float | None = None


@dataclass(frozen=True)
class FrameResult:
    snapshot: MapSnapshot
    observations: PointObservations
    range_image: RangeImage
    accounting: Accounting
    timings: StageTimings
    instances: tuple[InstanceEvidence, ...] = ()
    tracking: TrackingUpdate | None = None


class MappingEngine:
    def __init__(
        self,
        config: MappingConfig,
        *,
        mode: Mode = Mode.GEOMETRIC,
        ground: GroundSegmenter | None = None,
        predictor: SemanticPredictor | None = None,
        detector: ObstacleDetector | None = None,
        tracker: CandidateTracker | None = None,
        device: Literal["cpu", "cuda"] = "cpu",
    ) -> None:
        if mode not in (Mode.GEOMETRIC, Mode.ORACLE, Mode.LEARNED):
            raise ValueError("mapping mode must be geometric, oracle or learned")
        if (mode == Mode.LEARNED) != (predictor is not None):
            raise ValueError("learned mode requires a predictor; other modes forbid it")
        if device not in ("cpu", "cuda"):
            raise ValueError("mapping device must be cpu or cuda")
        if detector is not None and (mode != Mode.LEARNED or device != "cpu"):
            raise ValueError("obstacle candidates require learned CPU mode")
        if tracker is not None and detector is None:
            raise ValueError("tracking requires the learned CPU candidate stage")
        self.tracker = tracker
        self._pending_tracking: FrameResult | None = None
        self._tracking_failed = False
        self.config = config
        self.mode = mode
        self.device = device
        self._cuda = CudaFramePath() if device == "cuda" else None
        self.ground = PatchworkGround(config) if ground is None else ground
        self.predictor = predictor
        self.detector = detector
        self._stream: str | None = None
        self._last_frame = -1
        self._last_timestamp = -1.0

    def process(self, frame: ScanFrame) -> FrameResult:
        if self._tracking_failed:
            raise ValueError("tracking result rejected; restart sequence with a new engine")
        if self._pending_tracking is not None:
            raise ValueError("evaluate pending tracking result before processing another frame")
        start = perf_counter()
        config = self.config
        if self._stream is not None and frame.sequence != self._stream:
            raise ValueError("use a separate engine for each stream")
        if frame.frame_id <= self._last_frame or frame.timestamp_s <= self._last_timestamp:
            raise ValueError("stateful preprocessing requires increasing frame IDs and timestamps")
        if len(frame.points_sensor) > config.max_points:
            raise ValueError("scan point count exceeds configured capacity")
        if self.mode == Mode.ORACLE and frame.annotations is None:
            raise ValueError("oracle mode requires point-aligned annotations")
        if np.any(np.abs(frame.map_from_sensor[:2, 3]) > config.max_abs_coordinate_m):
            raise ValueError("sensor pose exceeds the configured coordinate bound")
        xyz = frame.points_sensor[:, :3].astype(np.float64)
        valid = np.isfinite(xyz[:, 0]) & np.isfinite(xyz[:, 1]) & np.isfinite(xyz[:, 2])
        valid &= (
            np.maximum(np.maximum(np.abs(xyz[:, 0]), np.abs(xyz[:, 1])), np.abs(xyz[:, 2]))
            <= config.max_abs_coordinate_m
        )
        range_m = np.sqrt(xyz[:, 0] ** 2 + xyz[:, 1] ** 2 + xyz[:, 2] ** 2)
        valid &= range_m >= config.min_range_m
        indices = np.flatnonzero(valid)
        xyz_map_m = transform_points(xyz[indices], frame.map_from_sensor)
        delta_m = xyz_map_m[:, :2] - frame.map_from_sensor[:2, 3]
        distance_m = (
            np.sqrt(delta_m[:, 0] ** 2 + delta_m[:, 1] ** 2)
            if config.footprint == "radial"
            else np.maximum(np.abs(delta_m[:, 0]), np.abs(delta_m[:, 1]))
        )
        in_roi = (distance_m < config.radii_m[-1]) & (
            np.maximum(np.abs(xyz_map_m[:, 0]), np.abs(xyz_map_m[:, 1]))
            <= config.max_abs_coordinate_m
        )
        in_height = np.abs(xyz_map_m[:, 2]) <= config.max_abs_height_m
        accepted = indices[in_roi & in_height]
        if len(accepted) == len(frame.points_sensor):
            points = frame.points_sensor
            ids = frame.point_ids
        else:
            points = immutable(frame.points_sensor[accepted])
            ids = immutable(frame.point_ids[accepted])
        mapped = immutable(xyz_map_m[in_roi & in_height])
        semantic = np.zeros(len(points), dtype=np.uint8)
        semantic_confidence = np.zeros(len(points), dtype=np.float64)
        semantic_unknown_reason = np.ones(len(points), dtype=np.uint8)
        motion = np.zeros(len(points), dtype=np.uint8)
        if self.mode == Mode.ORACLE:
            annotations = frame.annotations
            if annotations is None:
                raise ValueError("oracle mode requires annotations")
            semantic = annotations.semantic[accepted]
            semantic_confidence = np.where(semantic == 0, 0.0, 1.0).astype(np.float64)
            semantic_unknown_reason = np.where(semantic == 0, 2, 0).astype(np.uint8)
            motion = annotations.motion[accepted]
        preprocessed = perf_counter()
        if self.mode == Mode.LEARNED:
            if self.predictor is None:
                raise ValueError("learned mode requires a predictor")
            if not np.isfinite(points[:, 3]).all():
                raise ValueError("FRNet requires finite intensity for every accepted point")
            prediction = self.predictor.predict(points, ids)
            if len(prediction.semantic_id) != len(points):
                raise ValueError("predictor returned the wrong number of point labels")
            semantic = prediction.semantic_id
            semantic_confidence = prediction.confidence
            semantic_unknown_reason = prediction.unknown_reason
        model_completed = perf_counter()
        ground = self.ground.segment(points)
        if ground.shape != (len(points),) or not np.isin(ground, list(GroundClass)).all():
            raise ValueError("ground provider returned invalid point-aligned classifications")
        segmented = perf_counter()
        image = (
            self._cuda.project(points, ids, config)
            if self._cuda is not None
            else project(points, ids, config)
        )
        projected = perf_counter()
        aggregate = self._cuda.aggregate_cells if self._cuda is not None else aggregate_cells
        snapshot, cell_indices = aggregate(
            mapped,
            frame.map_from_sensor[:2, 3],
            ground,
            semantic,
            motion,
            points[:, 3].astype(np.float64),
            config=config,
            sequence=frame.sequence,
            frame_id=frame.frame_id,
            timestamp_s=frame.timestamp_s,
            mode=self.mode,
            pose_source=frame.pose_source,
            ground_method=self.ground.method,
        )
        observations = PointObservations(
            points,
            mapped,
            ids,
            immutable(ground),
            immutable(semantic),
            immutable(semantic_confidence),
            immutable(semantic_unknown_reason),
            immutable(motion),
            cell_indices,
        )
        detector_started = perf_counter()
        instances = (
            self.detector.detect(observations, round(frame.timestamp_s * 1_000_000_000))
            if self.detector is not None
            else ()
        )
        detector_completed = perf_counter()
        accounting = Accounting(
            input_points=len(xyz),
            invalid_geometry=int(np.count_nonzero(~valid)),
            outside_roi=int(np.count_nonzero(~in_roi)),
            outside_height=int(np.count_nonzero(in_roi & ~in_height)),
            accepted_points=len(points),
            invalid_intensity=int(np.count_nonzero(~np.isfinite(points[:, 3]))),
            projected_points=int(np.count_nonzero(image.valid)),
            projection_collisions=image.collisions,
            outside_projection=image.outside_fov,
        )
        association_started = perf_counter()
        tracking = (
            self.tracker.prepare(
                frame.sequence, frame.frame_id, round(frame.timestamp_s * 1e9), instances
            )
            if self.tracker is not None
            else None
        )
        association_completed = perf_counter()
        self._stream = frame.sequence
        self._last_frame = frame.frame_id
        self._last_timestamp = frame.timestamp_s
        end = perf_counter()
        timings = StageTimings(
            (preprocessed - start) * 1000,
            (model_completed - preprocessed) * 1000 if self.mode == Mode.LEARNED else None,
            (segmented - model_completed) * 1000,
            (projected - segmented) * 1000,
            (detector_started - projected) * 1000,
            (end - start) * 1000,
            (detector_completed - detector_started) * 1000 if self.detector is not None else None,
            (association_completed - association_started) * 1000
            if self.tracker is not None
            else None,
        )
        result = FrameResult(
            snapshot, observations, image, accounting, timings, instances, tracking
        )
        if tracking is not None:
            self._pending_tracking = result
        return result

    def receive_tracking(
        self,
        frame: ScanFrame,
        result: FrameResult,
        product: "ProductFrameResult",
        evaluator: "InProcessProductEvaluator",
    ) -> "ProductReceipt":
        """Validate the prepared evidence before committing sequence association state."""
        from drishti.product_result import ReceiptStatus

        if self.tracker is None or result is not self._pending_tracking or result.tracking is None:
            raise ValueError("no matching prepared tracking result")
        update = result.tracking
        if (
            product.stage != "tracking"
            or product.tracks != update.tracks
            or product.tracking_summary != update.summary
            or product.instances != result.instances
            or product.frame_id != update.frame_id
            or product.sequence_id != update.sequence
            or product.scan_timestamp_ns != update.timestamp_ns
        ):
            raise ValueError("product differs from prepared tracking evidence")
        receipt = evaluator.receive(frame, product)
        if receipt.status == ReceiptStatus.ACCEPTED:
            self.tracker.commit(update)
        else:
            self.tracker.discard(update)
            # Native ground preprocessing cannot be rolled back. Fail closed and replay.
            self._tracking_failed = True
        self._pending_tracking = None
        return receipt
