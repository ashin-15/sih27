import numpy as np
import pytest

from drishti.config import MappingConfig
from drishti.ground import GroundClass, PatchworkGround


@pytest.mark.native
def test_native_ground_has_per_stream_state_and_never_needs_labels() -> None:
    rng = np.random.default_rng(26053)
    xy = rng.uniform(-15, 15, (20000, 2))
    points = np.column_stack([xy, np.full(len(xy), -1.73), np.full(len(xy), 0.5)])
    points = points.astype(np.float32)
    first = PatchworkGround(MappingConfig())
    second = PatchworkGround(MappingConfig())
    result = first.segment(points)
    np.testing.assert_array_equal(result, second.segment(points))
    assert np.count_nonzero(result == GroundClass.GROUND) > 10000
    assert first.method == "patchworkpp"


def test_empty_ground_input_is_supported() -> None:
    result = PatchworkGround(MappingConfig()).segment(np.empty((0, 4), dtype=np.float32))
    assert result.shape == (0,)


def test_invalid_intensity_is_unclassified_not_fabricated_for_ground() -> None:
    points = np.array([[5, 0, -1.73, np.nan], [6, 0, -1.73, np.inf]], dtype=np.float32)
    result = PatchworkGround(MappingConfig()).segment(points)
    assert result.tolist() == [GroundClass.UNKNOWN, GroundClass.UNKNOWN]
    assert np.isnan(points[0, 3])
    assert np.isinf(points[1, 3])
