"""Fused sampling arithmetic for the unchanged current-scan corridor rule."""

from typing import Any

import numpy as np

from drishti.arrays import BoolArray, IntArray


def corridor_kernel(cp: Any) -> Any:
    """Return a lazy-compiled kernel; each thread owns one original beam sample."""
    return cp.ElementwiseKernel(
        "int64 owner, int64 step, raw float64 fraction, raw float64 distance, "
        "raw float64 delta, raw int64 ids, float64 ox, float64 oy, "
        "raw int64 ratios, raw float64 widths, raw float64 radii, int64 levels, bool radial",
        "int64 packed, int64 point_id, bool inside",
        r"""
        const double u = fraction[owner] + (double)step * 0.025 / distance[owner];
        const double x = ox + u * delta[owner * 2];
        const double y = oy + u * delta[owner * 2 + 1];
        const long long bx = (long long)floor(x / 0.05);
        const long long by = (long long)floor(y / 0.05);
        long long level = levels - 1;
        for (long long current = levels - 1; current > 0; --current) {
            const long long ratio = ratios[current];
            // C++ division truncates; the reference uses mathematical floor division.
            const long long kx = bx / ratio - (bx % ratio < 0);
            const long long ky = by / ratio - (by % ratio < 0);
            const double width = widths[current];
            const double low_x = (double)kx * width, low_y = (double)ky * width;
            const double dx = fmax(fmax(low_x - ox, ox - (low_x + width)), 0.0);
            const double dy = fmax(fmax(low_y - oy, oy - (low_y + width)), 0.0);
            const double closest = radial ? sqrt(dx * dx + dy * dy) : fmax(dx, dy);
            if (level == current && closest < radii[current - 1]) --level;
        }
        const long long ratio = ratios[level];
        const long long kx = bx / ratio - (bx % ratio < 0);
        const long long ky = by / ratio - (by % ratio < 0);
        const double width = widths[level];
        const double low_x = (double)kx * width, low_y = (double)ky * width;
        inside = u < 1.0 && x - low_x > 1e-6 && low_x + width - x > 1e-6
            && y - low_y > 1e-6 && low_y + width - y > 1e-6;
        packed = (((kx + 33554432LL) << 26) | (ky + 33554432LL)) << 3 | level;
        point_id = ids[owner];
        """,
        "drishti_corridor_samples_v1",
        options=("--fmad=false",),
    )


class CudaConflictQuery:
    """Exact Chebyshev lookup without expanding every conflict into a square."""

    def __init__(self, cp: Any) -> None:
        self.cp = cp
        self.kernel = cp.ElementwiseKernel(
            "int64 x, int64 y, raw int64 sorted_keys, int64 count, int64 steps",
            "bool blocked",
            r"""
            blocked = false;
            for (long long dx = -steps; dx <= steps && !blocked; ++dx) {
                const long long lower = (((x + dx + 33554432LL) << 26)
                    | (y - steps + 33554432LL)) << 3;
                const long long upper = (((x + dx + 33554432LL) << 26)
                    | (y + steps + 33554432LL)) << 3;
                long long lo = 0, hi = count;
                while (lo < hi) {
                    const long long mid = lo + (hi - lo) / 2;
                    if (sorted_keys[mid] < lower) lo = mid + 1;
                    else hi = mid;
                }
                blocked = lo < count && sorted_keys[lo] <= upper;
            }
            """,
            "drishti_conflict_query_v1",
        )

    def near(self, cells: IntArray, conflicts: IntArray, steps: int) -> BoolArray:
        if not len(cells) or not len(conflicts):
            return np.zeros(len(cells), dtype=np.bool_)
        cp = self.cp
        shifted = cp.asarray(conflicts) + (1 << 25)
        keys = cp.sort(((shifted[:, 0] << 26) | shifted[:, 1]) << 3)
        selected = cp.asarray(cells)
        result = self.kernel(
            selected[:, 0], selected[:, 1], keys, np.int64(len(keys)), np.int64(steps)
        )
        return np.asarray(cp.asnumpy(result), dtype=np.bool_)

    def exclude(self, keys: IntArray, occupied: IntArray) -> BoolArray:
        """Return the exact membership complement, including duplicate occupied keys."""
        if not len(keys) or not len(occupied):
            return np.ones(len(keys), dtype=np.bool_)
        cp = self.cp
        selected = cp.asarray(keys)
        ordered = cp.sort(cp.asarray(occupied))
        positions = cp.searchsorted(ordered, selected)
        clipped = cp.minimum(positions, len(ordered) - 1)
        allowed = (positions == len(ordered)) | (ordered[clipped] != selected)
        return np.asarray(cp.asnumpy(allowed), dtype=np.bool_)
