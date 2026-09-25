import argparse
import ctypes
import hashlib
import importlib
import importlib.metadata
import json
import platform
import sys
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter_ns, sleep

import numpy as np


@dataclass(frozen=True)
class Trial:
    case: str
    repetition: int
    duration_ms: float
    interior_python_heartbeats: int


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trials", type=int, default=12)
    args = parser.parse_args()
    if args.trials < 3:
        parser.error("at least three trials are required")
    if args.output.exists():
        parser.error("output must be a new file")

    module = importlib.import_module("pypatchworkpp")
    if module.__file__ is None:
        raise RuntimeError("installed binding has no binary path")
    binary = Path(module.__file__).resolve()
    rng = np.random.default_rng(26053)
    points = np.empty((130_000, 4), dtype=np.float32)
    points[:, :2] = rng.uniform(-60, 60, (len(points), 2))
    points[:, 2] = rng.normal(-1.73, 0.02, len(points))
    points[::10, 2] += 1.5
    points[:, 3] = rng.uniform(0, 1, len(points))
    fortran_points = np.asfortranarray(points)
    estimators = []
    for scan in (points, fortran_points):
        parameters = module.Parameters()
        parameters.sensor_height = 1.73
        parameters.min_range = 2.7
        parameters.max_range = 100.0
        parameters.verbose = False
        estimator = module.patchworkpp(parameters)
        estimator.estimateGround(scan)
        estimators.append(estimator)

    releasing_sleep = ctypes.CDLL(None).usleep
    holding_sleep = ctypes.PyDLL(None).usleep
    for native_sleep in (releasing_sleep, holding_sleep):
        native_sleep.argtypes = [ctypes.c_uint]
        native_sleep.restype = ctypes.c_int

    cases: list[tuple[str, Callable[[], object]]] = [
        ("control_holds_gil", lambda: holding_sleep(40_000)),
        ("estimateGround_c_order", lambda: estimators[0].estimateGround(points)),
        ("control_releases_gil", lambda: releasing_sleep(40_000)),
        ("estimateGround_f_order", lambda: estimators[1].estimateGround(fortran_points)),
    ]
    timestamps: list[int] = []
    ready = threading.Event()
    stop = threading.Event()

    def heartbeat() -> None:
        ready.set()
        while not stop.is_set():
            timestamps.append(perf_counter_ns())
            sleep(0.001)

    previous_interval = sys.getswitchinterval()
    sys.setswitchinterval(0.5)
    witness = threading.Thread(target=heartbeat, name="python-gil-witness")
    witness.start()
    records: list[Trial] = []
    try:
        if not ready.wait(timeout=5):
            raise RuntimeError("heartbeat thread did not start")
        for repetition in range(args.trials):
            rotated = cases[repetition % len(cases) :] + cases[: repetition % len(cases)]
            for name, operation in rotated:
                sleep(0.005)
                first = len(timestamps)
                started = perf_counter_ns()
                operation()
                finished = perf_counter_ns()
                interior = sum(
                    started + 1_000_000 < stamp < finished - 1_000_000
                    for stamp in timestamps[first:]
                )
                records.append(Trial(name, repetition, (finished - started) / 1e6, interior))
    finally:
        stop.set()
        sys.setswitchinterval(previous_interval)
        witness.join(timeout=5)
    if witness.is_alive():
        raise RuntimeError("heartbeat thread did not stop")

    summaries = {}
    for name, _ in cases:
        subset = [record for record in records if record.case == name]
        summaries[name] = {
            "trials": len(subset),
            "duration_ms_min": min(record.duration_ms for record in subset),
            "duration_ms_p50": float(np.median([record.duration_ms for record in subset])),
            "duration_ms_max": max(record.duration_ms for record in subset),
            "trials_with_interior_python_progress": sum(
                record.interior_python_heartbeats > 0 for record in subset
            ),
            "interior_python_heartbeats": [record.interior_python_heartbeats for record in subset],
        }
    controls_valid = (
        summaries["control_holds_gil"]["trials_with_interior_python_progress"] == 0
        and summaries["control_releases_gil"]["trials_with_interior_python_progress"] == args.trials
        and all(5 < record.duration_ms < 400 for record in records)
    )
    report = {
        "scope": "GIL probe only; synthetic input, not replay latency or release acceptance",
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pypatchworkpp": importlib.metadata.version("pypatchworkpp"),
        "binary": str(binary),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_sha256": hashlib.sha256(points.tobytes()).hexdigest(),
        "input_shape": list(points.shape),
        "input_dtype": str(points.dtype),
        "seed": 26053,
        "warmup_calls_per_estimator": 1,
        "python_switch_interval_s": 0.5,
        "heartbeat_sleep_s": 0.001,
        "excluded_boundary_ms": 1.0,
        "controls_valid": controls_valid,
        "ground_counts": [len(estimator.getGroundIndices()) for estimator in estimators],
        "nonground_counts": [len(estimator.getNongroundIndices()) for estimator in estimators],
        "summary": summaries,
        "trials": [asdict(record) for record in records],
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"controls_valid": controls_valid, "summary": summaries}, indent=2))
    return 0 if controls_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
