"""False-free scorer behaviour on authored voxel grids (evaluation only)."""

import numpy as np

from drishti.visibility_evaluation import (
    GRID,
    input_occupancy_iou,
    score_frame,
    unpack_bits,
    voxel_index,
)

CAR_RAW, ROAD_RAW, MOVING_CAR_RAW = 10, 40, 252


def _api_unpack(compressed: np.ndarray) -> np.ndarray:
    """The official semantic-kitti-api unpack routine, verbatim in behaviour."""
    out = np.zeros(compressed.shape[0] * 8, dtype=np.uint8)
    for bit in range(8):
        out[bit::8] = compressed >> (7 - bit) & 1
    return out


def test_unpack_matches_official_api() -> None:
    packed = np.random.default_rng(3).integers(0, 256, 4096, dtype=np.uint8)
    np.testing.assert_array_equal(unpack_bits(packed), _api_unpack(packed).astype(bool))


def test_layout_self_check_recovers_voxelized_scan() -> None:
    rng = np.random.default_rng(5)
    scan = np.column_stack(
        (
            rng.uniform(1, 50, 3000),
            rng.uniform(-25, 25, 3000),
            rng.uniform(-1.9, 4.3, 3000),
            np.zeros(3000),
        )
    ).astype(np.float32)
    index, inside = voxel_index(scan[:, :3].astype(np.float64))
    grid = np.zeros(GRID, dtype=np.bool_)
    grid[tuple(index[inside].T)] = True
    assert input_occupancy_iou(scan, np.packbits(grid.reshape(-1))) == 1.0
    shifted = np.roll(grid, 1, axis=0)
    assert input_occupancy_iou(scan, np.packbits(shifted.reshape(-1))) < 0.5


def _free_cell(x: float, y: float) -> dict[str, np.ndarray]:
    """One 10 cm cell at map (x, y) with a ground return at -1.73 m and identity pose."""
    return {
        "cell_sizes_cm": np.array([5, 10, 50], dtype=np.int32),
        "level": np.array([1], dtype=np.uint8),
        "indices": np.array([[int(x / 0.1), int(y / 0.1)]], dtype=np.int32),
        "ray_support": np.array([1], dtype=np.int32),
        "free_beam_id": np.array([0], dtype=np.int64),
        "return_z_m": np.array([-1.73]),
        "map_from_sensor": np.eye(4),
    }


def _grids() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    labels = np.zeros(GRID, dtype=np.uint16)
    invalid = np.zeros(GRID, dtype=np.bool_)
    occluded = np.zeros(GRID, dtype=np.bool_)
    return labels, invalid, occluded


def test_car_voxel_in_band_is_false_free_and_road_is_not() -> None:
    labels, invalid, occluded = _grids()
    index, _ = voxel_index(np.array([[20.05, 0.05, -1.65]]))
    cx, cy, cz = index[0]
    labels[cx, cy, cz] = CAR_RAW
    result = score_frame(_free_cell(20.0, 0.0), labels.reshape(-1), invalid, occluded, 0.10)
    assert result["inside"][0] and result["verifiable"][0] and result["false_free"][0]
    assert result["blocking_class"][0] == 1
    labels[cx, cy, cz] = ROAD_RAW
    road = score_frame(_free_cell(20.0, 0.0), labels.reshape(-1), invalid, occluded, 0.10)
    assert not road["false_free"][0]
    labels[cx, cy, cz] = MOVING_CAR_RAW
    moving = score_frame(_free_cell(20.0, 0.0), labels.reshape(-1), invalid, occluded, 0.10)
    assert moving["moving_hit"][0] and not moving["false_free"][0]


def test_only_empty_occluded_voxels_count_as_occluded_hits() -> None:
    labels, invalid, occluded = _grids()
    occluded[:] = True
    index, _ = voxel_index(np.array([[20.05, 0.05, -1.75]]))
    labels[tuple(index[0])] = ROAD_RAW
    result = score_frame(_free_cell(20.0, 0.0), labels.reshape(-1), invalid, occluded, 0.10)
    assert result["occluded_hit"][0]
    labels[:] = ROAD_RAW
    ground = score_frame(_free_cell(20.0, 0.0), labels.reshape(-1), invalid, occluded, 0.10)
    assert not ground["occluded_hit"][0]


def test_invalid_voxels_are_unverifiable_and_outside_cells_are_excluded() -> None:
    labels, invalid, occluded = _grids()
    invalid[:] = True
    result = score_frame(_free_cell(20.0, 0.0), labels.reshape(-1), invalid, occluded, 0.10)
    assert result["inside"][0] and not result["verifiable"][0]
    behind = score_frame(_free_cell(-5.0, 0.0), labels.reshape(-1), invalid, occluded, 0.10)
    assert not behind["inside"][0]
