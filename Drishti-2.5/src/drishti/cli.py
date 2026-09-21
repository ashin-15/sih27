import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import resource
import sys
from collections.abc import Iterator, Sequence
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Protocol

import numpy as np

from drishti.config import load_config
from drishti.contracts import Mode, PoseSource, ScanFrame, make_frame
from drishti.dataset import DatasetSource
from drishti.pipeline import FrameResult, MappingEngine
from drishti.semantics import decode_semantickitti


class SnapshotSink(Protocol):
    def publish(self, result: FrameResult) -> None: ...
    def close(self) -> None: ...


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Drishti-2.5 single-frame CPU mapping")
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
    for name in ("drishti-25", "numpy", "pypatchworkpp", "rerun-sdk"):
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
        frames = synthetic_frames(args.frames, args.seed, mode)
        metadata = {
            "synthetic": True,
            "seed": args.seed,
            "requested_frames": args.frames,
            "pose_source": PoseSource.SYNTHETIC.value,
        }
    engine = MappingEngine(config, mode=mode)
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
    peak_snapshot_bytes = 0
    flush_ms = 0.0
    run_start = perf_counter()
    try:
        if args.view != "none":
            sink = RerunView(
                recording_path=output / "map.rrd" if args.view == "record" else None,
                spawn=args.view == "spawn",
            )
        with (output / "frames.jsonl").open("x", encoding="utf-8") as stream:
            while True:
                start = perf_counter()
                try:
                    frame = next(frames)
                except StopIteration:
                    break
                loaded = perf_counter()
                result = engine.process(frame)
                publish_start = perf_counter()
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
                    "map_digest": result.snapshot.digest,
                    "accounting": asdict(result.accounting),
                    "timings_ms": asdict(result.timings),
                    "load_ms": (loaded - start) * 1000,
                    "publication_ms": (published - publish_start) * 1000,
                    "load_process_publish_ms": (published - start) * 1000,
                    "snapshot_array_bytes": result.snapshot.array_bytes,
                    "cells": len(result.snapshot.point_count),
                }
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                processing.append(result.timings.total_ms)
                end_to_end.append((perf_counter() - start) * 1000)
                peak_snapshot_bytes = max(peak_snapshot_bytes, result.snapshot.array_bytes)
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
            summary = {
                "status": status,
                "frames": len(processing),
                "cold_processing_ms": processing[0] if processing else None,
                "processing_ms": _percentiles(processing),
                "steady_processing_ms": _percentiles(processing[1:]),
                "end_to_end_with_audit_ms": _percentiles(end_to_end),
                "deadline_misses_with_audit": sum(
                    value > config.frame_budget_ms for value in end_to_end
                ),
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
    return 130 if status == "interrupted" else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"drishti: {exc}", file=sys.stderr)
        return 1
