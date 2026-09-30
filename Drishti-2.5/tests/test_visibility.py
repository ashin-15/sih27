"""Frozen T-006 current-scan visibility fixtures (docs/t-006-visibility-proposal.md)."""

from dataclasses import replace
from typing import Any

import numpy as np
import pytest

from drishti.arrays import ByteArray, FloatArray, IntArray, PointArray, immutable
from drishti.cli import main
from drishti.config import MappingConfig
from drishti.contracts import Mode, ScanFrame, make_frame
from drishti.ground import GroundClass
from drishti.learned import SemanticPrediction
from drishti.obstacles import ConnectedComponentDetector
from drishti.pipeline import FrameResult, MappingEngine
from drishti.product_result import (
    EvidenceSource,
    InProcessProductEvaluator,
    Occupancy,
    ProductFrameResult,
    ReceiptStatus,
    _segment_crosses_open_cell,
    _segments_cross_open_cells,
    canonical_result_digest,
    tracking_product_result,
    visibility_product_result,
)
from drishti.tracking import CandidateTracker
from drishti.visibility import CurrentScanVisibility, VisibilitySettings, _near, _near_window

ROAD = 9
Point = tuple[float, float, float, int, int]
Cell = tuple[int, int, int]


def _ground(x: float, y: float, z: float = -1.73, semantic: int = ROAD) -> Point:
    return (x, y, z, semantic, GroundClass.GROUND)


def _nonground(x: float, y: float, z: float, semantic: int) -> Point:
    return (x, y, z, semantic, GroundClass.NONGROUND)


class Authored:
    """Authored semantics and ground classes for accepted fixture points in input order."""

    checkpoint_sha256 = "a" * 64
    weights_sha256 = "b" * 64
    method = "authored-visibility-fixture"

    def __init__(self) -> None:
        self.semantic = np.empty(0, dtype=np.uint8)
        self.ground = np.empty(0, dtype=np.uint8)

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction:
        semantic = self.semantic[point_ids]
        return SemanticPrediction(
            immutable(semantic),
            immutable(np.where(semantic == 0, 0.0, 0.8)),
            immutable((semantic == 0).astype(np.uint8) * 2),
        )

    def segment(self, points: PointArray) -> ByteArray:
        assert len(points) == len(self.ground)
        return immutable(self.ground.copy())

    def close(self) -> None:
        pass


class Harness:
    def __init__(self, settings: VisibilitySettings | None = None) -> None:
        self.authored = Authored()
        self.engine = MappingEngine(
            MappingConfig(),
            mode=Mode.LEARNED,
            predictor=self.authored,
            ground=self.authored,
            detector=ConnectedComponentDetector(),
            tracker=CandidateTracker(),
            visibility=CurrentScanVisibility(settings),
        )
        self.evaluator = InProcessProductEvaluator()
        self.frame_id = 0

    def frame(self, scene: list[Point], pose: FloatArray | None = None) -> ScanFrame:
        values = np.array([point[:3] for point in scene], dtype=np.float64).reshape(-1, 3)
        points = np.column_stack((values, np.full(len(values), 0.5))).astype(np.float32)
        self.authored.semantic = np.array([point[3] for point in scene], dtype=np.uint8)
        self.authored.ground = np.array([point[4] for point in scene], dtype=np.uint8)
        frame = make_frame(
            points,
            sequence="visibility",
            frame_id=self.frame_id,
            timestamp_s=self.frame_id * 0.1,
            map_from_sensor=pose,
        )
        self.frame_id += 1
        return frame

    def step(
        self, scene: list[Point], pose: FloatArray | None = None
    ) -> tuple[ScanFrame, FrameResult, ProductFrameResult]:
        frame = self.frame(scene, pose)
        result = self.engine.process(frame)
        product = _product(frame, result)
        receipt = self.engine.receive_tracking(frame, result, product, self.evaluator)
        assert receipt.status == ReceiptStatus.ACCEPTED, receipt.error_code
        assert receipt.schema_version == 5
        return frame, result, product


def _product(frame: ScanFrame, result: FrameResult) -> ProductFrameResult:
    return visibility_product_result(
        frame,
        result,
        run_id="test",
        code_revision="c" * 64,
        checkpoint_sha256="a" * 64,
        weights_sha256="b" * 64,
        cell_sizes_cm=MappingConfig().cell_sizes_cm,
    )


def _cells(product: ProductFrameResult, state: Occupancy) -> set[Cell]:
    cells = product.cells
    mask = cells.occupancy == state
    return {
        (int(level), int(xy[0]), int(xy[1]))
        for level, xy in zip(cells.level[mask], cells.indices[mask], strict=True)
    }


def _row(product: ProductFrameResult, cell: Cell) -> int:
    keys = [
        (int(level), int(xy[0]), int(xy[1]))
        for level, xy in zip(product.cells.level, product.cells.indices, strict=True)
    ]
    return keys.index(cell)


def _set(product: ProductFrameResult, **arrays: Any) -> ProductFrameResult:
    sealed: dict[str, Any] = {name: immutable(value) for name, value in arrays.items()}
    return replace(product, cells=replace(product.cells, **sealed))


def _rejection(frame: ScanFrame, product: ProductFrameResult) -> str | None:
    receipt = InProcessProductEvaluator().receive(frame, product)
    assert receipt.status == ReceiptStatus.REJECTED
    return receipt.error_code


def test_ground_corridor_free_cells_proof_and_unknown_return_cell() -> None:
    frame, result, product = Harness().step([_ground(20.02, 0.03)])
    assert _cells(product, Occupancy.OBSERVED_FREE) == {(1, x, 0) for x in range(188, 200)}
    assert (1, 200, 0) in _cells(product, Occupancy.UNKNOWN)
    assert product.beam_table is not None and product.beam_table.point_id.tolist() == [0]
    free = product.cells.occupancy == Occupancy.OBSERVED_FREE
    assert np.all(product.cells.ray_support[free] == 1)
    assert np.all(product.cells.free_beam_id[free] == 0)
    assert np.all(product.cells.source == EvidenceSource.CURRENT_SCAN)
    assert result.visibility is not None and result.timings.visibility_ms is not None
    summary = result.visibility.summary
    assert (summary.qualifying_beams, summary.free_cells, summary.unknown_cells) == (1, 12, 1)
    assert summary.deskew_status == frame.deskew_status == "unavailable"


def test_pole_within_margin_blocks_nearby_corridor_cells() -> None:
    _, _, product = Harness().step(
        [
            _ground(20.02, 0.03),
            _nonground(19.5, 0.35, -1.0, 18),
            _nonground(19.5, 0.35, 0.5, 18),
        ]
    )
    assert _cells(product, Occupancy.OBSERVED_FREE) == {(1, x, 0) for x in range(188, 191)}
    assert (1, 195, 3) in _cells(product, Occupancy.OCCUPIED)


def test_steep_beam_and_low_curb() -> None:
    _, _, plain = Harness().step([_ground(3.02, 0.03)])
    assert _cells(plain, Occupancy.OBSERVED_FREE) == {(0, x, 0) for x in range(56, 60)}
    _, _, curb = Harness().step([_ground(3.02, 0.03), _nonground(2.5, 0.03, -1.65, 11)])
    assert _cells(curb, Occupancy.OBSERVED_FREE) == {(0, 58, 0), (0, 59, 0)}
    assert all(x * 0.05 >= 2.8 for _, x, _ in _cells(curb, Occupancy.OBSERVED_FREE))


def test_corridor_is_capped() -> None:
    _, _, product = Harness().step([_ground(90.2, 0.3)])
    free = _cells(product, Occupancy.OBSERVED_FREE)
    assert free == {(2, x, 0) for x in range(170, 180)}
    assert (2, 169, 0) not in free


@pytest.mark.parametrize(
    "scene",
    [
        [_nonground(20.02, 0.03, -1.73, 13)],
        [_ground(20.02, 0.03, semantic=0)],
        [(20.02, 0.03, -1.73, ROAD, GroundClass.UNKNOWN)],
        [_ground(20.02, 0.03, semantic=1)],
        [_ground(2.0, 0.03)],
        [_ground(20.02, 0.03, z=0.5)],
        [],
        [_nonground(10.02, 0.03, 0.0, 13)],
    ],
    ids=[
        "nonground",
        "unknown-semantic",
        "unknown-ground",
        "car-semantic",
        "below-min-range",
        "above-sensor",
        "empty",
        "behind-wall",
    ],
)
def test_invalid_cases_never_become_free(scene: list[Point]) -> None:
    _, result, product = Harness().step(scene)
    assert not _cells(product, Occupancy.OBSERVED_FREE)
    assert product.beam_table is not None and len(product.beam_table.beam_id) == 0
    assert result.visibility is not None and result.visibility.summary.free_cells == 0
    if scene and scene[0][3] == 0:
        assert _cells(product, Occupancy.AMBIGUOUS)
    if scene and scene[0][4] == GroundClass.UNKNOWN:
        # The detector keeps non-GROUND returns as candidates, so candidate support occupies it.
        assert _cells(product, Occupancy.OCCUPIED)


def test_free_capacity_is_explicit() -> None:
    _, result, product = Harness(VisibilitySettings(max_free_cells=3)).step([_ground(20.02, 0.03)])
    assert _cells(product, Occupancy.OBSERVED_FREE) == {(1, x, 0) for x in range(188, 191)}
    assert result.visibility is not None
    assert result.visibility.summary.rejected_free_cells == 9


def test_rotated_translated_pose_maps_free_cells() -> None:
    pose = np.array(
        [[0.0, -1.0, 0.0, 5.0], [1.0, 0.0, 0.0, -3.0], [0.0, 0.0, 1.0, 0.0], [0, 0, 0, 1.0]]
    )
    _, _, product = Harness().step([_ground(20.02, 0.03)], pose)
    assert _cells(product, Occupancy.OBSERVED_FREE) == {
        (1, 49 - 0, x - 30) for x in range(188, 200)
    }


def test_no_carry_over_and_fresh_engine_reproduces_cells() -> None:
    harness = Harness()
    _, _, first = harness.step([_ground(20.02, 0.03)])
    _, _, second = harness.step([_nonground(10.02, 0.03, 0.0, 13)])
    assert _cells(first, Occupancy.OBSERVED_FREE)
    assert not _cells(second, Occupancy.OBSERVED_FREE)
    _, _, again = Harness().step([_ground(20.02, 0.03)])
    for name in ("level", "indices", "occupancy", "ray_support", "free_beam_id"):
        assert np.array_equal(getattr(first.cells, name), getattr(again.cells, name))
    assert first.beam_table is not None and again.beam_table is not None
    for name in ("beam_id", "point_id", "origin_map_m", "return_map_m"):
        np.testing.assert_array_equal(
            getattr(first.beam_table, name), getattr(again.beam_table, name)
        )


def test_evaluator_rejects_unsupported_visibility_claims() -> None:
    frame, _, product = Harness().step([_ground(20.02, 0.03)])
    returned = _row(product, (1, 200, 0))
    occupancy = product.cells.occupancy.copy()
    occupancy[returned] = Occupancy.OBSERVED_FREE
    ray_support = product.cells.ray_support.copy()
    ray_support[returned] = 1
    free_beam = product.cells.free_beam_id.copy()
    free_beam[returned] = 0
    forged = _set(product, occupancy=occupancy, ray_support=ray_support, free_beam_id=free_beam)
    assert _rejection(frame, forged) == "unsupported-free"

    semantic = product.semantic_id.copy()
    semantic[0] = 13
    assert _rejection(frame, replace(product, semantic_id=immutable(semantic))) == (
        "visibility-beam"
    )

    stale = product.cells.occupancy.copy()
    stale[returned] = Occupancy.STALE
    summary = product.visibility_summary
    assert summary is not None
    stale_product = replace(
        _set(product, occupancy=stale),
        visibility_summary=replace(summary, unknown_cells=summary.unknown_cells - 1),
    )
    assert _rejection(frame, stale_product) == "visibility-temporal-claims"

    miscounted = replace(product, visibility_summary=replace(summary, free_cells=13))
    assert _rejection(frame, miscounted) == "visibility-summary"


def test_evaluator_rejects_margin_and_occupancy_forgeries() -> None:
    frame, _, product = Harness().step(
        [
            _ground(20.02, 0.03),
            _nonground(19.5, 0.35, -1.0, 18),
            _nonground(19.5, 0.35, 0.5, 18),
        ]
    )
    summary = product.visibility_summary
    assert summary is not None
    widened = replace(product, visibility_summary=replace(summary, conflict_margin_m=1.0))
    assert _rejection(frame, widened) == "visibility-margin"

    occupancy = product.cells.occupancy.copy()
    occupancy[_row(product, (1, 195, 3))] = Occupancy.UNKNOWN
    hidden = replace(
        _set(product, occupancy=occupancy),
        visibility_summary=replace(
            summary,
            occupied_cells=summary.occupied_cells - 1,
            unknown_cells=summary.unknown_cells + 1,
        ),
    )
    assert _rejection(frame, hidden) == "visibility-occupancy-support"


def test_stage_change_and_guards() -> None:
    harness = Harness()
    harness.step([_ground(20.02, 0.03)])
    frame = harness.frame([_ground(20.02, 0.03)])
    result = harness.engine.process(frame)
    tracking = tracking_product_result(
        frame,
        result,
        run_id="test",
        code_revision="c" * 64,
        checkpoint_sha256="a" * 64,
        weights_sha256="b" * 64,
        cell_sizes_cm=MappingConfig().cell_sizes_cm,
    )
    receipt = harness.evaluator.receive(frame, tracking)
    assert receipt.status == ReceiptStatus.REJECTED
    assert receipt.error_code == "tracking-stage-change"
    with pytest.raises(ValueError, match="visibility requires"):
        MappingEngine(MappingConfig(), visibility=CurrentScanVisibility())
    with pytest.raises(ValueError, match="max_free_cells"):
        VisibilitySettings(max_free_cells=0)
    with pytest.raises(ValueError, match="tau_free_m"):
        VisibilitySettings(tau_free_m=0.0)
    assert main(["demo", "--output", "/tmp/unused-visibility-guard", "--visibility"]) == 1


def test_schema_four_digest_ignores_visibility_summary() -> None:
    frame, result, product = Harness().step([_ground(20.02, 0.03)])
    tracking = tracking_product_result(
        frame,
        result,
        run_id="test",
        code_revision="c" * 64,
        checkpoint_sha256="a" * 64,
        weights_sha256="b" * 64,
        cell_sizes_cm=MappingConfig().cell_sizes_cm,
    )
    assert canonical_result_digest(tracking) == canonical_result_digest(
        replace(tracking, visibility_summary=product.visibility_summary)
    )


@pytest.mark.parametrize("steps", [1, 4, 7])
def test_window_margin_matches_offset_dilation(steps: int) -> None:
    rng = np.random.default_rng(steps)
    cells = rng.integers(-60, 60, (3000, 2)).astype(np.int64)
    conflicts = rng.integers(-90, 90, (400, 2)).astype(np.int64)
    expected = _near(cells, np.unique(conflicts, axis=0), steps)
    np.testing.assert_array_equal(_near_window(cells, conflicts, steps), expected)
    assert expected.any() and not expected.all()


def test_vectorized_crossing_matches_scalar_reference() -> None:
    rng = np.random.default_rng(7)
    start = rng.integers(-4, 5, (4000, 2)).astype(np.float64) * 0.25
    delta = rng.integers(-4, 5, (4000, 2)).astype(np.float64) * 0.25
    low = rng.integers(-4, 4, (4000, 2)).astype(np.float64) * 0.25
    high = low + 0.25
    expected = [
        _segment_crosses_open_cell(s, d, lo, hi)
        for s, d, lo, hi in zip(start, delta, low, high, strict=True)
    ]
    actual = _segments_cross_open_cells(start, delta, low, high)
    np.testing.assert_array_equal(actual, np.array(expected))
    assert actual.any() and not actual.all()


def test_light_receipts_keep_contract_checks_and_sample_the_deep_audit() -> None:
    frame, _, product = Harness().step(
        [
            _ground(20.02, 0.03),
            _nonground(19.5, 0.35, -1.0, 18),
            _nonground(19.5, 0.35, 0.5, 18),
        ]
    )
    summary = product.visibility_summary
    assert summary is not None
    widened = replace(product, visibility_summary=replace(summary, conflict_margin_m=1.0))
    light = InProcessProductEvaluator(audit_every=0).receive(frame, widened)
    assert light.status == ReceiptStatus.ACCEPTED and not light.deep_audit
    miscounted = replace(product, visibility_summary=replace(summary, free_cells=0))
    rejected = InProcessProductEvaluator(audit_every=0).receive(frame, miscounted)
    assert rejected.error_code == "visibility-summary"
    audited = InProcessProductEvaluator(audit_every=5).receive(frame, widened)
    assert audited.deep_audit and audited.error_code == "visibility-margin"
    with pytest.raises(ValueError, match="audit_every"):
        InProcessProductEvaluator(audit_every=-1)


def test_audit_schedule_counts_accepted_frames() -> None:
    harness = Harness()
    harness.evaluator = InProcessProductEvaluator(audit_every=2)
    flags = []
    for _ in range(5):
        frame = harness.frame([_ground(20.02, 0.03)])
        result = harness.engine.process(frame)
        receipt = harness.engine.receive_tracking(
            frame, result, _product(frame, result), harness.evaluator
        )
        assert receipt.status == ReceiptStatus.ACCEPTED
        flags.append(receipt.deep_audit)
    assert flags == [True, False, True, False, True]


def test_schema_five_raw_digest_is_stable_and_value_sensitive() -> None:
    _, _, product = Harness().step([_ground(20.02, 0.03)])
    assert canonical_result_digest(product) == canonical_result_digest(product)
    support = product.cells.ray_support.copy()
    support[-1] += 1
    assert canonical_result_digest(_set(product, ray_support=support)) != canonical_result_digest(
        product
    )
    moved = replace(product, frame_id=product.frame_id + 1)
    assert canonical_result_digest(moved) != canonical_result_digest(product)
