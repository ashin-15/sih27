import importlib
import math
from enum import IntEnum
from typing import Protocol, cast

import numpy as np

from drishti.arrays import ByteArray, IntArray, PointArray, immutable
from drishti.config import MappingConfig


class GroundClass(IntEnum):
    UNKNOWN = 0
    GROUND = 1
    NONGROUND = 2


class GroundSegmenter(Protocol):
    @property
    def method(self) -> str: ...

    def segment(self, points: PointArray) -> ByteArray: ...


class _Parameters(Protocol):
    sensor_height: float
    min_range: float
    max_range: float
    verbose: bool


class _Estimator(Protocol):
    def estimateGround(self, points: PointArray) -> None: ...
    def getGroundIndices(self) -> IntArray: ...
    def getNongroundIndices(self) -> IntArray: ...


class _PatchworkModule(Protocol):
    def Parameters(self) -> _Parameters: ...
    def patchworkpp(self, parameters: _Parameters) -> _Estimator: ...


class PatchworkGround:
    method = "patchworkpp"

    def __init__(self, config: MappingConfig) -> None:
        module = cast(_PatchworkModule, importlib.import_module("pypatchworkpp"))
        parameters = module.Parameters()
        parameters.sensor_height = config.sensor_height_m
        parameters.min_range = config.ground_min_range_m
        parameters.max_range = config.radii_m[-1] * (
            math.sqrt(2) if config.footprint == "square" else 1
        )
        parameters.verbose = False
        self._estimator = module.patchworkpp(parameters)
        self._config = config

    def segment(self, points: PointArray) -> ByteArray:
        if points.ndim != 2 or points.shape[1] != 4:
            raise ValueError("ground segmentation requires (N, 4) points")
        if len(points) > self._config.max_points or not np.isfinite(points[:, :3]).all():
            raise ValueError("ground input exceeds capacity or contains invalid geometry")
        result = np.full(len(points), GroundClass.UNKNOWN, dtype=np.uint8)
        eligible = np.flatnonzero(np.isfinite(points[:, 3]))
        if not len(eligible):
            return immutable(result)
        self._estimator.estimateGround(points[eligible])
        for category, indices in (
            (GroundClass.GROUND, self._estimator.getGroundIndices()),
            (GroundClass.NONGROUND, self._estimator.getNongroundIndices()),
        ):
            indices = np.asarray(indices, dtype=np.int64).reshape(-1)
            if np.any(indices < 0) or np.any(indices >= len(eligible)):
                raise RuntimeError("Patchwork++ returned out-of-bounds point indices")
            original = eligible[indices]
            if np.any(result[original] != GroundClass.UNKNOWN):
                raise RuntimeError("Patchwork++ returned overlapping ground classifications")
            result[original] = category
        return immutable(result)
