import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import sys
from collections.abc import Iterator, Sequence
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from time import perf_counter, sleep
from typing import Protocol

import numpy as np

from drishti.config import load_config
from drishti.contracts import Mode, PoseSource, ScanFrame, make_frame
from drishti.dataset import DatasetSource
from drishti.output import InProcessFrameConsumer
from drishti.pipeline import FrameResult, MappingEngine
from drishti.semantics import decode_semantickitti

REPLAY_RATE_HZ = 10.0
REPLAY_DEADLINE_MS = 100.0


class SnapshotSink(Protocol):
    def publish(self, result: FrameResult) -> None: ...
    def close(self) -> None: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Drishti-2.5 single-frame mapping")
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


def _run(args: argparse.Namespace) -> int:
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
    engine = MappingEngine(config, mode=mode, device=args.device)
    consumer = InProcessFrameConsumer() if check_deadline else None
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
        "report_schema_version": 2,
        "scope": "single-frame",
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
    }
    _write_json(output / "manifest.json", manifest)
    status = "failed"
    processing: list[float] = []
    end_to_end: list[float] = []
    output_age_ms: list[float] = []
    receipt_age_ms: list[float] = []
    deadline_check_met = False
    peak_snapshot_bytes = 0
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
                "worker_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * (1 if sys.platform == "darwin" else 1024),
                "viewer_rss_bytes": None,
                "scratch_bytes": None,
                "realtime_release_gate_met": False,
                "release_gate_note": (
                    "single-frame slice only; full pipeline and real data unverified"
                ),
            }
            _write_json(output / "summary.json", summary)
    print(f"{status}: {len(processing)} frames; single-frame {mode.value}; reports: {output}")
    if status == "interrupted":
        return 130
    if check_deadline and not deadline_check_met:
        return 2
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"drishti: {exc}", file=sys.stderr)
        return 1
