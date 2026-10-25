"""Same-state dense synthetic neighbour screen, including synchronous transfers.

Run from Drishti-2.5 with its environment; this is not a replay deadline test.
"""

import json
from time import perf_counter

import numpy as np

from drishti.config import MappingConfig
from drishti.temporal import TemporalMap

cpu = TemporalMap(MappingConfig())
gpu = TemporalMap(MappingConfig(), device="cuda")
rng = np.random.default_rng(55)
samples = {"cpu_ms": [], "cuda_ms": []}
windows = []
for window in cpu._windows:
    axis = np.arange(-window.half, window.half + 1, dtype=np.int64)
    keys = np.stack(np.meshgrid(axis, axis, indexing="ij"), axis=-1).reshape(-1, 2)
    slots = window.claim(keys)
    window.height[:] = rng.normal(size=len(slots)).astype(np.float32)
    window.variance[:] = 0
    windows.append((window, slots))
for iteration in range(21):
    results = {}
    order = [("cpu_ms", cpu), ("cuda_ms", gpu)]
    if iteration % 2:
        order.reverse()
    for name, engine in order:
        start = perf_counter()
        results[name] = [engine._steps(window, slots) for window, slots in windows]
        elapsed = (perf_counter() - start) * 1000
        if iteration:
            samples[name].append(elapsed)
    for expected, actual in zip(results["cpu_ms"], results["cuda_ms"], strict=True):
        for left, right in zip(expected, actual, strict=True):
            assert left.tobytes() == right.tobytes()
print(
    json.dumps(
        {
            "workload": "dense synthetic same-state three-level neighbour calculation",
            "parity": "all output bytes equal across 21 iterations",
            "cells_per_level": [len(slots) for _, slots in windows],
            "device_workspace_bytes": gpu.device_workspace_bytes,
            "samples": samples,
            "warm_p50_ms": {name: float(np.median(values)) for name, values in samples.items()},
            "release_acceptance": "NOT VERIFIED; battery-powered isolated screen",
        },
        indent=2,
    )
)
