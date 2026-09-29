"""Offline object-observation association diagnostic, not official LSTQ."""

from collections import Counter

import numpy as np

from drishti.obstacles import InstanceEvidence
from drishti.tracking import TrackEvidence


class AssociationEvaluation:
    """Class-aware >0.5 support IoU matches, >=50-point truth and predictions.

    Association Jaccard averages n(g,p)/(n(g)+n(p)-n(g,p)) over matched
    observations. Counts are object observations, not points; this is not the
    SemanticKITTI LSTQ or HOTA benchmark and must not be presented as either.
    """

    def __init__(self) -> None:
        self._last_frame = -1
        self._gt: Counter[tuple[int, int]] = Counter()
        self._pred: Counter[tuple[int, int]] = Counter()
        self._pairs: Counter[tuple[tuple[int, int], tuple[int, int]]] = Counter()
        self._last_match: dict[tuple[int, int], tuple[int, int]] = {}
        self._last_visible_match: dict[tuple[int, int], bool] = {}
        self._counts: dict[int, Counter[str]] = {label: Counter() for label in range(1, 9)}
        self.frames = 0

    def add_frame(
        self,
        frame_id: int,
        point_ids: np.ndarray,
        gt_semantic: np.ndarray,
        gt_instance: np.ndarray,
        instances: tuple[InstanceEvidence, ...],
        tracks: tuple[TrackEvidence, ...],
    ) -> None:
        if (
            frame_id <= self._last_frame
            or point_ids.ndim != 1
            or gt_semantic.shape != point_ids.shape
            or gt_instance.shape != point_ids.shape
            or len(np.unique(point_ids)) != len(point_ids)
        ):
            raise ValueError("invalid association evaluation frame or point alignment")
        self._last_frame = frame_id
        self.frames += 1
        observed = {t.instance_id: t.track_id for t in tracks if t.instance_id is not None}
        for label in range(1, 9):
            truth: dict[tuple[int, int], set[int]] = {}
            for instance_id in np.unique(gt_instance[gt_semantic == label]):
                if instance_id == 0:
                    continue
                support = set(
                    point_ids[(gt_semantic == label) & (gt_instance == instance_id)].tolist()
                )
                if len(support) >= 50:
                    truth[label, int(instance_id)] = support
            predicted = {
                (label, observed[item.instance_id]): set(item.point_ids)
                for item in instances
                if item.semantic_id == label
                and item.instance_id in observed
                and len(item.point_ids) >= 50
            }
            self._gt.update(truth.keys())
            self._pred.update(predicted.keys())
            matches: list[tuple[float, tuple[int, int], tuple[int, int]]] = []
            for gt_id, gt_support in truth.items():
                for pred_id, pred_support in predicted.items():
                    iou = len(gt_support & pred_support) / len(gt_support | pred_support)
                    if iou > 0.5:
                        matches.append((-iou, gt_id, pred_id))
            matched_gt: dict[tuple[int, int], tuple[int, int]] = {}
            matched_pred: set[tuple[int, int]] = set()
            for _, gt_id, pred_id in sorted(matches):
                if gt_id not in matched_gt and pred_id not in matched_pred:
                    matched_gt[gt_id] = pred_id
                    matched_pred.add(pred_id)
                    self._pairs[gt_id, pred_id] += 1
            counts = self._counts[label]
            counts.update(
                tp=len(matched_gt),
                fp=len(predicted) - len(matched_pred),
                fn=len(truth) - len(matched_gt),
            )
            for gt_id in truth:
                if gt_id in matched_gt:
                    pred_id = matched_gt[gt_id]
                    if gt_id in self._last_match:
                        counts["id_switches"] += self._last_match[gt_id] != pred_id
                        counts["fragmentations"] += not self._last_visible_match[gt_id]
                    self._last_match[gt_id] = pred_id
                self._last_visible_match[gt_id] = gt_id in matched_gt

    def report(self) -> dict[str, object]:
        matched_pred = {pred for _, pred in self._pairs}
        classes: dict[str, object] = {}
        total: Counter[str] = Counter()
        weighted_association = 0.0
        for label, counts in self._counts.items():
            weighted = sum(
                n * n / (self._gt[gt] + self._pred[pred] - n)
                for (gt, pred), n in self._pairs.items()
                if gt[0] == label
            )
            false_tracks = sum(key[0] == label and key not in matched_pred for key in self._pred)
            row = {key: counts[key] for key in ("tp", "fp", "fn", "id_switches", "fragmentations")}
            row["false_tracks"] = false_tracks
            row["gt_tracks"] = sum(key[0] == label for key in self._gt)
            row["predicted_tracks"] = sum(key[0] == label for key in self._pred)
            total.update(row)
            weighted_association += weighted
            classes[str(label)] = {
                **row,
                "association_jaccard": weighted / counts["tp"] if counts["tp"] else None,
            }
        return {
            "method": "object-observation-support-iou-v1",
            "frames": self.frames,
            "min_support_points": 50,
            "match_iou_strictly_greater_than": 0.5,
            "overall": {
                **dict(total),
                "association_jaccard": (
                    weighted_association / total["tp"] if total["tp"] else None
                ),
            },
            "classes": classes,
            "official_LSTQ": False,
        }
