"""Profile late diagnostic temporal updates on deterministic synthetic frames."""

import argparse
import cProfile
import pstats

from drishti.cli import synthetic_frames
from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.pipeline import MappingEngine
from drishti.temporal import TemporalMap


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--profile-last", type=int, default=5)
    args = parser.parse_args()
    if not 0 < args.profile_last <= args.frames:
        raise ValueError("profile-last must lie within the frame count")
    config = MappingConfig()
    engine = MappingEngine(config)
    temporal = TemporalMap(config)
    profile = cProfile.Profile()
    for index, frame in enumerate(synthetic_frames(args.frames, 26053, Mode.GEOMETRIC)):
        result = engine.process(frame)
        observations = result.observations
        if index >= args.frames - args.profile_last:
            profile.enable()
        temporal.update(
            points_map_m=observations.points_map_m,
            ground=observations.ground,
            semantic=observations.semantic,
            sensor_xy_m=frame.map_from_sensor[:2, 3],
            timestamp_ns=round(frame.timestamp_s * 1e9),
        )
        profile.disable()
    pstats.Stats(profile).strip_dirs().sort_stats("cumtime").print_stats(30)


if __name__ == "__main__":
    main()
