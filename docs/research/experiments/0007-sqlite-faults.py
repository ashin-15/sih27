"""Isolated SQLite WAL crash and database-limit recovery experiment."""

import argparse
import hashlib
import json
import multiprocessing
import sqlite3
from pathlib import Path
from typing import Any


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def configure(connection: sqlite3.Connection) -> None:
    if connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
        raise RuntimeError("WAL mode unavailable")
    connection.execute("PRAGMA synchronous=FULL")
    if connection.execute("PRAGMA synchronous").fetchone()[0] != 2:
        raise RuntimeError("FULL synchronization unavailable")


def create(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE scans (frame_id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL, "
        "payload BLOB NOT NULL)"
    )


def write_one(connection: sqlite3.Connection, frame_id: int, payload: bytes) -> None:
    with connection:
        connection.execute(
            "INSERT INTO scans VALUES (?, ?, ?)", (frame_id, digest(payload), payload)
        )


def worker(db_path: str, scan_paths: tuple[str, str], sender: Any) -> None:
    with sqlite3.connect(db_path) as connection:
        configure(connection)
        create(connection)
        write_one(connection, 0, Path(scan_paths[0]).read_bytes())
        sender.send("committed-0")
        connection.execute("BEGIN IMMEDIATE")
        payload = Path(scan_paths[1]).read_bytes()
        connection.execute(
            "INSERT INTO scans VALUES (?, ?, ?)", (1, digest(payload), payload)
        )
        sender.send("uncommitted-1")
        sender.recv()


def scan_ids(connection: sqlite3.Connection) -> list[int]:
    return [
        row[0]
        for row in connection.execute("SELECT frame_id FROM scans ORDER BY frame_id")
    ]


def verify_payloads(connection: sqlite3.Connection, paths: tuple[Path, Path]) -> None:
    for frame_id, stored_hash, payload in connection.execute(
        "SELECT frame_id, sha256, payload FROM scans ORDER BY frame_id"
    ):
        if (
            digest(payload) != stored_hash
            or digest(paths[frame_id].read_bytes()) != stored_hash
        ):
            raise AssertionError("stored payload differs from source")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--sequence", default="08")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    dataset = args.dataset.expanduser().resolve(strict=True)
    output = args.output.expanduser().resolve()
    report_path = args.report.expanduser().resolve()
    if any(
        path == dataset or dataset in path.parents for path in (output, report_path)
    ):
        parser.error("outputs must be outside the source dataset")
    if output.exists() or report_path.exists():
        parser.error("choose new output paths")
    paths = tuple(
        dataset / "sequences" / args.sequence / "velodyne" / f"{index:06d}.bin"
        for index in range(2)
    )
    if not all(path.is_file() for path in paths):
        parser.error("first two scans are unavailable")
    output.mkdir(parents=True, exist_ok=False)
    crash_db = output / "crash.sqlite"
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=True)
    process = context.Process(
        target=worker,
        args=(str(crash_db), (str(paths[0]), str(paths[1])), sender),
    )
    process.start()
    try:
        for expected in ("committed-0", "uncommitted-1"):
            if not receiver.poll(10) or receiver.recv() != expected:
                raise RuntimeError(f"worker did not reach {expected}")
        process.kill()
        process.join(timeout=10)
        if process.is_alive():
            raise RuntimeError("killed worker did not exit")
    finally:
        if process.is_alive():
            process.kill()
            process.join()
        receiver.close()
        sender.close()
    with sqlite3.connect(crash_db) as connection:
        configure(connection)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        ids_after_crash = scan_ids(connection)
        if integrity != "ok" or ids_after_crash != [0]:
            raise AssertionError("committed/uncommitted crash boundary changed")
        verify_payloads(connection, paths)
        write_one(connection, 1, paths[1].read_bytes())
        if scan_ids(connection) != [0, 1]:
            raise AssertionError("recovery did not restore contiguous IDs")
        verify_payloads(connection, paths)
        duplicate_rejected = False
        try:
            write_one(connection, 1, paths[1].read_bytes())
        except sqlite3.IntegrityError:
            duplicate_rejected = True
        if not duplicate_rejected or scan_ids(connection) != [0, 1]:
            raise AssertionError("duplicate frame ID was not rejected")
    limit_db = output / "limit.sqlite"
    with sqlite3.connect(limit_db) as connection:
        configure(connection)
        create(connection)
        write_one(connection, 0, paths[0].read_bytes())
        page_count = connection.execute("PRAGMA page_count").fetchone()[0]
        max_page_count = connection.execute(
            f"PRAGMA max_page_count={page_count + 100}"
        ).fetchone()[0]
        limit_error = None
        try:
            write_one(connection, 1, paths[1].read_bytes())
        except sqlite3.OperationalError as error:
            limit_error = str(error)
        if limit_error is None or scan_ids(connection) != [0]:
            raise AssertionError(
                "database capacity limit did not preserve committed frame"
            )
        verify_payloads(connection, paths)
    with sqlite3.connect(limit_db) as connection:
        limit_integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if limit_integrity != "ok" or scan_ids(connection) != [0]:
            raise AssertionError("limited database failed reopen validation")
    result = {
        "sequence": args.sequence,
        "worker_exit_code": process.exitcode,
        "integrity_after_kill": integrity,
        "ids_after_kill": ids_after_crash,
        "ids_after_resume": [0, 1],
        "duplicate_rejected": duplicate_rejected,
        "page_count_before_limit": page_count,
        "max_page_count": max_page_count,
        "limit_error": limit_error,
        "limit_integrity_after_reopen": limit_integrity,
        "ids_after_limit": [0],
    }
    with report_path.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, indent=2, allow_nan=False)
        destination.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
