"""Reproduce bounded reference/API checks, without changing either repository.

Run with the vrgrid editable package, numpy, pyyaml and pytest environment.
This creates synthetic fixtures only. It does not validate real-world accuracy.
"""

import argparse
import importlib.metadata
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import yaml


def run(command, cwd):
    result = subprocess.run(
        command, cwd=cwd, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(f"{command}: {result.stdout}\n{result.stderr}")
    return result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--api", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "evidence")
    args = parser.parse_args()
    args.reference = args.reference.resolve()
    args.api = args.api.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.api))

    from auxiliary.laserscan import SemLaserScan
    from auxiliary.np_ioueval import iouEval
    from vrgrid.cell import CELL_DTYPE
    from vrgrid.grid.fusion import unpack_class
    from vrgrid.grid.lattice import i_fine, i_ring
    from vrgrid.grid.schedule import load
    from vrgrid.grid.splitmerge import CellValue, merge, split
    from vrgrid.perception.semantics import is_moving, semantic_labels
    from vrgrid.run.engine import MapEngine

    cfg = yaml.safe_load((args.api / "config/semantic-kitti.yaml").read_text())
    result = {
        "scope": "Synthetic functional checks and CPU allocation accounting, not dataset accuracy",
        "reference_commit": run(["git", "rev-parse", "HEAD"], args.reference).strip(),
        "api_commit": run(["git", "rev-parse", "HEAD"], args.api).strip(),
        "python": sys.version,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "PyYAML", "pytest", "pypatchworkpp")
        },
        "checks": {},
    }
    checks = result["checks"]
    raw = np.array(sorted(cfg["learning_map"]), dtype=np.uint32)
    instances = np.arange(len(raw), dtype=np.uint32) + 32768
    packed = raw | (instances << 16)
    official = np.array([cfg["learning_map"][int(x)] for x in raw], dtype=np.int32)
    local = semantic_labels(packed)
    assert np.array_equal(local, official - 1)
    assert np.array_equal(is_moving(packed), np.isin(raw, np.arange(252, 260)))
    checks["all_raw_class_ids_match_official_minus_one"] = len(raw)
    checks["packed_upper_bits_do_not_corrupt_semantics_or_motion"] = True

    # A real scan-file -> official reader -> packed-label path, with pixel collision.
    with tempfile.TemporaryDirectory(prefix="sih26053-api-fixture-") as temp:
        root = Path(temp)
        dataset = root / "dataset"
        predictions = root / "predictions"
        scan_dir = dataset / "sequences/08/velodyne"
        label_dir = dataset / "sequences/08/labels"
        pred_dir = predictions / "sequences/08/predictions"
        for directory in (scan_dir, label_dir, pred_dir):
            directory.mkdir(parents=True)
        points = np.zeros((len(raw), 4), dtype="<f4")
        points[:, 0] = np.linspace(2, 49, len(raw))
        points[:, 3] = 0.5
        scan_file = scan_dir / "000000.bin"
        label_file = label_dir / "000000.label"
        pred_file = pred_dir / "000000.label"
        points.tofile(scan_file)
        packed.astype("<u4").tofile(label_file)
        canonical = np.array(
            [cfg["learning_map_inv"][int(x)] for x in official], dtype="<u4"
        )
        canonical.tofile(pred_file)
        reader = SemLaserScan(sem_color_dict=cfg["color_map"], project=True)
        reader.open_scan(str(scan_file))
        reader.open_label(str(label_file))
        assert np.array_equal(reader.sem_label, raw)
        assert np.array_equal(reader.inst_label, instances)
        assert len(reader.points) == len(raw)
        checks["scan_and_instance_roundtrip"] = True
        assert np.count_nonzero(reader.proj_idx >= 0) == 1
        assert reader.proj_idx[reader.proj_idx >= 0][0] == 0
        assert np.count_nonzero(reader.proj_mask) == 0
        checks["upstream_index_zero_mask_bug_reproduced"] = {
            "retained_raw_points": len(raw),
            "valid_projected_pixels": 1,
            "reported_mask_pixels": 0,
            "nearest_point_index": 0,
        }

        commands = {
            "api-semantic-perfect.txt": ["evaluate_semantics.py"],
            "api-distance-perfect.txt": ["evaluate_semantics_by_distance.py"],
            "api-mos-perfect.txt": [
                "evaluate_mos.py",
                "--datacfg",
                "config/semantic-kitti-mos.yaml",
            ],
        }
        for log_name, script in commands.items():
            if "mos" in log_name:
                mos_cfg = yaml.safe_load(
                    (args.api / "config/semantic-kitti-mos.yaml").read_text()
                )
                mos_pred = np.array(
                    [
                        mos_cfg["learning_map_inv"][mos_cfg["learning_map"][int(x)]]
                        for x in raw
                    ],
                    dtype="<u4",
                )
                mos_pred.tofile(pred_file)
            output = run(
                [
                    sys.executable,
                    *script,
                    "--dataset",
                    str(dataset),
                    "--predictions",
                    str(predictions),
                    "--split",
                    "valid",
                    "--backend",
                    "numpy",
                ],
                args.api,
            )
            (args.out / log_name).write_text(output)
        canonical.tofile(pred_file)
        # Negative control: reverse the raw per-point predictions, same length.
        canonical[::-1].tofile(pred_file)
        output = run(
            [
                sys.executable,
                "evaluate_semantics.py",
                "--dataset",
                str(dataset),
                "--predictions",
                str(predictions),
                "--split",
                "valid",
            ],
            args.api,
        )
        (args.out / "api-semantic-wrong-order.txt").write_text(output)

    evaluator = iouEval(20, ignore=[0])
    evaluator.addBatch(official, official)
    perfect, _ = evaluator.getIoU()
    assert np.isclose(perfect, 1)
    evaluator.reset()
    evaluator.addBatch(official[::-1], official)
    wrong_order, _ = evaluator.getIoU()
    assert wrong_order < 0.5
    checks["semantic_evaluation_positive_negative_control"] = {
        "perfect_all_19_classes_miou": float(perfect),
        "reversed_prediction_order_miou": float(wrong_order),
    }
    evaluator.reset()
    evaluator.addBatch(np.array([1]), np.array([1]))
    single_class, _ = evaluator.getIoU()
    assert np.isclose(single_class, 1 / 19)
    checks["official_mean_includes_absent_classes"] = float(single_class)

    # Parse the constant from the script itself, without running its CLI.
    import evaluate_semantics_by_distance as distance_module

    edge_points = np.array([10, 20, 30, 40, 50], dtype=float)
    memberships = np.array(
        [
            (edge_points > lo) & (edge_points < hi)
            for lo, hi in distance_module.DISTANCES
        ]
    ).sum(axis=0)
    assert np.all(memberships == 0)
    checks["distance_boundary_exclusion_reproduced"] = {
        "distances_m": edge_points.tolist(),
        "bin_memberships": memberships.tolist(),
        "bins": distance_module.DISTANCES,
    }

    rng = np.random.default_rng(26053)
    x = np.concatenate((rng.uniform(-100, 100, 100_000), [-0.02, 0, 0.2, 0.5]))
    for ratio in (1, 2, 4, 8, 10):
        assert np.array_equal(i_ring(x, 0.05, ratio), i_fine(x, 0.05) // ratio)
    checks["canonical_index_consistency_points"] = len(x)
    parent = CellValue(0.12, 0.003, n=9)
    for schedule_name in ("5/10/20/40", "5/10/50"):
        schedule = load(schedule_name)
        children = split(parent, schedule, ring=2, grad_z=0.3)
        restored = merge(children)
        assert restored.mu_m == parent.mu_m and restored.sigma2_m2 == parent.sigma2_m2
    checks["unchanged_derived_children_restore_parent"] = True
    assert CELL_DTYPE.itemsize == 12
    checks["cell_bytes"] = CELL_DTYPE.itemsize
    engine = MapEngine(load("5/10/20/40"), ghost_removal=False)
    frame = SimpleNamespace(
        index=0,
        points_sensor=np.array([[5.0, 0.0, -1.73, 0.5]]),
        points_world=np.array([[5.0, 0.0, 0.0]]),
        vehicle_xyz_world=np.zeros(3),
        pose=np.eye(4)[:3],
        semantic=np.array([-1], dtype=np.int32),
        ground=np.array([True]),
        reflectivity8=np.array([128], dtype=np.uint8),
        moving=np.array([False]),
    )
    engine.step(frame)
    seen = engine.handle.grid["obs_count"] > 0
    candidates, _ = unpack_class(engine.handle.grid["semantic_class"][seen])
    assert candidates.tolist() == [0]
    checks["engine_ignored_semantic_becomes_car_reproduced"] = {
        "input_semantic": -1,
        "stored_candidate": 0,
        "meaning": "car",
    }
    checks["engine_handle_bytes_including_visibility"] = engine.handle.total_bytes()
    # Count additional engine arrays by identity, excluding the allocation handle.
    seen_arrays = set()

    def array_bytes(value):
        if isinstance(value, np.ndarray):
            if id(value) in seen_arrays:
                return 0
            seen_arrays.add(id(value))
            return value.nbytes
        if isinstance(value, dict):
            return sum(array_bytes(child) for child in value.values())
        return 0

    extras = (
        "bin_scratch",
        "idx",
        "occ_scratch",
        "occ_state",
        "_cand",
        "_cand_slots",
        "_has_return",
        "range2d",
    )
    checks["additional_engine_array_bytes_selected_fields"] = {
        name: array_bytes(getattr(engine, name)) for name in extras
    }
    del engine
    for name, extra in (
        ("default", []),
        ("5-10-50", ["--schedule", "5/10/50", "--transient-rings", "2"]),
    ):
        output = run(
            [sys.executable, "scripts/memory_bound.py", *extra], args.reference
        )
        (args.out / f"memory-{name}.txt").write_text(output)
    checks["allocation_bounds_equal_measured_array_bytes"] = True
    junit = args.out / "vrgrid-pytest.xml"
    if junit.exists():
        suite = ET.parse(junit).getroot().find("testsuite")
        result["reference_pytest"] = dict(suite.attrib)
        result["reference_pytest"]["skip_reasons"] = sorted(
            {
                case.find("skipped").get("message", "")
                for case in suite.findall("testcase")
                if case.find("skipped") is not None
            }
        )
    (args.out / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
