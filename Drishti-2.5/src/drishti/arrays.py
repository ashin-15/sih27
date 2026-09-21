import numpy as np
from numpy.typing import NDArray

type FloatArray = NDArray[np.float64]
type PointArray = NDArray[np.float32]
type IntArray = NDArray[np.int64]
type ByteArray = NDArray[np.uint8]
type BoolArray = NDArray[np.bool_]


def immutable[Scalar: np.generic](values: NDArray[Scalar]) -> NDArray[Scalar]:
    return np.frombuffer(values.tobytes(order="C"), dtype=values.dtype).reshape(values.shape)
