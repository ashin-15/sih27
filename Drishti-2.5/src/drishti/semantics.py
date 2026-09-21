from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray

from drishti.arrays import ByteArray, immutable


class Motion(IntEnum):
    UNKNOWN = 0
    STATIONARY = 1
    MOVING = 2


CLASS_NAMES = (
    "unknown",
    "car",
    "bicycle",
    "motorcycle",
    "truck",
    "other-vehicle",
    "person",
    "bicyclist",
    "motorcyclist",
    "road",
    "parking",
    "sidewalk",
    "other-ground",
    "building",
    "fence",
    "vegetation",
    "trunk",
    "terrain",
    "pole",
    "traffic-sign",
)

RAW_TO_LEARNING = {
    0: 0,
    1: 0,
    10: 1,
    11: 2,
    13: 5,
    15: 3,
    16: 5,
    18: 4,
    20: 5,
    30: 6,
    31: 7,
    32: 8,
    40: 9,
    44: 10,
    48: 11,
    49: 12,
    50: 13,
    51: 14,
    52: 0,
    60: 9,
    70: 15,
    71: 16,
    72: 17,
    80: 18,
    81: 19,
    99: 0,
    252: 1,
    253: 7,
    254: 6,
    255: 8,
    256: 5,
    257: 5,
    258: 4,
    259: 5,
}

_RAW_LUT = np.full(65536, -1, dtype=np.int16)
for _raw, _learning in RAW_TO_LEARNING.items():
    _RAW_LUT[_raw] = _learning
_RAW_LUT.setflags(write=False)


@dataclass(frozen=True)
class Annotations:
    semantic: ByteArray
    motion: ByteArray
    instance: NDArray[np.uint16]

    def __post_init__(self) -> None:
        for name, dtype in (("semantic", np.uint8), ("motion", np.uint8), ("instance", np.uint16)):
            value = getattr(self, name)
            if value.ndim != 1 or value.dtype != dtype or value.shape != self.semantic.shape:
                raise ValueError(
                    f"{name} annotations must be aligned one-dimensional {dtype} arrays"
                )
            object.__setattr__(self, name, immutable(value))
        if np.any(self.semantic >= len(CLASS_NAMES)):
            raise ValueError("semantic annotations must use canonical learning IDs 0..19")
        if np.any(self.motion > Motion.MOVING):
            raise ValueError("motion annotations must use UNKNOWN, STATIONARY or MOVING")


def decode_semantickitti(packed: NDArray[np.uint32]) -> Annotations:
    if packed.ndim != 1 or packed.dtype.kind != "u" or packed.dtype.itemsize != 4:
        raise ValueError("packed SemanticKITTI labels must be a one-dimensional uint32 array")
    raw = packed & 0xFFFF
    learning = _RAW_LUT[raw]
    if np.any(learning < 0):
        bad = np.unique(raw[learning < 0]).tolist()
        raise ValueError(f"unsupported raw semantic IDs: {bad}")
    motion = np.full(len(packed), Motion.STATIONARY, dtype=np.uint8)
    motion[learning == 0] = Motion.UNKNOWN
    motion[(raw >= 252) & (raw <= 259)] = Motion.MOVING
    return Annotations(
        learning.astype(np.uint8),
        motion,
        (packed >> 16).astype(np.uint16),
    )
