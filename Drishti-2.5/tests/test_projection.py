import numpy as np

from drishti.config import MappingConfig
from drishti.projection import project


def test_index_zero_nearest_return_is_valid_and_collision_is_counted() -> None:
    points = np.array([[5.0, 0, 0, 0.2], [10.0, 0, 0, 0.8]], dtype=np.float32)
    image = project(points, np.array([0, 1], dtype=np.int64), MappingConfig())
    assert image.point_ids[image.valid].tolist() == [0]
    assert image.ranges_m[image.valid].tolist() == [5.0]
    assert image.collisions == 1
    assert image.outside_fov == 0


def test_equal_range_ties_use_original_identity_not_array_order() -> None:
    points = np.array([[5.0, 0, 0, 0.2], [5.0, 0, 0, 0.8]], dtype=np.float32)
    ids = np.array([7, 2], dtype=np.int64)
    first = project(points, ids, MappingConfig())
    second = project(points[::-1], ids[::-1], MappingConfig())
    np.testing.assert_array_equal(first.point_ids, second.point_ids)
    assert first.point_ids[first.valid].tolist() == [2]


def test_outside_fov_is_not_clamped_into_a_valid_beam() -> None:
    points = np.array([[5.0, 0, 5.0, 0.2]], dtype=np.float32)
    image = project(points, np.array([0], dtype=np.int64), MappingConfig())
    assert not image.valid.any()
    assert image.outside_fov == 1
