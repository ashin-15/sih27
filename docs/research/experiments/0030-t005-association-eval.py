"""Fixed 200-frame T-005 association screen using saved FRNet classes.

Runs the shared map/detector and production tracker algorithm. No fresh model
inference or product receipts are claimed by this offline diagnostic.
"""

import argparse
import hashlib
import importlib.util
import json
import resource
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from time import perf_counter

import numpy as np
from drishti.cli import _source_digest
from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.dataset import DatasetSource
from drishti.obstacles import ConnectedComponentDetector
from drishti.pipeline import MappingEngine
from drishti.tracking import CandidateTracker
from drishti.tracking_evaluation import AssociationEvaluation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--saved-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("choose a new output file")
    module_path = Path(__file__).with_name("0028-t004-saved-prediction-eval.py")
    spec = importlib.util.spec_from_file_location("candidate_screen", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("missing saved-class adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    predictor = module.SavedClasses(args.saved_run)
    source = DatasetSource(args.dataset, "08", mode=Mode.ORACLE)
    engine = MappingEngine(
        MappingConfig(),
        mode=Mode.LEARNED,
        predictor=predictor,
        detector=ConnectedComponentDetector(),
    )
    tracker, evaluator = CandidateTracker(), AssociationEvaluation()
    association_ms: list[float] = []
    lifecycle: Counter[str] = Counter()
    input_hash, annotation_hash, class_hash, track_hash = (
        hashlib.sha256() for _ in range(4)
    )
    rejected_births = 0
    peak_live = 0
    start = perf_counter()
    for frame in source.frames(max_frames=200):
        annotation = frame.annotations
        if annotation is None:
            raise ValueError("evaluation requires independent instance annotations")
        actual = replace(frame, annotations=None)
        result = engine.process(actual)
        before = perf_counter()
        update = tracker.prepare(
            frame.sequence,
            frame.frame_id,
            round(frame.timestamp_s * 1e9),
            result.instances,
        )
        tracker.commit(update)
        association_ms.append((perf_counter() - before) * 1000)
        evaluator.add_frame(
            frame.frame_id,
            frame.point_ids,
            annotation.semantic,
            annotation.instance,
            result.instances,
            update.tracks,
        )
        input_hash.update(frame.points_sensor.tobytes())
        input_hash.update(frame.map_from_sensor.tobytes())
        annotation_hash.update(annotation.semantic.tobytes())
        annotation_hash.update(annotation.instance.tobytes())
        class_hash.update(result.observations.semantic.tobytes())
        track_hash.update(
            json.dumps([asdict(t) for t in update.tracks], sort_keys=True).encode()
        )
        lifecycle.update(t.lifecycle for t in update.tracks)
        rejected_births += len(update.summary.rejected_instance_ids)
        peak_live = max(peak_live, sum(t.lifecycle != "expired" for t in update.tracks))
    if evaluator.frames != 200:
        raise ValueError("fixed 200-frame workload incomplete")
    report = {
        "date": "2026-09-29",
        "sequence": "08",
        "start_frame": 0,
        "end_frame": 199,
        "scope": "saved-class offline association diagnostic; no model inference or receipts",
        "source_digest": _source_digest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_pose_sha256": input_hash.hexdigest(),
        "annotation_sha256": annotation_hash.hexdigest(),
        "accepted_class_sha256": class_hash.hexdigest(),
        "track_trace_sha256": track_hash.hexdigest(),
        "dataset_metadata_hashes": source.metadata_hashes,
        "config_digest": engine.config.digest,
        "capacity": tracker.capacity,
        "peak_live_tracks": peak_live,
        "rejected_births": rejected_births,
        "lifecycle_observations": dict(lifecycle),
        "metrics": evaluator.report(),
        "association_ms": dict(
            zip(
                ("p50", "p95", "p99", "max"),
                map(float, np.percentile(association_ms, [50, 95, 99, 100])),
                strict=True,
            )
        ),
        "parent_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * 1024,
        "wall_seconds": perf_counter() - start,
        "quality_gate_pass": None,
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report["metrics"]["overall"], sort_keys=True))


if __name__ == "__main__":
    main()
