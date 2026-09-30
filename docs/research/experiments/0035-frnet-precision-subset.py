"""FRNet speed-option accuracy on a strided sequence subset (experiment 0035).

Run from Drishti-2.5 with the cuda and model extras. Writes raw-ID prediction files for
every ``--stride``-th scan of sequence 08, for scoring with
``python -m drishti.evaluation --allow-partial``. Labels are never read here.
"""

import argparse
import json
import statistics
from pathlib import Path
from time import perf_counter

import numpy as np

from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.frnet_model import TorchFRNetPredictor
from drishti.semantics import LEARNING_TO_RAW


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--precision", choices=("fp32", "fp16"), default="fp32")
    parser.add_argument("--gpu-interpolation", action="store_true")
    parser.add_argument("--stride", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.output / "predictions" / "sequences" / "08" / "predictions"
    target.mkdir(parents=True, exist_ok=False)
    source = DatasetSource(args.dataset, "08", mode=Mode.LEARNED)
    timings = []
    with TorchFRNetPredictor(
        checkpoint=args.checkpoint,
        checkpoint_sha256=args.checkpoint_sha256,
        device="cuda",
        precision=args.precision,
        gpu_interpolation=args.gpu_interpolation,
    ) as model:
        for frame_id in range(0, source.frame_count, args.stride):
            frame = next(source.frames(start_frame=frame_id, max_frames=1))
            # Whole scans for every configuration, so the three runs are directly comparable.
            started = perf_counter()
            prediction = model.predict(frame.points_sensor, frame.point_ids)
            timings.append((perf_counter() - started) * 1000)
            raw = LEARNING_TO_RAW[prediction.semantic_id].astype(np.uint32)
            raw.tofile(target / f"{frame_id:06d}.label")
        environment = model.environment
    report = {
        "precision": args.precision,
        "gpu_interpolation": args.gpu_interpolation,
        "stride": args.stride,
        "scans": len(timings),
        "model_ms_p50": statistics.median(timings[1:]),
        "environment": environment,
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
