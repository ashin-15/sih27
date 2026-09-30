"""In-process FRNet semantic inference on CPU or CUDA, without mmcv/mmdet3d.

Reimplements only the inference path of FRNet (Xu et al., "FRNet: Frustum-Range Networks
for Scalable LiDAR Segmentation") from the authors' Apache-2.0 source at the pinned
revision ``FRNET_REVISION``: test-time range interpolation, frustum-range preprocessing,
frustum feature encoder, FRNet backbone and FRHead. Auxiliary heads, losses and training
augmentations are not needed for inference and are omitted. Parameter names match the
authors' checkpoint so it loads strictly. Requires the optional ``model`` extra (PyTorch).
"""

from pathlib import Path
from typing import Literal

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor, nn

from drishti.arrays import FloatArray, IntArray, PointArray
from drishti.learned import (
    FRNET_CLASS_MAP_VERSION,
    FRNET_REVISION,
    SemanticPrediction,
    checked_digest,
    remap_frnet_output,
)

TORCH_RUNTIME = "drishti-torch-frnet-v1"
TORCH_CUDA_MEMORY_FRACTION = 0.4
_BN_EPS = 1e-3  # SyncBN(eps=1e-3) in the authors' config; evaluation uses running stats.
_NUM_CLASSES = 20
_RANGE_H, _MODEL_W, _INTERPOLATION_W = 64, 512, 2048
_FOV_UP_DEG, _FOV_DOWN_DEG = 3.0, -25.0


def range_interpolation(points: PointArray) -> PointArray:
    """Vectorized form of the authors' test-time ``RangeInterpolation`` (H=64, W=2048).

    An empty pixel is filled only when both horizontal neighbours were occupied in the
    original projection, so the authors' row-major loop has no order dependence. Their
    ``proj_idx > 0`` test treats the pixel holding point 0 as empty; that is preserved.
    """
    fov_up = _FOV_UP_DEG / 180.0 * np.pi
    fov_down = _FOV_DOWN_DEG / 180.0 * np.pi
    fov = abs(fov_down) + abs(fov_up)
    depth = np.linalg.norm(points[:, :3], 2, axis=1)
    yaw = -np.arctan2(points[:, 1], points[:, 0])
    pitch = np.arcsin(points[:, 2] / depth)
    proj_x = 0.5 * (yaw / np.pi + 1.0) * _INTERPOLATION_W
    proj_y = (1.0 - (pitch + abs(fov_down)) / fov) * _RANGE_H
    column = np.maximum(0, np.minimum(_INTERPOLATION_W - 1, np.floor(proj_x))).astype(np.int64)
    row = np.maximum(0, np.minimum(_RANGE_H - 1, np.floor(proj_y))).astype(np.int64)
    # Farthest first, so the nearest return is written last and wins each pixel; exact depth
    # ties resolve to the lowest point index (the authors' unstable argsort leaves them open).
    order = np.lexsort((np.arange(len(depth)), depth))[::-1]
    index = np.full((_RANGE_H, _INTERPOLATION_W), -1, dtype=np.int64)
    image = np.full((_RANGE_H, _INTERPOLATION_W, 4), -1, dtype=np.float32)
    index[row[order], column[order]] = order
    image[row[order], column[order]] = points[order]
    occupied = index > 0
    fill = np.zeros_like(occupied)
    fill[:, 1:-1] = ~occupied[:, 1:-1] & occupied[:, :-2] & occupied[:, 2:]
    ys, xs = np.nonzero(fill)
    added = (image[ys, xs - 1] + image[ys, xs + 1]) / 2
    return np.concatenate((points, added.astype(np.float32)), axis=0)


def range_interpolation_torch(points: Tensor) -> Tensor:
    """Device form of ``range_interpolation`` with an explicit, deterministic pixel winner.

    Duplicate-index writes are nondeterministic on GPU, so the nearest return (then lowest
    point index) is selected by stable sorts. Device ``atan2``/``arcsin`` rounding can move
    rare points across a pixel edge, so this matches the NumPy reference closely, not exactly.
    """
    fov_up = _FOV_UP_DEG / 180.0 * np.pi
    fov_down = _FOV_DOWN_DEG / 180.0 * np.pi
    fov = abs(fov_down) + abs(fov_up)
    depth = torch.linalg.norm(points[:, :3], 2, dim=1)
    yaw = -torch.atan2(points[:, 1], points[:, 0])
    pitch = torch.arcsin(points[:, 2] / depth)
    proj_x = 0.5 * (yaw / np.pi + 1.0) * _INTERPOLATION_W
    proj_y = (1.0 - (pitch + abs(fov_down)) / fov) * _RANGE_H
    column = torch.clamp(torch.floor(proj_x), 0, _INTERPOLATION_W - 1).long()
    row = torch.clamp(torch.floor(proj_y), 0, _RANGE_H - 1).long()
    pixel = row * _INTERPOLATION_W + column
    by_depth = torch.argsort(depth, stable=True)
    by_pixel = by_depth[torch.argsort(pixel[by_depth], stable=True)]
    sorted_pixel = pixel[by_pixel]
    first = torch.ones_like(sorted_pixel, dtype=torch.bool)
    first[1:] = sorted_pixel[1:] != sorted_pixel[:-1]
    winners = by_pixel[first]
    size = _RANGE_H * _INTERPOLATION_W
    index = torch.full((size,), -1, dtype=torch.long, device=points.device)
    image = torch.full((size, 4), -1.0, dtype=points.dtype, device=points.device)
    index[pixel[winners]] = winners
    image[pixel[winners]] = points[winners]
    occupied = (index > 0).reshape(_RANGE_H, _INTERPOLATION_W)
    image = image.reshape(_RANGE_H, _INTERPOLATION_W, 4)
    fill = torch.zeros_like(occupied)
    fill[:, 1:-1] = ~occupied[:, 1:-1] & occupied[:, :-2] & occupied[:, 2:]
    ys, xs = torch.nonzero(fill, as_tuple=True)
    added = (image[ys, xs - 1] + image[ys, xs + 1]) / 2
    return torch.cat((points, added), dim=0)


def _scatter_max(values: Tensor, inverse: Tensor, groups: int) -> Tensor:
    index = inverse[:, None].expand(-1, values.shape[1])
    empty = values.new_zeros((groups, values.shape[1]))
    return empty.scatter_reduce(0, index, values, reduce="amax", include_self=False)


def _scatter_mean(values: Tensor, inverse: Tensor, groups: int) -> Tensor:
    total = values.new_zeros((groups, values.shape[1])).index_add_(0, inverse, values)
    count = torch.bincount(inverse, minlength=groups).to(values.dtype)
    return total / count[:, None]


def _conv3(inputs: int, outputs: int, stride: int = 1) -> nn.Conv2d:
    return nn.Conv2d(inputs, outputs, 3, stride=stride, padding=1, bias=False)


def _point_layer(inputs: int, outputs: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Linear(inputs, outputs, bias=False),
        nn.BatchNorm1d(outputs, eps=_BN_EPS),
        nn.ReLU(inplace=True),
    )


def _fusion_layer(inputs: int, outputs: int) -> nn.Sequential:
    return nn.Sequential(
        _conv3(inputs, outputs), nn.BatchNorm2d(outputs, eps=_BN_EPS), nn.Hardswish()
    )


class _BasicBlock(nn.Module):
    def __init__(self, inplanes: int, planes: int, stride: int) -> None:
        super().__init__()
        self.conv1 = _conv3(inplanes, planes, stride)
        self.bn1 = nn.BatchNorm2d(planes, eps=_BN_EPS)
        self.conv2 = _conv3(planes, planes)
        self.bn2 = nn.BatchNorm2d(planes, eps=_BN_EPS)
        self.relu = nn.Hardswish()
        self.downsample: nn.Module | None = None
        if stride != 1 or inplanes != planes:
            self.downsample = nn.Sequential(
                nn.Conv2d(inplanes, planes, 1, stride=stride, bias=False),
                nn.BatchNorm2d(planes, eps=_BN_EPS),
            )

    def forward(self, x: Tensor) -> Tensor:
        identity = x if self.downsample is None else self.downsample(x)
        out = self.relu(self.bn1(self.conv1(x)))
        result: Tensor = self.relu(self.bn2(self.conv2(out)) + identity)
        return result


class _ConvModule(nn.Module):
    """mmcv ``ConvModule`` naming: ``conv`` then ``bn`` then activation."""

    def __init__(self, inputs: int, outputs: int) -> None:
        super().__init__()
        self.conv = _conv3(inputs, outputs)
        self.bn = nn.BatchNorm2d(outputs, eps=_BN_EPS)
        self.activate = nn.Hardswish()

    def forward(self, x: Tensor) -> Tensor:
        result: Tensor = self.activate(self.bn(self.conv(x)))
        return result


class _FrustumFeatureEncoder(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        channels = (8, 64, 128, 256, 256)  # x, y, z, r + distance + cluster offset.
        self.pre_norm = nn.BatchNorm1d(channels[0], eps=_BN_EPS)
        layers: list[nn.Module] = [
            nn.Sequential(
                nn.Linear(channels[i], channels[i + 1], bias=False),
                nn.BatchNorm1d(channels[i + 1], eps=_BN_EPS),
                nn.ReLU(inplace=True),
            )
            for i in range(3)
        ]
        layers.append(nn.Linear(channels[3], channels[4]))
        self.ffe_layers = nn.ModuleList(layers)
        self.compression_layers = nn.Sequential(nn.Linear(256, 16), nn.ReLU(inplace=True))

    def forward(self, points: Tensor, coors: Tensor) -> tuple[Tensor, Tensor, list[Tensor]]:
        voxel_coors, inverse = torch.unique(coors, return_inverse=True, dim=0)
        groups = len(voxel_coors)
        distance = torch.norm(points[:, :3], 2, 1, keepdim=True)
        mean = _scatter_mean(points, inverse, groups)[inverse]
        features = self.pre_norm(torch.cat((points, distance, points[:, :3] - mean[:, :3]), -1))
        point_feats = []
        for layer in self.ffe_layers:
            features = layer(features)
            point_feats.append(features)
        voxel_feats = self.compression_layers(_scatter_max(features, inverse, groups))
        return voxel_feats, voxel_coors, point_feats


class _Backbone(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        stem = 128
        self.ny, self.nx = _RANGE_H, _MODEL_W
        self.stem = nn.Sequential(
            _conv3(16, stem // 2),
            nn.BatchNorm2d(stem // 2, eps=_BN_EPS),
            nn.Hardswish(),
            _conv3(stem // 2, stem),
            nn.BatchNorm2d(stem, eps=_BN_EPS),
            nn.Hardswish(),
            _conv3(stem, stem),
            nn.BatchNorm2d(stem, eps=_BN_EPS),
            nn.Hardswish(),
        )
        self.point_stem = _point_layer(384, stem)
        self.fusion_stem = _fusion_layer(stem * 2, stem)
        self.point_fusion_layers = nn.ModuleList()
        self.pixel_fusion_layers = nn.ModuleList()
        self.attention_layers = nn.ModuleList()
        self.strides: list[int] = []
        overall = 1
        for index, (blocks, stride) in enumerate(zip((3, 4, 6, 3), (1, 2, 2, 2), strict=True)):
            overall *= stride
            self.strides.append(overall)
            layer = [_BasicBlock(stem, stem, stride)]
            layer += [_BasicBlock(stem, stem, 1) for _ in range(1, blocks)]
            self.add_module(f"layer{index + 1}", nn.Sequential(*layer))
            self.point_fusion_layers.append(_point_layer(stem * 2, stem))
            self.pixel_fusion_layers.append(_fusion_layer(stem * 2, stem))
            self.attention_layers.append(
                nn.Sequential(
                    _conv3(stem, stem),
                    nn.BatchNorm2d(stem, eps=_BN_EPS),
                    nn.Hardswish(),
                    _conv3(stem, stem),
                    nn.BatchNorm2d(stem, eps=_BN_EPS),
                    nn.Sigmoid(),
                )
            )
        self.fuse_layer1 = _ConvModule(stem * 5, 256)
        self.point_fuse_layer1 = _point_layer(stem * 5, 256)
        self.fuse_layer2 = _ConvModule(256, 128)
        self.point_fuse_layer2 = _point_layer(256, 128)

    def _to_pixel(self, features: Tensor, coors: Tensor, stride: int) -> Tensor:
        pixels = features.new_zeros((1, self.ny // stride, self.nx // stride, features.shape[1]))
        pixels[coors[:, 0], coors[:, 1], coors[:, 2]] = features
        return pixels.permute(0, 3, 1, 2).contiguous()

    @staticmethod
    def _to_point(pixels: Tensor, coors: Tensor, stride: int) -> Tensor:
        pixels = pixels.permute(0, 2, 3, 1).contiguous()
        return pixels[coors[:, 0], coors[:, 1] // stride, coors[:, 2] // stride]

    @staticmethod
    def _to_frustum(features: Tensor, coors: Tensor, stride: int) -> tuple[Tensor, Tensor]:
        strided = coors.clone()
        strided[:, 1:] = coors[:, 1:] // stride
        frustum_coors, inverse = torch.unique(strided, return_inverse=True, dim=0)
        return frustum_coors, _scatter_max(features, inverse, len(frustum_coors))

    def forward(
        self, voxel_feats: Tensor, voxel_coors: Tensor, point_feats: Tensor, coors: Tensor
    ) -> tuple[Tensor, Tensor]:
        x = self.stem(self._to_pixel(voxel_feats, voxel_coors, 1))
        point = self.point_stem(torch.cat((self._to_point(x, coors, 1), point_feats), 1))
        frustum_coors, frustum = self._to_frustum(point, coors, 1)
        x = self.fusion_stem(torch.cat((self._to_pixel(frustum, frustum_coors, 1), x), 1))
        outs, points = [x], [point]
        for index, stride in enumerate(self.strides):
            x = getattr(self, f"layer{index + 1}")(x)
            fused = torch.cat((self._to_point(x, coors, stride), point), 1)
            point = self.point_fusion_layers[index](fused)
            frustum_coors, frustum = self._to_frustum(point, coors, stride)
            pixels = self._to_pixel(frustum, frustum_coors, stride)
            fuse = self.pixel_fusion_layers[index](torch.cat((pixels, x), 1))
            x = fuse * self.attention_layers[index](fuse) + x
            outs.append(x)
            points.append(point)
        size = outs[0].shape[2:]
        outs = [
            out
            if out.shape == outs[0].shape
            else F.interpolate(out, size=size, mode="bilinear", align_corners=True)
            for out in outs
        ]
        pixel = self.fuse_layer2(self.fuse_layer1(torch.cat(outs, 1)))
        point = self.point_fuse_layer2(self.point_fuse_layer1(torch.cat(points, 1)))
        return pixel, point


class _FRHead(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.mlps = nn.ModuleList()
        inputs = 128
        for outputs in (128, 256, 128, 64):
            self.mlps.append(_point_layer(inputs, outputs))
            inputs = outputs
        self.conv_seg = nn.Linear(64, _NUM_CLASSES)

    def forward(
        self, pixel: Tensor, backbone_point: Tensor, point_feats: list[Tensor], coors: Tensor
    ) -> Tensor:
        pixels = pixel.permute(0, 2, 3, 1)
        features = pixels[coors[:, 0], coors[:, 1], coors[:, 2]]
        encoder_feats = point_feats[:-1]
        for index, mlp in enumerate(self.mlps):
            features = mlp(features)
            features = features + (backbone_point if index == 0 else encoder_feats[-index])
        logits: Tensor = self.conv_seg(features)
        return logits


class FRNetSegmentor(nn.Module):
    """Inference-only FRNet for SemanticKITTI (64 x 512 frustum range image)."""

    def __init__(self) -> None:
        super().__init__()
        self.voxel_encoder = _FrustumFeatureEncoder()
        self.backbone = _Backbone()
        self.decode_head = _FRHead()
        self._fov_up = _FOV_UP_DEG / 180 * np.pi
        self._fov_down = _FOV_DOWN_DEG / 180 * np.pi
        self._fov = abs(self._fov_down) + abs(self._fov_up)

    def frustum_coordinates(self, points: Tensor) -> Tensor:
        depth = torch.linalg.norm(points[:, :3], 2, dim=1)
        yaw = -torch.atan2(points[:, 1], points[:, 0])
        pitch = torch.arcsin(points[:, 2] / depth)
        x = torch.floor(0.5 * (yaw / np.pi + 1.0) * _MODEL_W)
        y = torch.floor((1.0 - (pitch + abs(self._fov_down)) / self._fov) * _RANGE_H)
        x = torch.clamp(x, min=0, max=_MODEL_W - 1).type(torch.int64)
        y = torch.clamp(y, min=0, max=_RANGE_H - 1).type(torch.int64)
        return F.pad(torch.stack((y, x), dim=1), (1, 0), mode="constant", value=0)

    def forward(self, points: Tensor) -> Tensor:
        coors = self.frustum_coordinates(points)
        voxel_feats, voxel_coors, point_feats = self.voxel_encoder(points, coors)
        pixel, backbone_point = self.backbone(voxel_feats, voxel_coors, point_feats[-1], coors)
        return self.decode_head(pixel, backbone_point, point_feats, coors)  # type: ignore[no-any-return]


class TorchFRNetPredictor:
    """Label-free FRNet predictor running in-process on CPU or an NVIDIA GPU."""

    def __init__(
        self,
        *,
        checkpoint: Path,
        checkpoint_sha256: str,
        device: Literal["cpu", "cuda"] = "cpu",
        precision: Literal["fp32", "fp16"] = "fp32",
        gpu_interpolation: bool = False,
    ) -> None:
        if device not in ("cpu", "cuda"):
            raise ValueError("FRNet device must be cpu or cuda")
        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("FRNet CUDA inference requires a CUDA-enabled PyTorch build")
        if precision not in ("fp32", "fp16") or (precision == "fp16" and device != "cuda"):
            raise ValueError("FRNet fp16 autocast requires --device cuda")
        if gpu_interpolation and device != "cuda":
            raise ValueError("FRNet GPU interpolation requires --device cuda")
        # fp32 with the NumPy interpolation is the reference: it reproduces the authors'
        # runtime byte for byte on CPU. fp16 and GPU interpolation are measured speed options.
        self.precision = precision
        self.gpu_interpolation = gpu_interpolation
        self.checkpoint_sha256 = checked_digest(checkpoint, checkpoint_sha256, "checkpoint")
        self.weights_sha256 = self.checkpoint_sha256
        self.source_revision = FRNET_REVISION
        self.class_map_version = FRNET_CLASS_MAP_VERSION
        self.device = device
        # The checkpoint hash is checked first; weights_only refuses arbitrary pickled code.
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)["state_dict"]
        inference = {
            key: value for key, value in state.items() if not key.startswith("auxiliary_head.")
        }
        if not all(isinstance(value, Tensor) for value in inference.values()) or not all(
            bool(torch.isfinite(value).all()) for value in inference.values()
        ):
            raise ValueError("FRNet checkpoint contains non-tensor or nonfinite weights")
        self.skipped_training_tensors = len(state) - len(inference)
        model = FRNetSegmentor()
        model.load_state_dict(inference, strict=True)
        if device == "cuda":
            # Bounded device memory: cap the caching allocator so it frees and retries
            # instead of oversubscribing VRAM (WDDM would back that with system RAM).
            torch.cuda.set_per_process_memory_fraction(TORCH_CUDA_MEMORY_FRACTION)
            # Full-precision convolutions and matmuls keep CUDA numerically close to CPU.
            torch.backends.cudnn.allow_tf32 = False
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.benchmark = False
        self._model = model.eval().to(device)
        self.environment = {
            "runtime": TORCH_RUNTIME,
            "torch": torch.__version__,
            "device": device,
            "cuda": str(torch.version.cuda) if device == "cuda" else "none",
            "gpu": torch.cuda.get_device_name(0) if device == "cuda" else "none",
            "skipped_training_tensors": str(self.skipped_training_tensors),
            "precision": precision,
            "interpolation": "torch-device" if gpu_interpolation else "numpy-reference",
        }

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction:
        if points.ndim != 2 or points.shape[1] != 4 or points.dtype != np.float32:
            raise ValueError("FRNet requires float32 sensor points with shape (N, 4)")
        if point_ids.shape != (len(points),) or point_ids.dtype != np.int64:
            raise ValueError("FRNet point IDs must align with accepted points")
        if not np.isfinite(points).all():
            raise ValueError("FRNet requires finite geometry and intensity")
        if len(points) == 0:
            return SemanticPrediction(
                np.empty(0, dtype=np.uint8),
                np.empty(0, dtype=np.float64),
                np.empty(0, dtype=np.uint8),
            )
        with torch.inference_mode():
            if self.gpu_interpolation:
                # Inputs are sealed read-only arrays; copy before wrapping as a tensor.
                augmented = range_interpolation_torch(
                    torch.from_numpy(points.copy()).to(self.device)
                )
            else:
                augmented = torch.from_numpy(range_interpolation(points)).to(self.device)
            if self.precision == "fp16":
                # autocast keeps numerically sensitive ops (softmax, norms) in float32.
                with torch.autocast("cuda", dtype=torch.float16):
                    logits = self._model(augmented)[: len(points)]
                logits = logits.float()
            else:
                logits = self._model(augmented)[: len(points)]
            scores = torch.softmax(logits.transpose(0, 1), dim=0)
            confidence, raw_class = scores.max(dim=0)
        classes = raw_class.cpu().numpy().astype(np.uint8)
        scores_host: FloatArray = confidence.cpu().numpy().astype(np.float64)
        return remap_frnet_output(classes, scores_host)

    def close(self) -> None:
        del self._model
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def __enter__(self) -> "TorchFRNetPredictor":
        return self

    def __exit__(self, _kind: object, _error: object, _traceback: object) -> None:
        self.close()
