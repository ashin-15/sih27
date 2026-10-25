"""Development-only forward refinement from pose-derived planar speed.

The base ownership is always retained. A forward half-ellipse can only promote
whole coarse blocks; semantic errors therefore cannot coarsen any obstacle.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np

from drishti.arrays import FloatArray

FOVEATION_METHOD = "forward-half-ellipse-refine-only-v1"
MAX_STRETCH = 2.0


@dataclass(frozen=True)
class FoveationState:
    method: str
    speed_mps: float
    heading_xy: tuple[float, float]
    stretch: float
    reason: str

    def __post_init__(self) -> None:
        if (
            self.method != FOVEATION_METHOD
            or not np.isfinite(self.speed_mps)
            or self.speed_mps < 0
            or len(self.heading_xy) != 2
            or not np.isfinite(self.heading_xy).all()
            or not np.isclose(np.hypot(*self.heading_xy), 1, rtol=0, atol=1e-12)
            or not 1 <= self.stretch <= MAX_STRETCH
            or self.reason
            not in ("first-pose", "below-heading-threshold", "pose-derived-uncalibrated")
        ):
            raise ValueError("invalid foveation state")


class FoveationEstimator:
    """Bounded two-pose state; first frame and sub-0.5 m/s use base ownership."""

    def __init__(self) -> None:
        self._sequence: str | None = None
        self._timestamp_ns = -1
        self._xy: FloatArray | None = None

    def update(self, sequence: str, timestamp_ns: int, xy: FloatArray) -> FoveationState:
        if not sequence or (self._sequence is not None and sequence != self._sequence):
            raise ValueError("use a new foveation estimator per sequence")
        if (
            type(timestamp_ns) is not int
            or timestamp_ns <= self._timestamp_ns
            or xy.shape != (2,)
            or not np.isfinite(xy).all()
        ):
            raise ValueError("invalid foveation pose or timestamp")
        speed, heading, stretch, reason = 0.0, (1.0, 0.0), 1.0, "first-pose"
        if self._xy is not None:
            delta = xy - self._xy
            length = float(np.hypot(delta[0], delta[1]))
            speed = length / ((timestamp_ns - self._timestamp_ns) / 1e9)
            reason = "below-heading-threshold"
            if speed >= 0.5:
                heading = (float(delta[0] / length), float(delta[1] / length))
                stretch = 1 + min(speed / 10, MAX_STRETCH - 1)
                reason = "pose-derived-uncalibrated"
        self._sequence, self._timestamp_ns, self._xy = sequence, timestamp_ns, xy.copy()
        return FoveationState(FOVEATION_METHOD, speed, heading, stretch, reason)


def forward_block_distance(
    xp: Any, lower: Any, width: float, sensor: Any, state: FoveationState
) -> Any:
    """Exact minimum ellipse norm over the forward portion of an axis-aligned block.

    The convex quadratic minimum lies on a block edge or at the origin. Each edge
    is clipped to the forward half-plane before minimizing its one-variable form.
    NumPy and CuPy share the arithmetic; no cell-centre approximation is used.
    """
    hx, hy = state.heading_xy
    scale = 1 / state.stretch**2 - 1
    ax, ay, cross = 1 + scale * hx * hx, 1 + scale * hy * hy, scale * hx * hy
    x0, y0 = (lower - sensor).T
    x1, y1 = x0 + width, y0 + width
    minimum = xp.full(len(lower), xp.inf, dtype=xp.float64)
    for fixed in (x0, x1):
        low, high = y0, y1
        if hy > 0:
            low = xp.maximum(low, -hx * fixed / hy)
        elif hy < 0:
            high = xp.minimum(high, -hx * fixed / hy)
        free = xp.minimum(xp.maximum(-cross * fixed / ay, low), high)
        value = ax * fixed * fixed + 2 * cross * fixed * free + ay * free * free
        valid = (low <= high) & ((hx * fixed >= 0) if hy == 0 else True)
        minimum = xp.minimum(minimum, xp.where(valid, value, xp.inf))
    for fixed in (y0, y1):
        low, high = x0, x1
        if hx > 0:
            low = xp.maximum(low, -hy * fixed / hx)
        elif hx < 0:
            high = xp.minimum(high, -hy * fixed / hx)
        free = xp.minimum(xp.maximum(-cross * fixed / ax, low), high)
        value = ax * free * free + 2 * cross * free * fixed + ay * fixed * fixed
        valid = (low <= high) & ((hy * fixed >= 0) if hx == 0 else True)
        minimum = xp.minimum(minimum, xp.where(valid, value, xp.inf))
    contains_origin = (x0 <= 0) & (x1 >= 0) & (y0 <= 0) & (y1 >= 0)
    return xp.sqrt(xp.where(contains_origin, 0.0, xp.maximum(minimum, 0.0)))
