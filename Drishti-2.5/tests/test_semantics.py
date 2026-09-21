import numpy as np
import pytest

from drishti.semantics import Annotations, decode_semantickitti


def test_packed_raw_car_and_unknown_keep_their_explicit_meanings() -> None:
    packed = np.array([0, 10, 252, (32768 << 16) | 40], dtype=np.uint32)
    annotations = decode_semantickitti(packed)
    np.testing.assert_array_equal(annotations.semantic, [0, 1, 1, 9])
    np.testing.assert_array_equal(annotations.motion, [0, 1, 2, 1])
    np.testing.assert_array_equal(annotations.instance, [0, 0, 0, 32768])


def test_small_raw_ids_are_not_guessed_to_be_learning_ids() -> None:
    annotations = decode_semantickitti(np.array([10], dtype=np.uint32))
    assert annotations.semantic.tolist() == [1]


def test_unsupported_raw_ids_raise_before_narrowing() -> None:
    with pytest.raises(ValueError, match="unsupported raw semantic"):
        decode_semantickitti(np.array([65535], dtype=np.uint32))


def test_annotation_contract_rejects_noncanonical_ids_and_owns_its_arrays() -> None:
    semantic = np.array([1], dtype=np.uint8)
    motion = np.array([1], dtype=np.uint8)
    instance = np.array([0], dtype=np.uint16)
    annotations = Annotations(semantic, motion, instance)
    semantic[0] = 9
    assert annotations.semantic.tolist() == [1]
    with pytest.raises(ValueError, match="semantic"):
        Annotations(np.array([255], dtype=np.uint8), motion, instance)
    with pytest.raises(ValueError, match="motion"):
        Annotations(semantic, np.array([255], dtype=np.uint8), instance)
