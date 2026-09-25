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
    assert manifest["device"] == "cpu"
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


def test_paced_replay_checks_each_scan_from_scheduled_arrival(
    dataset_root: Path, tmp_path: Path
) -> None:
    output = tmp_path / "paced"
    config = tmp_path / "map.toml"
    config.write_text("frame_budget_ms = 200.0\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "drishti",
            "replay",
            "--config",
            str(config),
            "--dataset",
            str(dataset_root),
            "--sequence",
            "08",
            "--output",
            str(output),
            "--max-frames",
            "3",
            "--check-100ms",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode in (0, 2), completed.stderr
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["paced_replay"] is True
    assert manifest["replay_rate_hz"] == 10.0
    assert manifest["replay_deadline_ms"] == 100.0
    assert manifest["expected_frames"] == 3
    assert manifest["report_schema_version"] == 2
    assert manifest["replay_publication_event"] == "current-frame-inprocess-receipt-diagnostic"
    assert manifest["replay_audit_event"] == "frame-jsonl-flushed-from-python"
    timings = [
        json.loads(line) for line in (output / "replay-timing.jsonl").read_text().splitlines()
    ]
    assert [timing["frame_id"] for timing in timings] == [0, 1, 2]
    assert [timing["scheduled_arrival_offset_ms"] for timing in timings] == pytest.approx(
        [0.0, 100.0, 200.0]
    )
    assert all(
        timing["report_output_age_ms"] >= timing["receipt_age_ms"] >= timing["load_start_lag_ms"]
        for timing in timings
    )
    records = [json.loads(line) for line in (output / "frames.jsonl").read_text().splitlines()]
    assert all(record["result_receipt"]["frame_id"] == record["frame_id"] for record in records)
    assert all(record["result_receipt"]["map_digest"] == record["map_digest"] for record in records)
    assert all(len(record["result_receipt"]["result_digest"]) == 64 for record in records)
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "completed"
    assert summary["frames"] == 3
    assert summary["expected_frames"] == 3
    assert summary["frame_budget_ms"] == 200.0
    misses = sum(timing["deadline_missed"] for timing in timings)
    report_misses = sum(timing["report_deadline_missed"] for timing in timings)
    assert summary["replay_deadline_misses"] == misses
    assert summary["replay_report_deadline_misses"] == report_misses
    assert summary["replay_receipt_age_max_ms"] == max(
        timing["receipt_age_ms"] for timing in timings
    )
    assert summary["replay_deadline_check_met"] is (misses == 0)
    assert completed.returncode == (0 if misses == 0 else 2)
    assert summary["realtime_release_gate_met"] is False


def test_paced_replay_rejects_oracle_labels(dataset_root: Path, tmp_path: Path) -> None:
    from drishti.cli import main

    output = tmp_path / "oracle-check"
    assert (
        main(
            [
                "replay",
                "--dataset",
                str(dataset_root),
                "--sequence",
                "08",
                "--mode",
                "oracle",
                "--output",
                str(output),
                "--check-100ms",
            ]
        )
        == 1
    )
    assert not output.exists()


def test_paced_replay_excludes_rerun(dataset_root: Path, tmp_path: Path) -> None:
    from drishti.cli import main

    output = tmp_path / "paced-recording"
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
                "2",
                "--view",
                "record",
                "--check-100ms",
            ]
        )
        == 1
    )
    assert not output.exists()


def test_cuda_selection_fails_before_creating_a_run_without_a_device(tmp_path: Path) -> None:
    from drishti.cli import main
    from drishti.cuda_backend import CudaFramePath

    if CudaFramePath.available():
        pytest.skip("CUDA device is available")
    output = tmp_path / "cuda-unavailable"
    assert main(["demo", "--output", str(output), "--device", "cuda", "--frames", "1"]) == 1
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
