"""Compare exact toroidal step implementations on the same fused state."""

import argparse
from time import perf_counter

import numpy as np

from drishti.cli import synthetic_frames
from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.pipeline import MappingEngine
from drishti.temporal import TemporalMap, _Window


def reference(window: _Window, slots: np.ndarray, limit: float) -> tuple[np.ndarray, np.ndarray]:
    size = window.size
    row, column = np.divmod(slots, size)
    keys = window.key[slots]
    height = window.height[slots].astype(np.float64)
    rise = np.zeros(len(slots))
    drop = np.zeros(len(slots))
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        neighbour_row = (row + dx) % size
        neighbour_column = (column + dy) % size
        neighbour = neighbour_row * size + neighbour_column
        target = keys + (dx, dy)
        stored = window.key[neighbour]
        usable = (
            (stored[:, 0] == target[:, 0])
            & (stored[:, 1] == target[:, 1])
            & (window.variance[neighbour] <= limit)
        )
        difference = np.where(usable, window.height[neighbour] - height, 0.0)
        rise = np.maximum(rise, difference)
        drop = np.maximum(drop, -difference)
    return rise, drop


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    if args.frames <= 0 or args.repeats <= 0:
        raise ValueError("frames and repeats must be positive")
    config = MappingConfig()
    engine = MappingEngine(config)
    temporal = TemporalMap(config)
    for frame in synthetic_frames(args.frames, 26053, Mode.GEOMETRIC):
        observations = engine.process(frame).observations
        temporal.update(
            points_map_m=observations.points_map_m,
            ground=observations.ground,
            semantic=observations.semantic,
            sensor_xy_m=frame.map_from_sensor[:2, 3],
            timestamp_ns=round(frame.timestamp_s * 1e9),
        )
    for level, window in enumerate(temporal._windows):
        observed = np.flatnonzero(
            (window.key[:, 0] != np.iinfo(np.int64).min) & (window.last_seen >= 0)
        )
        slots = observed[temporal._owned(level, window.key[observed], frame.map_from_sensor[:2, 3])]
        previous = reference(window, slots, temporal.settings.valid_sigma_m**2)
        current = temporal._steps(window, slots)
        for left, right in zip(previous, current, strict=True):
            np.testing.assert_array_equal(left, right)
        start = perf_counter()
        for _ in range(args.repeats):
            reference(window, slots, temporal.settings.valid_sigma_m**2)
        reference_ms = (perf_counter() - start) * 1000 / args.repeats
        start = perf_counter()
        for _ in range(args.repeats):
            temporal._steps(window, slots)
        current_ms = (perf_counter() - start) * 1000 / args.repeats
        print(
            f"level={level} cells={len(slots)} "
            f"reference={reference_ms:.3f} ms current={current_ms:.3f} ms"
        )


if __name__ == "__main__":
    main()
