"""Bounded CUDA workspace for exact temporal neighbour calculations.

Fusion remains on the host in this first slice. Transfers and output collection
are synchronous and included in the caller's temporal stage time.
"""

import numpy as np
from numpy.typing import NDArray

from drishti.arrays import BoolArray, FloatArray, IntArray
from drishti.config import MappingConfig
from drishti.cuda_backend import CudaFramePath


class CudaTemporalSteps:
    """Reuse one workspace across all windows of a sequence-owned temporal map."""

    def __init__(self, capacity: int) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("temporal CUDA capacity must be a positive integer")
        self.capacity = capacity
        self.cp = CudaFramePath().cp
        cp = self.cp
        self.keys = cp.empty((capacity, 2), dtype=cp.int64)
        self.height = cp.empty(capacity, dtype=cp.float32)
        self.variance = cp.empty(capacity, dtype=cp.float32)
        self.slots = cp.empty(capacity, dtype=cp.int64)
        self.rise = cp.empty(capacity, dtype=cp.float64)
        self.drop = cp.empty(capacity, dtype=cp.float64)
        self.kernel = cp.ElementwiseKernel(
            "int64 slot, raw int64 keys, raw float32 height, raw float32 variance, "
            "int64 size, float32 limit",
            "float64 rise, float64 drop",
            r"""
            const long long row = slot / size, column = slot % size;
            const long long dx[4] = {1, -1, 0, 0};
            const long long dy[4] = {0, 0, 1, -1};
            double r = 0.0, d = 0.0;
            for (int j = 0; j < 4; ++j) {
                const long long nr = (row + dx[j] + size) % size;
                const long long nc = (column + dy[j] + size) % size;
                const long long neighbour = nr * size + nc;
                const bool usable = keys[2 * neighbour] == keys[2 * slot] + dx[j]
                    && keys[2 * neighbour + 1] == keys[2 * slot + 1] + dy[j]
                    && variance[neighbour] <= limit;
                const double difference = usable
                    ? (double)height[neighbour] - (double)height[slot] : 0.0;
                // Match NumPy maximum's NaN and equal-value/signed-zero behavior.
                r = isnan(r) || r > difference ? r : difference;
                d = isnan(d) || d > -difference ? d : -difference;
            }
            rise = r;
            drop = d;
            """,
            "drishti_temporal_steps_v1",
            options=("--fmad=false",),
        )
        self.ownership_kernel = cp.ElementwiseKernel(
            "int64 x, int64 y, int64 level, raw int64 ratios, raw float64 widths, "
            "raw float64 radii, int64 levels, float64 ox, float64 oy, bool radial",
            "int64 owned",
            r"""
            owned = 1;
            for (long long current = level; current < levels; ++current) {
                if (current == 0) continue;
                const long long bx = x * ratios[level], by = y * ratios[level];
                const long long ratio = ratios[current];
                const long long kx = bx / ratio - (bx % ratio < 0);
                const long long ky = by / ratio - (by % ratio < 0);
                const double width = widths[current];
                const double lx = (double)kx * width, ly = (double)ky * width;
                const double dx = fmax(fmax(lx - ox, ox - (lx + width)), 0.0);
                const double dy = fmax(fmax(ly - oy, oy - (ly + width)), 0.0);
                const double closest = radial ? sqrt(dx * dx + dy * dy) : fmax(dx, dy);
                const bool promoted = closest < radii[current - 1];
                owned = owned && (current == level ? !promoted : promoted);
            }
            """,
            "drishti_temporal_ownership_v1",
            options=("--fmad=false",),
        )

    @property
    def allocated_bytes(self) -> int:
        return sum(
            int(array.nbytes)
            for array in (self.keys, self.height, self.variance, self.slots, self.rise, self.drop)
        )

    def compute(
        self,
        keys: IntArray,
        height: NDArray[np.float32],
        variance: NDArray[np.float32],
        slots: IntArray,
        size: int,
        limit: np.float32,
    ) -> tuple[FloatArray, FloatArray]:
        count = len(slots)
        cells = size * size
        if (
            size < 1
            or cells > self.capacity
            or count > self.capacity
            or keys.shape != (cells, 2)
            or height.shape != (cells,)
            or variance.shape != (cells,)
            or slots.shape != (count,)
            or keys.dtype != np.int64
            or slots.dtype != np.int64
            or height.dtype != np.float32
            or variance.dtype != np.float32
        ):
            raise ValueError("invalid temporal CUDA workspace input or capacity")
        if not count:
            return np.empty(0), np.empty(0)
        if slots.min() < 0 or slots.max() >= cells:
            raise ValueError("temporal CUDA slots outside window")
        self.keys[:cells].set(keys)
        self.height[:cells].set(height)
        self.variance[:cells].set(variance)
        self.slots[:count].set(slots)
        self.kernel(
            self.slots[:count],
            self.keys,
            self.height,
            self.variance,
            np.int64(size),
            limit,
            self.rise[:count],
            self.drop[:count],
        )
        return (
            np.asarray(self.cp.asnumpy(self.rise[:count]), dtype=np.float64),
            np.asarray(self.cp.asnumpy(self.drop[:count]), dtype=np.float64),
        )

    def owned(
        self, level: int, keys: IntArray, sensor: FloatArray, config: MappingConfig
    ) -> BoolArray:
        count = len(keys)
        if count > self.capacity or keys.shape != (count, 2):
            raise ValueError("temporal CUDA ownership capacity exceeded")
        if not count:
            return np.empty(0, dtype=np.bool_)
        cp = self.cp
        self.keys[:count].set(np.ascontiguousarray(keys))
        self.ownership_kernel(
            self.keys[:count, 0],
            self.keys[:count, 1],
            np.int64(level),
            cp.asarray(config.ratios, dtype=cp.int64),
            cp.asarray(config.cell_sizes_cm, dtype=cp.float64) / 100,
            cp.asarray(config.radii_m, dtype=cp.float64),
            np.int64(len(config.ratios)),
            np.float64(sensor[0]),
            np.float64(sensor[1]),
            config.footprint == "radial",
            self.slots[:count],
        )
        return np.asarray(cp.asnumpy(self.slots[:count]), dtype=np.bool_)
