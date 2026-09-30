import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, sleep
from typing import TYPE_CHECKING, Protocol

import numpy as np

from drishti.config import load_config
from drishti.contracts import Mode, PoseSource, ScanFrame, make_frame
from drishti.dataset import DatasetSource
from drishti.learned import FRNET_CLASS_MAP_VERSION, FRNET_REVISION, FRNetPredictor
from drishti.obstacles import ConnectedComponentDetector, panoptic_raw_labels
from drishti.output import InProcessFrameConsumer
from drishti.pipeline import FrameResult, MappingEngine
from drishti.product_result import (
    InProcessProductEvaluator,
    Occupancy,
    ProductFrameResult,
    ReceiptStatus,
    candidate_product_result,
    diagnostic_product_result,
    semantic_product_result,
    tracking_product_result,
    visibility_product_result,
)
from drishti.semantics import LEARNING_TO_RAW, decode_semantickitti
from drishti.tracking import MAX_TRACKS, CandidateTracker
from drishti.visibility import VISIBILITY_METHOD, CurrentScanVisibility, VisibilitySettings

if TYPE_CHECKING:
    from drishti.frnet_model import TorchFRNetPredictor

if sys.platform != "win32":
    import resource

REPLAY_RATE_HZ = 10.0
REPLAY_DEADLINE_MS = 100.0


class SnapshotSink(Protocol):
    def publish(self, result: FrameResult) -> None: ...
    def close(self) -> None: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drishti-2.5 LiDAR mapping and optional sequence association"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("replay", "demo"):
        command = commands.add_parser(name)
        command.add_argument("--config", type=Path)
        command.add_argument(
            "--output",
            required=True,
            type=Path,
            help="new run directory, outside the source dataset",
        )
        command.add_argument("--mode", choices=list(Mode), default=Mode.GEOMETRIC, type=Mode)
        command.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
        command.add_argument("--view", choices=("none", "record", "spawn"), default="none")
        command.add_argument(
            "--frnet-runtime",
            choices=("torch", "authors"),
            default="torch",
            help="torch: in-process FRNet on --device (needs --extra model); "
            "authors: pinned mmdet3d CPU worker (Linux reference)",
        )
        command.add_argument(
            "--frnet-precision",
            choices=("fp32", "fp16"),
            default="fp32",
            help="torch runtime only; fp16 autocast needs --device cuda (measured speed option)",
        )
        command.add_argument(
            "--frnet-gpu-interpolation",
            action="store_true",
            help="torch runtime only; run FRNet's range interpolation on the GPU",
        )
        command.add_argument("--frnet-python", type=Path)
        command.add_argument("--frnet-source", type=Path)
        command.add_argument("--frnet-checkpoint", type=Path)
        command.add_argument("--frnet-checkpoint-sha256")
        command.add_argument("--frnet-weights-npz", type=Path)
        command.add_argument("--frnet-weights-sha256")
        command.add_argument(
            "--detect-obstacles",
            action="store_true",
            help="emit evidence-only CPU obstacle candidates in learned mode",
        )
        command.add_argument(
            "--track-obstacles",
            action="store_true",
            help="associate observed thing candidates across frames; velocity remains unknown",
        )
        command.add_argument("--max-tracks", type=int, default=MAX_TRACKS)
        command.add_argument(
            "--audit-every",
            type=int,
            default=100,
            help="deep-audit every N-th accepted product result (1 = every frame, 0 = never); "
            "light contract checks run on every receipt",
        )
        command.add_argument(
            "--write-visibility-every",
            type=int,
            default=0,
            help="save observed-free cells of every N-th frame for false-free scoring",
        )
        command.add_argument(
            "--visibility",
            action="store_true",
            help="emit current-scan occupied/observed-free/unknown cell evidence; not clearance",
        )
        command.add_argument(
            "--write-panoptic-predictions",
            action="store_true",
            help="write point-aligned SemanticKITTI candidate predictions for offline scoring",
        )
        command.add_argument(
            "--write-predictions",
            action="store_true",
            help="write raw-ID SemanticKITTI .label files under the new run directory",
        )
        command.add_argument(
            "--evaluate-product-contract",
            action="store_true",
            help="validate a versioned product result; not release acceptance",
        )
        if name == "replay":
            command.add_argument(
                "--dataset",
                required=True,
                type=Path,
                help="SemanticKITTI root containing sequences/",
            )
            command.add_argument("--sequence", required=True)
            command.add_argument(
                "--pose-source",
                type=PoseSource,
                default=PoseSource.SLAM,
                choices=(PoseSource.SLAM, PoseSource.KITTI_GT),
            )
            command.add_argument("--start-frame", type=int, default=0)
            command.add_argument("--max-frames", type=int)
            command.add_argument(
                "--check-100ms",
                action="store_true",
                help="pace replay at 10 Hz and check a current-frame receipt; not release proof",
            )
        else:
            command.add_argument("--frames", type=int, default=3)
            command.add_argument("--seed", type=int, default=26053)
    return parser


def synthetic_frames(count: int, seed: int, mode: Mode) -> Iterator[ScanFrame]:
    if count <= 0:
        raise ValueError("demo frame count must be positive")
    rng = np.random.default_rng(seed)
    for index in range(count):
        xy = rng.uniform(-35, 35, (20000, 2))
        ground = np.column_stack([xy, np.full(len(xy), -1.73), rng.uniform(0.1, 0.9, len(xy))])
        wall = np.column_stack(
            [
                rng.uniform(12, 12.1, 1000),
                rng.uniform(-5, 5, 1000),
                rng.uniform(-1.73, 2, 1000),
                np.full(1000, 0.7),
            ]
        )
        points = np.vstack([ground, wall]).astype(np.float32)
        annotations = None
        if mode == Mode.ORACLE:
            raw = np.r_[np.full(len(ground), 40), np.full(len(wall), 50)].astype(np.uint32)
            annotations = decode_semantickitti(raw)
        yield make_frame(
            points,
            sequence="synthetic-plane-wall",
            frame_id=index,
            timestamp_s=index * 0.1,
            annotations=annotations,
        )


def _versions() -> dict[str, str]:
    versions = {}
    for name in (
        "drishti-25",
        "numpy",
        "pypatchworkpp",
        "rerun-sdk",
        "cupy-cuda12x",
        "cupy-cuda13x",
    ):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def _source_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _percentiles(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    result = np.percentile(values, [50, 95, 99], method="linear")
    return dict(zip(("p50", "p95", "p99"), map(float, result), strict=True))


def _run_ready(
    args: argparse.Namespace, predictor: "FRNetPredictor | TorchFRNetPredictor | None"
) -> int:
    config = load_config(args.config)
    mode = Mode(args.mode)
    check_deadline = bool(args.command == "replay" and args.check_100ms)
    if check_deadline and mode != Mode.GEOMETRIC:
        raise ValueError("the 100 ms replay check requires label-free geometric mode")
    if check_deadline and args.view != "none":
        raise ValueError("the 100 ms replay check requires --view none; measure Rerun separately")
    output = args.output.expanduser().resolve()
    metadata: dict[str, object]
    if args.command == "replay":
        root = args.dataset.expanduser().resolve(strict=True)
        if output == root or root in output.parents:
            raise ValueError("output must not resolve into the source dataset")
        source = DatasetSource(
            root,
            args.sequence,
            mode=mode,
            pose_source=args.pose_source,
            max_points=config.max_points,
        )
        if not 0 <= args.start_frame < source.frame_count:
            raise ValueError(f"start_frame must lie in [0, {source.frame_count})")
        if args.max_frames is not None and args.max_frames <= 0:
            raise ValueError("max_frames must be positive")
        expected_frames = (
            min(source.frame_count - args.start_frame, args.max_frames)
            if args.max_frames is not None
            else source.frame_count - args.start_frame
        )
        frames = source.frames(start_frame=args.start_frame, max_frames=args.max_frames)
        metadata = {
            "dataset": str(root),
            "sequence": source.sequence,
            "available_frames": source.frame_count,
            "start_frame": args.start_frame,
            "max_frames": args.max_frames,
            "pose_source": source.pose_source.value,
            "dataset_metadata_hashes": source.metadata_hashes,
            "synthetic": False,
        }
    else:
        if args.frames <= 0:
            raise ValueError("demo frame count must be positive")
        expected_frames = args.frames
        frames = synthetic_frames(args.frames, args.seed, mode)
        metadata = {
            "synthetic": True,
            "seed": args.seed,
            "requested_frames": args.frames,
            "pose_source": PoseSource.SYNTHETIC.value,
        }
    engine = MappingEngine(
        config,
        mode=mode,
        predictor=predictor,
        detector=ConnectedComponentDetector(device=args.device) if args.detect_obstacles else None,
        device=args.device,
        tracker=CandidateTracker(args.max_tracks) if args.track_obstacles else None,
        visibility=CurrentScanVisibility(device=args.device) if args.visibility else None,
    )
    consumer = InProcessFrameConsumer() if check_deadline else None
    product_evaluator = (
        InProcessProductEvaluator(audit_every=args.audit_every)
        if args.evaluate_product_contract or mode == Mode.LEARNED
        else None
    )
    sink: SnapshotSink | None = None
    if args.view != "none":
        try:
            from drishti.visualization import RerunView
        except ModuleNotFoundError as exc:
            raise RuntimeError("Rerun is optional; install it with uv sync --extra viz") from exc
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        **metadata,
        "mode": mode.value,
        "device": args.device,
        "report_schema_version": (
            7
            if args.visibility
            else 6
            if args.track_obstacles
            else 5
            if args.detect_obstacles
            else (4 if mode == Mode.LEARNED else (3 if product_evaluator else 2))
        ),
        "product_result_schema_version": (
            5
            if args.visibility
            else 4
            if args.track_obstacles
            else 3
            if args.detect_obstacles
            else (2 if mode == Mode.LEARNED else (1 if product_evaluator else None))
        ),
        "product_result_stage": (
            "visibility"
            if args.visibility
            else "tracking"
            if args.track_obstacles
            else "candidate"
            if args.detect_obstacles
            else (
                "semantic"
                if mode == Mode.LEARNED
                else ("diagnostic" if product_evaluator else None)
            )
        ),
        "detector": (
            {
                "name": "semantic-connected-components",
                "voxel_width_m": 0.45,
                "scope": "observed-point-candidates",
            }
            if args.detect_obstacles
            else None
        ),
        "model": (
            {
                "name": "FRNet SemanticKITTI",
                "checkpoint_sha256": predictor.checkpoint_sha256,
                "weights_sha256": predictor.weights_sha256,
                "source_revision": FRNET_REVISION,
                "class_map_version": FRNET_CLASS_MAP_VERSION,
                "runtime": args.frnet_runtime,
                "worker_environment": predictor.environment,
                "score_meaning": "uncalibrated maximum softmax score",
                "inference_device": getattr(predictor, "device", "cpu"),
            }
            if predictor is not None
            else None
        ),
        "scope": "single-frame-map-with-sequence-tracks-and-current-scan-visibility"
        if args.visibility
        else "single-frame-map-with-sequence-tracks"
        if args.track_obstacles
        else "single-frame",
        "visibility": (
            {
                "method": VISIBILITY_METHOD,
                **asdict(VisibilitySettings()),
                "evidence_source": "current-scan",
                "free_meaning": (
                    "a ground-terminated current beam crossed the cell at or below tau_free "
                    "above its return with no conflicting return nearby; not clearance, "
                    "drivability or navigation proof"
                ),
                "ground_only_cells": "unknown",
            }
            if args.visibility
            else None
        ),
        "tracker": (
            {
                "method": "map-center-prediction-greedy-v1",
                "capacity": args.max_tracks,
                "history_frames": 2,
                "confirmed_misses_before_expiry": 3,
                "association_confidence": "uncalibrated geometric score",
                "motion": "unknown",
            }
            if args.track_obstacles
            else None
        ),
        "ground_method": engine.ground.method,
        "deskew_status": "unavailable",
        "config": asdict(config),
        "config_digest": config.digest,
        "source_digest": _source_digest(),
        "dependencies": _versions(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": platform.processor(),
        "logical_cpus": os.cpu_count(),
        "view": args.view,
        "coordinate_frame": "map-x-forward-y-left-z-up",
        "vertical_datum": "initial-sensor-origin",
        "percentile_method": "linear",
        "paced_replay": check_deadline,
        "expected_frames": expected_frames,
        "replay_rate_hz": REPLAY_RATE_HZ if check_deadline else None,
        "replay_deadline_ms": REPLAY_DEADLINE_MS if check_deadline else None,
        "replay_capture_event": (
            "scheduled-scan-arrival-on-monotonic-clock" if check_deadline else None
        ),
        "replay_publication_event": (
            "current-frame-inprocess-receipt-diagnostic" if check_deadline else None
        ),
        "replay_consumer": "in-process-current-frame-diagnostic" if check_deadline else None,
        "replay_audit_event": "frame-jsonl-flushed-from-python" if check_deadline else None,
        "replay_viewer_flush_each_frame": False,
        "limits": [
            "no temporal fusion",
            "no motion estimation",
            "no refinement",
            "no clearance or passability verdict",
            "no real-time claim",
        ],
        "prediction_format": (
            "SemanticKITTI uint32 raw semantic IDs, unknown=0" if args.write_predictions else None
        ),
        "panoptic_prediction_format": (
            "SemanticKITTI uint32, lower 16 raw semantic, upper 16 frame-local thing instance"
            if args.write_panoptic_predictions
            else None
        ),
    }
    _write_json(output / "manifest.json", manifest)
    status = "failed"
    processing: list[float] = []
    end_to_end: list[float] = []
    output_age_ms: list[float] = []
    receipt_age_ms: list[float] = []
    product_receipts = 0
    deadline_check_met = False
    peak_snapshot_bytes = 0
    prediction_files = 0
    panoptic_prediction_files = 0
    visibility_files = 0
    flush_ms = 0.0
    run_start = perf_counter()
    try:
        if args.view != "none":
            sink = RerunView(
                recording_path=output / "map.rrd" if args.view == "record" else None,
                spawn=args.view == "spawn",
            )
        with ExitStack() as stack:
            stream = stack.enter_context((output / "frames.jsonl").open("x", encoding="utf-8"))
            timing_stream = (
                stack.enter_context((output / "replay-timing.jsonl").open("x", encoding="utf-8"))
                if check_deadline
                else None
            )
            capture_origin = perf_counter()
            while True:
                if len(processing) == expected_frames:
                    break
                scheduled_capture = None
                if timing_stream is not None:
                    scheduled_capture = capture_origin + len(processing) / REPLAY_RATE_HZ
                    remaining = scheduled_capture - perf_counter()
                    if remaining > 0:
                        sleep(remaining)
                start = perf_counter()
                try:
                    frame = next(frames)
                except StopIteration:
                    break
                loaded = perf_counter()
                result = engine.process(frame)
                processed = perf_counter()
                receipt = consumer.receive(frame, result) if consumer is not None else None
                receipt_ready = perf_counter()
                product_receipt = None
                if product_evaluator is not None:
                    arrival_ns = (
                        round(scheduled_capture * 1_000_000_000)
                        if scheduled_capture is not None
                        else None
                    )
                    if predictor is not None:
                        learned_product = (
                            visibility_product_result
                            if args.visibility
                            else tracking_product_result
                            if args.track_obstacles
                            else candidate_product_result
                            if args.detect_obstacles
                            else semantic_product_result
                        )
                        product = learned_product(
                            frame,
                            result,
                            run_id=output.name,
                            code_revision=manifest["source_digest"],
                            checkpoint_sha256=predictor.checkpoint_sha256,
                            weights_sha256=predictor.weights_sha256,
                            cell_sizes_cm=config.cell_sizes_cm,
                            scheduled_arrival_ns=arrival_ns,
                            backend=engine.device,
                        )
                    else:
                        product = diagnostic_product_result(
                            frame,
                            result,
                            run_id=output.name,
                            code_revision=manifest["source_digest"],
                            backend=engine.device,
                            cell_sizes_cm=config.cell_sizes_cm,
                            scheduled_arrival_ns=arrival_ns,
                        )
                    product_receipt = (
                        engine.receive_tracking(frame, result, product, product_evaluator)
                        if args.track_obstacles
                        else product_evaluator.receive(frame, product)
                    )
                    if product_receipt.status != ReceiptStatus.ACCEPTED:
                        raise ValueError(f"product result rejected: {product_receipt.error_code}")
                    product_receipts += 1
                if args.write_panoptic_predictions:
                    panoptic = panoptic_raw_labels(
                        frame.point_ids,
                        result.observations.point_ids,
                        result.observations.semantic,
                        result.instances,
                    )
                    target = (
                        output
                        / "panoptic"
                        / "sequences"
                        / frame.sequence
                        / "predictions"
                        / f"{frame.frame_id:06d}.label"
                    )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as destination:
                        destination.write(panoptic.tobytes())
                    panoptic_prediction_files += 1
                if (
                    args.write_visibility_every
                    and frame.frame_id % args.write_visibility_every == 0
                ):
                    assert product_receipt is not None
                    _write_free_cells(output, frame, product)
                    visibility_files += 1
                if args.write_predictions:
                    # Accepted IDs are validated input IDs; scatter by sorted lookup.
                    order = np.argsort(frame.point_ids, kind="stable")
                    positions = order[
                        np.searchsorted(frame.point_ids[order], result.observations.point_ids)
                    ]
                    raw = np.zeros(len(frame.point_ids), dtype=np.uint32)
                    raw[positions] = LEARNING_TO_RAW[result.observations.semantic]
                    prediction_path = (
                        output
                        / "predictions"
                        / "sequences"
                        / frame.sequence
                        / "predictions"
                        / f"{frame.frame_id:06d}.label"
                    )
                    prediction_path.parent.mkdir(parents=True, exist_ok=True)
                    with prediction_path.open("xb") as prediction_stream:
                        raw.tofile(prediction_stream)
                    prediction_files += 1
                publish_start = perf_counter()
                viewer_flush_ms = 0.0
                if sink is not None:
                    sink.publish(result)
                published = perf_counter()
                input_hash = hashlib.sha256(frame.points_sensor.tobytes())
                input_hash.update(frame.map_from_sensor.tobytes())
                if mode == Mode.ORACLE and frame.annotations is not None:
                    for array in (
                        frame.annotations.semantic,
                        frame.annotations.motion,
                        frame.annotations.instance,
                    ):
                        input_hash.update(array.tobytes())
                record = {
                    "frame_id": frame.frame_id,
                    "timestamp_s": frame.timestamp_s,
                    "input_digest": input_hash.hexdigest(),
                    "map_digest": (
                        receipt.map_digest if receipt is not None else result.snapshot.digest
                    ),
                    "result_receipt": asdict(receipt) if receipt is not None else None,
                    "product_result_receipt": (
                        asdict(product_receipt) if product_receipt is not None else None
                    ),
                    "semantic_unknown_points": (
                        int(np.count_nonzero(result.observations.semantic == 0))
                        if predictor is not None
                        else None
                    ),
                    "tracks": (
                        [asdict(track) for track in result.tracking.tracks]
                        if result.tracking is not None
                        else None
                    ),
                    "tracking_summary": (
                        asdict(result.tracking.summary) if result.tracking is not None else None
                    ),
                    "visibility_summary": (
                        asdict(result.visibility.summary) if result.visibility is not None else None
                    ),
                    "candidate_instances": (
                        [
                            {
                                "instance_id": item.instance_id,
                                "semantic_id": item.semantic_id,
                                "status": item.status,
                                "bounds_min_m": item.bounds_min_m,
                                "bounds_max_m": item.bounds_max_m,
                                "support_points": len(item.point_ids),
                            }
                            for item in result.instances
                        ]
                        if args.detect_obstacles
                        else None
                    ),
                    "receipt_ms": (
                        (receipt_ready - processed) * 1000 if receipt is not None else None
                    ),
                    "load_process_receipt_ms": (
                        (receipt_ready - start) * 1000 if receipt is not None else None
                    ),
                    "accounting": asdict(result.accounting),
                    "timings_ms": asdict(result.timings),
                    "load_ms": (loaded - start) * 1000,
                    "publication_ms": (published - publish_start) * 1000,
                    "viewer_flush_ms": viewer_flush_ms,
                    "load_process_publish_ms": (published - start) * 1000,
                    "snapshot_array_bytes": result.snapshot.array_bytes,
                    "cells": len(result.snapshot.point_count),
                }
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                report_published = perf_counter()
                processing.append(result.timings.total_ms)
                end_to_end.append((report_published - start) * 1000)
                peak_snapshot_bytes = max(peak_snapshot_bytes, result.snapshot.array_bytes)
                if timing_stream is not None and scheduled_capture is not None:
                    report_age_ms = (report_published - scheduled_capture) * 1000
                    current_receipt_age_ms = (receipt_ready - scheduled_capture) * 1000
                    output_age_ms.append(report_age_ms)
                    receipt_age_ms.append(current_receipt_age_ms)
                    timing_stream.write(
                        json.dumps(
                            {
                                "frame_id": frame.frame_id,
                                "scheduled_arrival_offset_ms": (scheduled_capture - capture_origin)
                                * 1000,
                                "load_start_lag_ms": max(0.0, (start - scheduled_capture) * 1000),
                                "receipt_age_ms": current_receipt_age_ms,
                                "report_output_age_ms": report_age_ms,
                                "deadline_missed": current_receipt_age_ms > REPLAY_DEADLINE_MS,
                                "report_deadline_missed": report_age_ms > REPLAY_DEADLINE_MS,
                            },
                            sort_keys=True,
                            allow_nan=False,
                        )
                        + "\n"
                    )
                    timing_stream.flush()
        status = "completed"
    except KeyboardInterrupt:
        status = "interrupted"
    finally:
        try:
            if sink is not None:
                flush_start = perf_counter()
                sink.close()
                flush_ms = (perf_counter() - flush_start) * 1000
        except (OSError, RuntimeError):
            status = "failed"
            raise
        finally:
            deadline_check_met = bool(
                check_deadline
                and status == "completed"
                and len(receipt_age_ms) == expected_frames
                and all(value <= REPLAY_DEADLINE_MS for value in receipt_age_ms)
            )
            summary = {
                "status": status,
                "frames": len(processing),
                "expected_frames": expected_frames,
                "product_receipts": product_receipts,
                "prediction_files": prediction_files,
                "panoptic_prediction_files": panoptic_prediction_files,
                "visibility_files": visibility_files,
                "cold_processing_ms": processing[0] if processing else None,
                "processing_ms": _percentiles(processing),
                "steady_processing_ms": _percentiles(processing[1:]),
                "end_to_end_with_audit_ms": _percentiles(end_to_end),
                "deadline_misses_with_audit": sum(
                    value > config.frame_budget_ms for value in end_to_end
                ),
                "replay_output_age_ms": _percentiles(output_age_ms),
                "replay_output_age_max_ms": max(output_age_ms, default=None),
                "replay_receipt_age_ms": _percentiles(receipt_age_ms),
                "replay_receipt_age_max_ms": max(receipt_age_ms, default=None),
                "replay_deadline_misses": sum(
                    value > REPLAY_DEADLINE_MS for value in receipt_age_ms
                ),
                "replay_report_deadline_misses": sum(
                    value > REPLAY_DEADLINE_MS for value in output_age_ms
                ),
                "replay_deadline_check_met": deadline_check_met,
                "frame_budget_ms": config.frame_budget_ms,
                "final_viewer_flush_ms": flush_ms,
                "wall_seconds": perf_counter() - run_start,
                "rendering_fps": None,
                "peak_snapshot_array_bytes": peak_snapshot_bytes,
                "worker_peak_rss_bytes": _peak_rss_bytes(),
                "viewer_rss_bytes": None,
                "scratch_bytes": None,
                "realtime_release_gate_met": False,
                "release_gate_note": (
                    "single-frame slice only; full pipeline and real data unverified"
                ),
            }
            _write_json(output / "summary.json", summary)
    scope = (
        "sequence tracks and current-scan visibility"
        if args.visibility
        else "sequence tracks"
        if args.track_obstacles
        else "single-frame map"
    )
    print(f"{status}: {len(processing)} frames; {scope} {mode.value}; reports: {output}")
    if status == "interrupted":
        return 130
    if check_deadline and not deadline_check_met:
        return 2
    return 0


def _write_free_cells(output: Path, frame: ScanFrame, product: ProductFrameResult) -> None:
    """Save one frame's accepted observed-free cells for offline false-free scoring."""
    cells = product.cells
    free = np.flatnonzero(cells.occupancy == Occupancy.OBSERVED_FREE)
    table = product.beam_table
    if table is None:
        raise ValueError("visibility product result has no beam table")
    returns = dict(zip(table.beam_id.tolist(), table.return_map_m.tolist(), strict=True))
    target = output / "visibility" / "sequences" / frame.sequence / f"{frame.frame_id:06d}.npz"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        np.savez(
            stream,
            cell_sizes_cm=np.asarray(cells.cell_sizes_cm, dtype=np.int32),
            level=cells.level[free].astype(np.uint8),
            indices=cells.indices[free].astype(np.int32),
            ray_support=cells.ray_support[free].astype(np.int32),
            free_beam_id=cells.free_beam_id[free].astype(np.int64),
            return_z_m=np.array(
                [returns[int(beam)][2] for beam in cells.free_beam_id[free]], dtype=np.float64
            ),
            map_from_sensor=frame.map_from_sensor,
        )


def _peak_rss_bytes() -> int | None:
    """Peak worker RSS where the platform exposes it; Windows reports it as unmeasured."""
    if sys.platform != "win32":
        scale = 1 if sys.platform == "darwin" else 1024
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
    return None


def _run(args: argparse.Namespace) -> int:
    mode = Mode(args.mode)
    if args.track_obstacles and not args.detect_obstacles:
        raise ValueError("tracking requires --detect-obstacles")
    if args.visibility and not args.track_obstacles:
        raise ValueError("visibility requires --track-obstacles")
    if args.write_visibility_every < 0 or (args.write_visibility_every and not args.visibility):
        raise ValueError("--write-visibility-every needs --visibility and a positive N")
    if not 1 <= args.max_tracks <= MAX_TRACKS:
        raise ValueError(f"--max-tracks must be between 1 and {MAX_TRACKS}")
    if args.max_tracks != MAX_TRACKS and not args.track_obstacles:
        raise ValueError("--max-tracks requires --track-obstacles")
    if args.write_panoptic_predictions and not args.detect_obstacles:
        raise ValueError("panoptic predictions require --detect-obstacles")
    model_options = (
        args.frnet_python,
        args.frnet_source,
        args.frnet_checkpoint,
        args.frnet_checkpoint_sha256,
        args.frnet_weights_npz,
        args.frnet_weights_sha256,
    )
    if mode != Mode.LEARNED:
        if any(value is not None for value in model_options) or args.write_predictions:
            raise ValueError("FRNet options require --mode learned")
        if args.detect_obstacles:
            raise ValueError("obstacle candidates require --mode learned")
        return _run_ready(args, None)
    if args.frnet_runtime == "torch":
        if args.frnet_checkpoint is None or args.frnet_checkpoint_sha256 is None:
            raise ValueError(
                "torch FRNet requires --frnet-checkpoint and --frnet-checkpoint-sha256"
            )
        if any(
            value is not None
            for value in (
                args.frnet_python,
                args.frnet_source,
                args.frnet_weights_npz,
                args.frnet_weights_sha256,
            )
        ):
            raise ValueError("--frnet-python/-source/-weights-* need --frnet-runtime authors")
        try:
            from drishti.frnet_model import TorchFRNetPredictor
        except ModuleNotFoundError as exc:
            raise RuntimeError("torch FRNet needs PyTorch; install with --extra model") from exc
        with TorchFRNetPredictor(
            checkpoint=args.frnet_checkpoint,
            checkpoint_sha256=args.frnet_checkpoint_sha256,
            device=args.device,
            precision=args.frnet_precision,
            gpu_interpolation=args.frnet_gpu_interpolation,
        ) as torch_predictor:
            return _run_ready(args, torch_predictor)
    if args.device != "cpu":
        raise ValueError("the authors' FRNet worker runtime supports CPU only")
    if args.frnet_precision != "fp32" or args.frnet_gpu_interpolation:
        raise ValueError("fp16 and GPU interpolation need --frnet-runtime torch")
    if any(value is None for value in model_options):
        raise ValueError("the authors' FRNet runtime requires all six --frnet-* options")
    with FRNetPredictor(
        python=args.frnet_python,
        source_root=args.frnet_source,
        checkpoint=args.frnet_checkpoint,
        checkpoint_sha256=args.frnet_checkpoint_sha256,
        weights_npz=args.frnet_weights_npz,
        weights_sha256=args.frnet_weights_sha256,
    ) as predictor:
        return _run_ready(args, predictor)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"drishti: {exc}", file=sys.stderr)
        return 1
