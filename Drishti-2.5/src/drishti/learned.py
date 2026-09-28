"""Point-aligned semantic prediction contract and isolated FRNet CPU adapter."""

import hashlib
import json
import math
import select
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

import numpy as np

from drishti.arrays import ByteArray, FloatArray, IntArray, PointArray, immutable

FRNET_REVISION = "d3749c8bcf6ef0fe2c95adea55375ac73a4b3825"
FRNET_CLASS_MAP_VERSION = "frnet-semantickitti-to-drishti-v1"
FRNET_WORKER_PROTOCOL = 1


@dataclass(frozen=True)
class SemanticPrediction:
    semantic_id: ByteArray
    confidence: FloatArray
    unknown_reason: ByteArray

    def __post_init__(self) -> None:
        count = len(self.semantic_id)
        if (
            self.semantic_id.shape != (count,)
            or self.semantic_id.dtype != np.uint8
            or self.confidence.shape != (count,)
            or self.confidence.dtype != np.float64
            or self.unknown_reason.shape != (count,)
            or self.unknown_reason.dtype != np.uint8
        ):
            raise ValueError("semantic prediction arrays must be aligned uint8/float64/uint8")
        if np.any(self.semantic_id > 19):
            raise ValueError("semantic predictions must use learning IDs 0..19")
        if not np.isfinite(self.confidence).all() or np.any(
            (self.confidence < 0) | (self.confidence > 1)
        ):
            raise ValueError("semantic scores must be finite and within [0, 1]")
        if np.any((self.semantic_id == 0) != (self.unknown_reason != 0)):
            raise ValueError("unknown labels must have a reason, known labels must not")
        if np.any(self.unknown_reason > 2):
            raise ValueError("unknown reason is outside the product contract")
        for name in ("semantic_id", "confidence", "unknown_reason"):
            object.__setattr__(self, name, immutable(getattr(self, name)))


class SemanticPredictor(Protocol):
    checkpoint_sha256: str
    weights_sha256: str

    def predict(self, points: PointArray, point_ids: IntArray) -> SemanticPrediction: ...
    def close(self) -> None: ...


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _checked_digest(path: Path, expected: str, name: str) -> str:
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise ValueError(f"{name} SHA-256 must be 64 lowercase hex characters")
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"{name} SHA-256 mismatch")
    return actual


def remap_frnet_output(raw_class: ByteArray, confidence: FloatArray) -> SemanticPrediction:
    """Map FRNet channels 0..18 to Drishti 1..19, channel 19 to unknown."""
    if (
        raw_class.ndim != 1
        or raw_class.dtype != np.uint8
        or confidence.shape != raw_class.shape
        or confidence.dtype != np.float64
        or np.any(raw_class > 19)
    ):
        raise ValueError("FRNet worker returned invalid point-aligned classes or scores")
    semantic = np.where(raw_class == 19, 0, raw_class + 1).astype(np.uint8)
    reason = np.where(semantic == 0, 2, 0).astype(np.uint8)
    return SemanticPrediction(semantic, confidence, reason)


class FRNetPredictor:
    """Persistent label-free CPU worker using the authors' pinned FRNet source."""

    def __init__(
        self,
        *,
        python: Path,
        source_root: Path,
        checkpoint: Path,
        checkpoint_sha256: str,
        weights_npz: Path,
        weights_sha256: str,
        timeout_s: float = 120.0,
    ) -> None:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("FRNet worker timeout must be positive and finite")
        self.timeout_s = timeout_s
        self.checkpoint_sha256 = _checked_digest(checkpoint, checkpoint_sha256, "checkpoint")
        self.weights_sha256 = _checked_digest(weights_npz, weights_sha256, "tensor export")
        source_revision = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if source_revision.returncode != 0:
            raise ValueError("FRNet source root must be a Git checkout")
        revision = source_revision.stdout.strip()
        if revision != FRNET_REVISION:
            raise ValueError(f"FRNet source revision must be {FRNET_REVISION}")
        source_status = subprocess.run(
            ["git", "-C", str(source_root), "status", "--porcelain", "--untracked-files=no"],
            check=False,
            capture_output=True,
            text=True,
        )
        if source_status.returncode != 0 or source_status.stdout.strip():
            raise ValueError("FRNet tracked source files must match the pinned revision")
        self.source_revision = revision
        self._scratch = tempfile.TemporaryDirectory(prefix="drishti-frnet-")
        self._stderr: TextIO = Path(self._scratch.name, "worker.stderr").open("w+")
        self._process = subprocess.Popen(
            [
                str(python),
                str(Path(__file__).with_name("frnet_worker.py")),
                "--source-root",
                str(source_root),
                "--weights-npz",
                str(weights_npz),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr,
            text=True,
            bufsize=1,
        )
        self._request_index = 0
        try:
            ready = self._response()
            if ready.get("status") != "ready" or ready.get("protocol") != FRNET_WORKER_PROTOCOL:
                raise RuntimeError("FRNet worker did not complete the protocol handshake")
            self.environment = {
                key: str(ready[key]) for key in ("python", "torch", "mmcv", "mmengine", "mmdet3d")
            }
        except BaseException:
            self.close()
            raise

    def _response(self) -> dict[str, object]:
        if self._process.stdout is None:
            raise RuntimeError("FRNet worker stdout is unavailable")
        ready, _, _ = select.select([self._process.stdout], [], [], self.timeout_s)
        if not ready:
            self._process.kill()
            raise RuntimeError("FRNet worker timed out")
        line = self._process.stdout.readline()
        if not line:
            self._stderr.flush()
            error = Path(self._scratch.name, "worker.stderr").read_text()[-2000:]
            raise RuntimeError(f"FRNet worker exited without a response: {error}")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError("FRNet worker returned a non-object response")
        return value

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
        if self._process.stdin is None:
            raise RuntimeError("FRNet worker stdin is unavailable")
        index = self._request_index
        self._request_index += 1
        input_path = Path(self._scratch.name, f"input-{index}.npy")
        output_path = Path(self._scratch.name, f"output-{index}.npz")
        try:
            np.save(input_path, points, allow_pickle=False)
            self._process.stdin.write(
                json.dumps({"input": str(input_path), "output": str(output_path)}) + "\n"
            )
            self._process.stdin.flush()
            response = self._response()
            if response.get("status") != "ok" or response.get("points") != len(points):
                raise RuntimeError(f"FRNet worker rejected the scan: {response.get('error')}")
            with np.load(output_path, allow_pickle=False) as result:
                if set(result.files) != {"raw_class", "confidence"}:
                    raise ValueError("FRNet worker returned unexpected output fields")
                raw_class = result["raw_class"]
                confidence = result["confidence"]
            if raw_class.shape != (len(points),):
                raise ValueError("FRNet worker returned the wrong number of point labels")
            return remap_frnet_output(raw_class, confidence)
        finally:
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        if self._process.stdin is not None:
            self._process.stdin.close()
        if self._process.stdout is not None:
            self._process.stdout.close()
        self._stderr.close()
        self._scratch.cleanup()

    def __enter__(self) -> "FRNetPredictor":
        return self

    def __exit__(self, _kind: object, _error: object, _traceback: object) -> None:
        self.close()
