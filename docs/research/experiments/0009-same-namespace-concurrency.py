"""Run the LMDB writer and held-open reader under one process namespace."""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--writer", type=Path, required=True)
    parser.add_argument("--reader", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()

    if args.directory.exists() or args.csv.exists():
        raise ValueError("output already exists")
    writer = subprocess.Popen(
        [
            str(args.writer),
            "lmdb",
            str(args.dataset),
            args.sequence,
            "100",
            "100",
            str(args.directory),
            str(args.csv),
        ]
    )
    reader: subprocess.Popen[bytes] | None = None
    try:
        deadline = time.monotonic() + 5
        while not (args.directory / "data.mdb").exists():
            if writer.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("writer did not create LMDB store")
            time.sleep(0.01)
        reader = subprocess.Popen([str(args.reader), str(args.directory), "1", "20000"])
        print(
            f"parent PID {os.getpid()}, writer PID {writer.pid}, reader PID {reader.pid}",
            flush=True,
        )
        writer_code = writer.wait(timeout=30)
        reader_code = reader.wait(timeout=30)
        if writer_code or reader_code:
            raise RuntimeError(f"writer={writer_code}, reader={reader_code}")
    finally:
        if writer.poll() is None:
            writer.terminate()
            writer.wait(timeout=5)
        if reader is not None and reader.poll() is None:
            reader.terminate()
            reader.wait(timeout=5)


if __name__ == "__main__":
    main()
