"""Isolated paced MCAP segment recorder, with sealed-file acknowledgements."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
from time import monotonic, perf_counter, sleep, time_ns

import numpy as np
from mcap.reader import make_reader
from mcap.writer import CompressionType, Writer


def summary(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "p50": float(np.percentile(array, 50)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)),
        "max": float(array.max()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--interval-ms", type=float, default=100.0)
    parser.add_argument("--segment-frames", type=int, required=True)
    parser.add_argument("--compression", choices=("none", "zstd"), default="none")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.frames < 2 or args.interval_ms <= 0 or args.segment_frames < 1:
        parser.error("invalid frames, interval or segment size")
    dataset = args.dataset.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    if any(
        path == dataset or dataset in path.parents for path in (output, report_path)
    ):
        parser.error("outputs must be outside the source dataset")
    if output.exists() or report_path.exists():
        parser.error("choose new output paths")
    paths = sorted((dataset / "sequences" / args.sequence / "velodyne").glob("*.bin"))
    if len(paths) < args.frames:
        parser.error("not enough scan files")
    output.mkdir(parents=True, exist_ok=False)
    compression = (
        CompressionType.NONE if args.compression == "none" else CompressionType.ZSTD
    )
    read_ms: list[float] = []
    hash_ms: list[float] = []
    add_ms: list[float] = []
    seal_ms: list[float] = []
    ack_delay_ms: list[float] = []
    schedule_lag_ms: list[float] = []
    expected_hashes: list[str] = []
    segment_beginnings: list[float] = []
    segment_files: list[Path] = []
    stream = None
    writer = None
    channel_id = 0
    segment_path = None
    start = monotonic()
    for index, path in enumerate(paths[: args.frames]):
        due = start + index * args.interval_ms / 1000
        sleep(max(0.0, due - monotonic()))
        began = perf_counter()
        schedule_lag_ms.append((monotonic() - due) * 1000)
        payload = path.read_bytes()
        loaded = perf_counter()
        if len(payload) % 16:
            raise ValueError(f"invalid scan byte length: {path}")
        digest = hashlib.sha256(payload).hexdigest()
        hashed = perf_counter()
        expected_hashes.append(digest)
        if writer is None:
            segment_path = output / f"{index:06d}.mcap"
            partial_path = segment_path.with_suffix(".partial")
            stream = partial_path.open("xb")
            writer = Writer(
                stream,
                chunk_size=8 * 1024 * 1024,
                compression=compression,
                enable_crcs=True,
                enable_data_crcs=True,
            )
            writer.start()
            channel_id = writer.register_channel(
                topic="/drishti/raw_points",
                message_encoding="application/octet-stream",
                schema_id=0,
                metadata={"point_format": "xyzi-f32-le"},
            )
        writer.add_message(
            channel_id=channel_id,
            log_time=time_ns(),
            data=payload,
            publish_time=time_ns(),
            sequence=index,
        )
        added = perf_counter()
        segment_beginnings.append(began)
        read_ms.append((loaded - began) * 1000)
        hash_ms.append((hashed - loaded) * 1000)
        add_ms.append((added - hashed) * 1000)
        if len(segment_beginnings) == args.segment_frames or index == args.frames - 1:
            sealing = perf_counter()
            writer.finish()
            if stream is None or segment_path is None:
                raise AssertionError("segment state missing")
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.replace(segment_path.with_suffix(".partial"), segment_path)
            dir_fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            sealed = perf_counter()
            seal_ms.append((sealed - sealing) * 1000)
            ack_delay_ms.extend((sealed - value) * 1000 for value in segment_beginnings)
            segment_beginnings.clear()
            segment_files.append(segment_path)
            stream = None
            writer = None
    verified = 0
    for segment_file in segment_files:
        with segment_file.open("rb") as source:
            reader = make_reader(source, validate_crcs=True)
            for _, channel, message in reader.iter_messages(log_time_order=False):
                if (
                    channel.topic != "/drishti/raw_points"
                    or message.sequence != verified
                ):
                    raise AssertionError("MCAP channel or message order mismatch")
                if (
                    hashlib.sha256(message.data).hexdigest()
                    != expected_hashes[verified]
                ):
                    raise AssertionError("MCAP payload checksum mismatch")
                verified += 1
    if verified != args.frames:
        raise AssertionError("MCAP scan count mismatch")
    report = {
        "sequence": args.sequence,
        "frames": args.frames,
        "interval_ms": args.interval_ms,
        "segment_frames": args.segment_frames,
        "compression": args.compression,
        "mcap_version": importlib.metadata.version("mcap"),
        "segments": len(segment_files),
        "verified_frames": verified,
        "stored_bytes": sum(path.stat().st_size for path in segment_files),
        "schedule_lag_ms": summary(schedule_lag_ms),
        "read_ms": summary(read_ms),
        "hash_ms": summary(hash_ms),
        "add_ms": summary(add_ms),
        "seal_ms": summary(seal_ms),
        "ack_delay_ms": summary(ack_delay_ms),
    }
    with report_path.open("x", encoding="utf-8") as destination:
        json.dump(report, destination, indent=2, allow_nan=False)
        destination.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
