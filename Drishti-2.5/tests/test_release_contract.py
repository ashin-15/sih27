import pytest

from drishti.release_contract import (
    D005_VERSION,
    DEFAULT_D005,
    ResourceLimits,
    check_evidence_metrics,
    check_resource_sample,
    check_semantic_metrics,
    check_traffic_metrics,
)


def test_d005_semantic_thresholds_require_all_blocking_rows() -> None:
    passed = check_semantic_metrics(
        overall_miou=0.65,
        per_class_iou=(0.10,) * 19,
        supported_range_miou=(0.60, 0.45, 0.20),
        unknown_overall=0.01,
        unknown_by_range=(0.02, 0.02, 0.02),
    )
    assert passed.status == "passed"
    assert DEFAULT_D005.version == D005_VERSION
    assert DEFAULT_D005.status == "approved"

    failed = check_semantic_metrics(
        overall_miou=0.651,
        per_class_iou=(0.10,) * 18 + (0.099,),
        supported_range_miou=(0.60, 0.45, 0.20),
        unknown_overall=0.0,
        unknown_by_range=(0.0, 0.0, 0.0),
    )
    assert failed.status == "failed"
    assert failed.failures == ("per-class-IoU",)

    not_verified = check_semantic_metrics(
        overall_miou=0.7,
        per_class_iou=(0.2,) * 19,
        supported_range_miou=(0.7, None, 0.3),
        unknown_overall=0.0,
        unknown_by_range=(0.0, 0.0, 0.0),
    )
    assert not_verified.status == "not-verified"
    assert "supported-range-mIoU[1]" in not_verified.missing


def test_resource_limits_report_missing_samples_and_reject_overages() -> None:
    missing = check_resource_sample(
        process_rss_bytes=None,
        device_memory_bytes=None,
        swap_delta_bytes=None,
        map_cells=1,
        track_count=1,
        queue_depth=0,
        queue_age_ms=0.0,
    )
    assert missing.status == "not-verified"
    assert "process-rss" in missing.missing
    assert "swap-delta" in missing.missing

    limits = ResourceLimits(
        max_process_rss_bytes=100,
        max_device_memory_bytes=100,
        max_swap_delta_bytes=0,
        max_map_cells=1,
        max_tracks=1,
        max_queue_depth=1,
        max_queue_age_ms=1.0,
        max_receipt_bytes=100,
        max_audit_bytes=100,
        min_disk_free_bytes=100,
    )
    failed = check_resource_sample(
        process_rss_bytes=101,
        device_memory_bytes=None,
        swap_delta_bytes=0,
        map_cells=1,
        track_count=1,
        queue_depth=1,
        queue_age_ms=1.0,
        receipt_bytes=100,
        audit_bytes=100,
        disk_free_bytes=100,
        limits=limits,
    )
    assert failed.status == "failed"
    assert failed.failures == ("process-rss",)

    with pytest.raises(ValueError, match="max_points"):
        ResourceLimits(max_points=0)


def test_traffic_and_evidence_gates_keep_support_and_unknown_rows_explicit() -> None:
    traffic = check_traffic_metrics(
        thing_pq=0.65,
        per_class_recall=(0.70,) * 8,
        range_recall=(0.90, 0.85, 0.70),
        size_recall=(0.85, 0.90, 0.90),
        per_class_support=(100,) * 8,
        range_support=(100,) * 3,
        size_support=(100,) * 3,
        unmatched_candidates_per_100_scans=100,
    )
    assert traffic.status == "passed"

    underpowered = check_traffic_metrics(
        thing_pq=0.90,
        per_class_recall=(1.0,) * 8,
        range_recall=(1.0,) * 3,
        size_recall=(1.0,) * 3,
        per_class_support=(99,) * 8,
        range_support=(100,) * 3,
        size_support=(100,) * 3,
        unmatched_candidates_per_100_scans=0,
    )
    assert underpowered.status == "not-verified"
    assert "per-class traffic support" in underpowered.missing

    fixture = check_evidence_metrics(unsupported_free_cells=0)
    assert fixture.status == "not-verified"
    assert "false-free-rate" in fixture.missing
    failed = check_evidence_metrics(unsupported_free_cells=1)
    assert failed.status == "not-verified"
    assert "unsupported-free-cells" in failed.failures
