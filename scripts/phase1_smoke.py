from __future__ import annotations

import argparse
from pathlib import Path

from foveamap.data.audit import audit_nuscenes_mini
from foveamap.runtime import collect_runtime_report, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 1 environment and dataset smoke check")
    parser.add_argument("--dataroot", type=Path, default=None)
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/phase1"))
    parser.add_argument("--full-audit", action="store_true")
    args = parser.parse_args()

    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    runtime = collect_runtime_report(Path.cwd())
    write_json(runtime, args.artifact_dir / "environment.json")
    print(f"environment: {args.artifact_dir / 'environment.json'}")
    print(f"accelerator: {runtime['accelerator']['device']}")

    if args.dataroot is None:
        print("dataroot: skipped (provide --dataroot to run the nuScenes contract audit)")
        return 0

    audit = audit_nuscenes_mini(args.dataroot, max_point_pairs=None if args.full_audit else 3)
    write_json(audit, args.artifact_dir / "dataset_audit.json")
    print(f"dataset audit: {args.artifact_dir / 'dataset_audit.json'}")
    print(f"dataset passed: {audit['passed']}")
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
