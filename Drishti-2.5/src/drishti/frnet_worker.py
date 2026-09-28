"""Isolated FRNet CPU worker. Run by path with the pinned Python 3.8 environment.

This module intentionally does not import the Drishti package. The parent sends only
accepted sensor-frame points, never dataset labels or oracle annotations.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
import types
from importlib import import_module
from pathlib import Path
from typing import Any, cast

import numpy as np

torch = cast(Any, import_module("torch"))
MODELS = cast(Any, import_module("mmdet3d.registry")).MODELS
structures = cast(Any, import_module("mmdet3d.structures"))
Det3DDataSample = structures.Det3DDataSample
LiDARPoints = structures.LiDARPoints
PointData = structures.PointData
Config = cast(Any, import_module("mmengine.config")).Config
init_default_scope = cast(Any, import_module("mmengine.registry")).init_default_scope
import_modules_from_strings = cast(Any, import_module("mmengine.utils")).import_modules_from_strings


def _cpu_syncbn_forward(self: Any, value: Any) -> Any:
    return torch.nn.functional.batch_norm(
        value,
        self.running_mean,
        self.running_var,
        self.weight,
        self.bias,
        training=False,
        momentum=self.momentum,
        eps=self.eps,
    )


def _load_model(source_root: Path, weights_path: Path) -> tuple[Any, Any]:
    sys.path.insert(0, str(source_root.resolve()))
    cfg = Config.fromfile(str(source_root / "configs/frnet/frnet-semantickitti_seg.py"))
    import_modules_from_strings(**cfg.custom_imports)
    init_default_scope("mmdet3d")
    model = MODELS.build(cfg.model)
    with np.load(weights_path, allow_pickle=False) as weights:
        state = {key: torch.from_numpy(weights[key].copy()) for key in weights.files}
    model.load_state_dict(state, strict=True)
    for module in model.modules():
        if isinstance(module, torch.nn.SyncBatchNorm):
            module.forward = types.MethodType(_cpu_syncbn_forward, module)
    model.eval()
    RangeInterpolation = cast(
        Any, import_module("frnet.datasets.transforms.transforms_3d")
    ).RangeInterpolation
    transform = RangeInterpolation(H=64, W=2048, fov_up=3.0, fov_down=-25.0, ignore_index=19)
    return model, transform


def _predict(model: Any, transform: Any, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    sample = Det3DDataSample()
    sample.set_metainfo({"num_points": len(points)})
    sample.gt_pts_seg = PointData()
    augmented = transform.transform({"points": LiDARPoints(points, points_dim=4)})
    data = {
        "inputs": {"points": [augmented["points"].tensor]},
        "data_samples": [sample],
    }
    prepared = model.data_preprocessor(data, training=False)
    with torch.no_grad():
        result = model.predict(prepared["inputs"], prepared["data_samples"])[0]
    logits = result.pts_seg_logits.pts_seg_logits
    if logits.shape != (20, len(points)):
        raise ValueError("FRNet returned an invalid original-point logit shape")
    scores = torch.softmax(logits, dim=0)
    confidence, raw_class = scores.max(dim=0)
    return (
        cast(np.ndarray, raw_class.cpu().numpy().astype(np.uint8)),
        cast(np.ndarray, confidence.cpu().numpy().astype(np.float64)),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--weights-npz", type=Path, required=True)
    args = parser.parse_args()
    model, transform = _load_model(args.source_root, args.weights_npz)
    print(
        json.dumps(
            {
                "status": "ready",
                "protocol": 1,
                "python": sys.version.split()[0],
                "torch": torch.__version__,
                "mmcv": importlib.metadata.version("mmcv"),
                "mmengine": importlib.metadata.version("mmengine"),
                "mmdet3d": importlib.metadata.version("mmdet3d"),
            }
        ),
        flush=True,
    )
    for line in sys.stdin:
        try:
            request = json.loads(line)
            with Path(request["input"]).open("rb") as stream:
                points = np.load(stream, allow_pickle=False)
            if points.ndim != 2 or points.shape[1] != 4 or points.dtype != np.float32:
                raise ValueError("worker input must be float32 (N, 4)")
            if not np.isfinite(points).all():
                raise ValueError("worker input points must be finite")
            raw_class, confidence = _predict(model, transform, points)
            with Path(request["output"]).open("xb") as stream:
                np.savez(stream, raw_class=raw_class, confidence=confidence)
            response = {"status": "ok", "points": len(points)}
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            response = {"status": "error", "error": str(exc)}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
