from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import platform
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


RELEVANT_PACKAGES = (
    "nuscenes-devkit",
    "numpy",
    "pandas",
    "torch",
    "torchvision",
    "matplotlib",
    "plotly",
    "open3d",
    "scikit-learn",
    "psutil",
)


def is_kaggle() -> bool:
    return Path("/kaggle/input").exists() or os.environ.get("KAGGLE_KERNEL_RUN_TYPE") is not None


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def git_revision(repo_path: str | Path) -> str | None:
    repo_path = Path(repo_path)
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def cpu_and_memory() -> dict[str, Any]:
    report: dict[str, Any] = {
        "cpu_count_logical": os.cpu_count(),
        "processor": platform.processor() or None,
    }
    try:
        import psutil  # type: ignore

        memory = psutil.virtual_memory()
        report["memory"] = {
            "total_bytes": int(memory.total),
            "available_bytes": int(memory.available),
            "percent_used": float(memory.percent),
        }
    except ImportError:
        report["memory"] = None
    return report


def accelerator_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "torch_available": False,
        "cuda_available": False,
        "device": "cpu",
        "gpus": [],
        "smoke_test": "skipped_no_torch",
    }
    try:
        import torch  # type: ignore
    except ImportError:
        return report

    report["torch_available"] = True
    report["torch_version"] = torch.__version__
    report["torch_cuda_build"] = torch.version.cuda
    try:
        report["cudnn_version"] = torch.backends.cudnn.version()
    except Exception:
        report["cudnn_version"] = None

    if not torch.cuda.is_available():
        report["smoke_test"] = "cpu"
        return report

    report["cuda_available"] = True
    report["device"] = "cuda"
    gpus = []
    for index in range(torch.cuda.device_count()):
        properties = torch.cuda.get_device_properties(index)
        gpus.append(
            {
                "index": index,
                "name": properties.name,
                "major": int(properties.major),
                "minor": int(properties.minor),
                "total_memory_bytes": int(properties.total_memory),
                "multi_processor_count": int(properties.multi_processor_count),
            }
        )
    report["gpus"] = gpus

    try:
        value = torch.arange(4, device="cuda", dtype=torch.float32).sum().item()
        torch.cuda.synchronize()
        report["smoke_test"] = "passed" if value == 6.0 else "unexpected_result"
    except Exception as exc:
        report["smoke_test"] = f"failed:{type(exc).__name__}"
        report["smoke_error"] = str(exc)
    return report


def seed_everything(seed: int = 26053) -> int:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np  # type: ignore
    except ImportError:
        np = None
    if np is not None:
        np.random.seed(seed)
    try:
        import torch  # type: ignore
    except ImportError:
        torch = None
    if torch is not None:
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    return seed


def collect_runtime_report(repo_path: str | Path, seed: int = 26053) -> dict[str, Any]:
    cwd = Path.cwd()
    working = Path("/kaggle/working") if is_kaggle() else cwd / "artifacts"
    working.mkdir(parents=True, exist_ok=True)
    disk = shutil.disk_usage(working)
    return {
        "kaggle": is_kaggle(),
        "python": {
            "version": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "executable": sys.executable,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "packages": {name: package_version(name) for name in RELEVANT_PACKAGES},
        "accelerator": accelerator_report(),
        "resources": {
            **cpu_and_memory(),
            "working_dir": str(working),
            "disk_total_bytes": int(disk.total),
            "disk_free_bytes": int(disk.free),
        },
        "seed": seed_everything(seed),
        "git_sha": git_revision(repo_path),
        "cwd": str(cwd),
    }


def write_json(data: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
