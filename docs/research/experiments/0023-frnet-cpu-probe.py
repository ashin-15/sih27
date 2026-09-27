import argparse
import json
import resource
import sys
import types
from pathlib import Path
from time import perf_counter

import numpy as np
import torch
from mmdet3d.registry import MODELS
from mmdet3d.structures import Det3DDataSample, LiDARPoints, PointData
from mmengine.config import Config
from mmengine.registry import init_default_scope
from mmengine.utils import import_modules_from_strings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--weights-npz", type=Path, required=True)
    parser.add_argument("--scan", type=Path, required=True)
    parser.add_argument("--count", type=int)
    parser.add_argument("--check-shuffle", action="store_true")
    parser.add_argument("--labels", type=Path)
    args = parser.parse_args()
    if args.count is not None and args.count < 1:
        raise ValueError("count must be positive")
    sys.path.insert(0, str(args.source_root.resolve()))
    start = perf_counter()
    cfg = Config.fromfile(str(args.source_root / "configs/frnet/frnet-semantickitti_seg.py"))
    import_modules_from_strings(**cfg.custom_imports)
    init_default_scope("mmdet3d")
    model = MODELS.build(cfg.model)
    with np.load(args.weights_npz, allow_pickle=False) as weights:
        state = {key: torch.from_numpy(weights[key]) for key in weights.files}
    model.load_state_dict(state, strict=True)

    def cpu_syncbn_forward(self, value):
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

    for module in model.modules():
        if isinstance(module, torch.nn.SyncBatchNorm):
            module.forward = types.MethodType(cpu_syncbn_forward, module)
    model.eval()
    loaded = perf_counter()

    points = np.fromfile(args.scan, dtype=np.float32).reshape(-1, 4)[: args.count].copy()
    original_count = len(points)
    from frnet.datasets.transforms.transforms_3d import RangeInterpolation

    transform = RangeInterpolation(H=64, W=2048, fov_up=3.0, fov_down=-25.0, ignore_index=19)
    augmented = transform.transform({"points": LiDARPoints(points, points_dim=4)})
    augmented_count = len(augmented["points"])
    sample = Det3DDataSample()
    sample.set_metainfo({"num_points": original_count})
    sample.gt_pts_seg = PointData()
    data = {
        "inputs": {"points": [augmented["points"].tensor]},
        "data_samples": [sample],
    }
    preprocessed = model.data_preprocessor(data, training=False)
    prepared = perf_counter()
    with torch.no_grad():
        predicted = model.predict(preprocessed["inputs"], preprocessed["data_samples"])
    completed = perf_counter()
    labels = predicted[0].pred_pts_seg.pts_semantic_mask.cpu().numpy()
    shuffle_mismatches = None
    quality = None
    if args.labels is not None:
        raw = np.fromfile(args.labels, dtype=np.uint32)[:original_count] & 0xFFFF
        if len(raw) != original_count:
            raise ValueError("label and scan lengths differ")
        target = np.full(original_count, 19, dtype=np.int64)
        for raw_id, training_id in cfg.metainfo.seg_label_mapping.items():
            target[raw == raw_id] = training_id
        valid = target != 19
        confusion = np.bincount(target[valid] * 20 + labels[valid], minlength=400).reshape(20, 20)
        target_present = np.flatnonzero(confusion.sum(axis=1)[:19])
        ious = []
        for class_id in target_present:
            intersection = confusion[class_id, class_id]
            union = confusion[class_id, :].sum() + confusion[:, class_id].sum() - intersection
            ious.append(float(intersection / union))
        quality = {
            "labeled_points": int(valid.sum()),
            "ignored_points": int((~valid).sum()),
            "observed_classes": target_present.tolist(),
            "mean_iou_observed": round(float(np.mean(ious)), 4),
            "point_accuracy": round(float(np.trace(confusion) / confusion.sum()), 4),
        }
    if args.check_shuffle:
        permutation = np.random.default_rng(20260927).permutation(original_count)
        shuffled = transform.transform(
            {"points": LiDARPoints(points[permutation].copy(), points_dim=4)}
        )
        shuffled_sample = Det3DDataSample()
        shuffled_sample.set_metainfo({"num_points": original_count})
        shuffled_sample.gt_pts_seg = PointData()
        shuffled_data = {
            "inputs": {"points": [shuffled["points"].tensor]},
            "data_samples": [shuffled_sample],
        }
        shuffled_preprocessed = model.data_preprocessor(shuffled_data, training=False)
        with torch.no_grad():
            shuffled_output = model.predict(
                shuffled_preprocessed["inputs"], shuffled_preprocessed["data_samples"]
            )
        restored = np.empty_like(labels)
        restored[permutation] = shuffled_output[0].pred_pts_seg.pts_semantic_mask.cpu().numpy()
        shuffle_mismatches = int(np.count_nonzero(labels != restored))
    print(
        json.dumps(
            {
                "original_points": original_count,
                "augmented_points": augmented_count,
                "predicted_points": int(labels.size),
                "label_counts": {
                    str(i): int(v) for i, v in enumerate(np.bincount(labels, minlength=20)) if v
                },
                "load_s": round(loaded - start, 3),
                "preprocess_s": round(prepared - loaded, 3),
                "predict_s": round(completed - prepared, 3),
                "shuffle_mismatches": shuffle_mismatches,
                "single_frame_quality": quality,
                "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
