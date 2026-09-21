import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_installed_cli_replays_dataset_from_another_directory(
    dataset_root: Path, tmp_path: Path
) -> None:
    output = tmp_path / "run"
    command = [
        sys.executable,
        "-m",
        "drishti",
        "replay",
        "--dataset",
        str(dataset_root),
        "--sequence",
        "08",
        "--output",
        str(output),
        "--max-frames",
        "2",
    ]
    completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["mode"] == "geometric"
    assert manifest["scope"] == "single-frame"
    assert manifest["ground_method"] == "patchworkpp"
    assert manifest["pose_source"] == "slam"
    records = [json.loads(line) for line in (output / "frames.jsonl").read_text().splitlines()]
    assert len(records) == 2
    assert all(record["accounting"]["accepted_points"] == 2 for record in records)
    assert all(len(record["map_digest"]) == 64 for record in records)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "completed"
    assert summary["frames"] == 2
    assert summary["rendering_fps"] is None
    repeated = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert repeated.returncode != 0
    assert "exists" in repeated.stderr


def test_output_cannot_be_written_into_the_dataset(dataset_root: Path, tmp_path: Path) -> None:
    alias = tmp_path / "alias"
    alias.symlink_to(dataset_root, target_is_directory=True)
    output = alias / "run"
    command = [
        sys.executable,
        "-m",
        "drishti",
        "replay",
        "--dataset",
        str(dataset_root),
        "--sequence",
        "08",
        "--output",
        str(output),
    ]
    completed = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert completed.returncode != 0
    assert "dataset" in completed.stderr
    assert not output.exists()


def test_failed_replay_saves_failure_summary(dataset_root: Path, tmp_path: Path) -> None:
    from drishti.cli import main

    (dataset_root / "sequences/08/velodyne/000001.bin").write_bytes(b"bad")
    output = tmp_path / "failed"
    assert (
        main(
            ["replay", "--dataset", str(dataset_root), "--sequence", "08", "--output", str(output)]
        )
        == 1
    )
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert summary["frames"] == 1


@pytest.mark.viewer
def test_viewer_flush_failure_cannot_report_success(
    dataset_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("rerun")
    from drishti.cli import main
    from drishti.visualization import RerunView

    original_close = RerunView.close

    def fail_after_close(view: RerunView) -> None:
        original_close(view)
        raise OSError("injected recorder flush failure")

    monkeypatch.setattr(RerunView, "close", fail_after_close)
    output = tmp_path / "failed-flush"
    assert (
        main(
            [
                "replay",
                "--dataset",
                str(dataset_root),
                "--sequence",
                "08",
                "--output",
                str(output),
                "--max-frames",
                "1",
                "--view",
                "record",
            ]
        )
        == 1
    )
    assert json.loads((output / "summary.json").read_text())["status"] == "failed"
