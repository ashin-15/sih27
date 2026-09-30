"""Synthetic CPU vs CUDA stage timing; diagnostic only, not a release or real-data result."""

import statistics
import sys
from time import perf_counter

import numpy as np

sys.path.insert(0, "tests")
from test_cuda_stages import Authored, _frame  # noqa: E402

from drishti.config import MappingConfig  # noqa: E402
from drishti.contracts import Mode  # noqa: E402
from drishti.ground import GroundClass  # noqa: E402
from drishti.obstacles import ConnectedComponentDetector  # noqa: E402
from drishti.pipeline import MappingEngine  # noqa: E402
from drishti.tracking import CandidateTracker  # noqa: E402
from drishti.visibility import CurrentScanVisibility  # noqa: E402

rng = np.random.default_rng(26053)
n_ground, n_obj = 70_000, 50_000
radius = np.sqrt(rng.uniform(3**2, 70**2, n_ground))
angle = rng.uniform(-np.pi, np.pi, n_ground)
ground = np.column_stack((radius * np.cos(angle), radius * np.sin(angle), np.full(n_ground, -1.73)))
centers = rng.uniform(-50, 50, (250, 2))
objects = np.column_stack(
    (
        np.repeat(centers, n_obj // 250, axis=0) + rng.uniform(-1.5, 1.5, (n_obj, 2)),
        rng.uniform(-1.6, 2.0, n_obj),
    )
)
xyz = np.concatenate((ground, objects))
semantic = np.concatenate(
    (np.full(n_ground, 9), rng.choice([1, 13, 15, 18], n_obj))
).astype(np.uint8)
ground_class = np.concatenate(
    (np.full(n_ground, GroundClass.GROUND), np.full(n_obj, GroundClass.NONGROUND))
).astype(np.uint8)
frame = _frame(xyz)
print(f"points={len(xyz)}")
for device in ("cpu", "cuda"):
    authored = Authored(semantic, ground_class)
    detector_ms, visibility_ms = [], []
    for repeat in range(6):
        engine = MappingEngine(
            MappingConfig(),
            mode=Mode.LEARNED,
            predictor=authored,
            ground=authored,
            detector=ConnectedComponentDetector(device=device),
            tracker=CandidateTracker(),
            visibility=CurrentScanVisibility(device=device),
            device=device,
        )
        start = perf_counter()
        result = engine.process(frame)
        wall = (perf_counter() - start) * 1000
        if repeat:  # first run is warmup (kernel compilation, allocator)
            detector_ms.append(result.timings.detector_ms)
            visibility_ms.append(result.timings.visibility_ms)
    assert result.visibility is not None
    print(
        f"{device}: detector p50 {statistics.median(detector_ms):.1f} ms, "
        f"visibility p50 {statistics.median(visibility_ms):.1f} ms, "
        f"candidates {len(result.instances)}, free {result.visibility.summary.free_cells}, "
        f"last total {wall:.1f} ms"
    )
