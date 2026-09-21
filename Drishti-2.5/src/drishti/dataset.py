import hashlib
import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from drishti.arrays import FloatArray, immutable
from drishti.contracts import Mode, PoseSource, ScanFrame
from drishti.geometry import map_sensor_poses, validate_transform
from drishti.semantics import decode_semantickitti


def read_calibration(path: Path) -> FloatArray:
    transforms = [
        line.split(":", 1)[1]
        for line in path.read_text().splitlines()
        if line.strip().startswith("Tr:")
    ]
    if len(transforms) != 1:
        raise ValueError(f"{path}: expected exactly one Tr calibration")
    try:
        values = np.array([float(value) for value in transforms[0].split()], dtype=np.float64)
    except ValueError as exc:
        raise ValueError(f"{path}: invalid calibration values") from exc
    if values.size != 12:
        raise ValueError(f"{path}: calibration Tr must contain 12 values")
    result = np.eye(4)
    result[:3] = values.reshape(3, 4)
    validate_transform(result)
    return result


class DatasetSource:
    def __init__(
        self,
        root: Path,
        sequence: str,
        *,
        mode: Mode = Mode.GEOMETRIC,
        pose_source: PoseSource = PoseSource.SLAM,
        max_points: int = 150_000,
    ) -> None:
        if re.fullmatch(r"\d{2}", sequence) is None or not 0 <= int(sequence) <= 21:
            raise ValueError("sequence must be a two-digit SemanticKITTI ID from 00 to 21")
        if type(max_points) is not int or max_points <= 0:
            raise ValueError("max_points must be a positive integer")
        if pose_source not in (PoseSource.SLAM, PoseSource.KITTI_GT):
            raise ValueError("dataset pose source must be slam or kitti-gt")
        if mode not in (Mode.GEOMETRIC, Mode.ORACLE):
            raise ValueError("dataset mode must be geometric or oracle")
        self.root = root.expanduser().resolve(strict=True)
        self.sequence = sequence
        self.mode = mode
        self.pose_source = pose_source
        self.max_points = max_points
        folder = self.root / "sequences" / sequence
        self.scan_paths = tuple(sorted((folder / "velodyne").glob("*.bin")))
        if not self.scan_paths:
            raise FileNotFoundError(f"no scans in {folder / 'velodyne'}")
        expected = [f"{index:06d}" for index in range(len(self.scan_paths))]
        if [path.stem for path in self.scan_paths] != expected:
            raise ValueError(
                "scan frame names must be contiguous, six-digit IDs starting at 000000"
            )
        self.label_paths: tuple[Path, ...] = ()
        if mode == Mode.ORACLE:
            self.label_paths = tuple(sorted((folder / "labels").glob("*.label")))
            if [path.stem for path in self.label_paths] != expected:
                raise ValueError("oracle mode requires exactly one matching label file per scan")
        times_path = folder / "times.txt"
        timestamps = np.loadtxt(times_path, dtype=np.float64, ndmin=1)
        if timestamps.shape != (len(self.scan_paths),) or not np.isfinite(timestamps).all():
            raise ValueError(f"{times_path}: timestamp count or values are invalid")
        if np.any(timestamps < 0) or np.any(np.diff(timestamps) <= 0):
            raise ValueError(
                f"{times_path}: timestamps must be nonnegative and strictly increasing"
            )
        self.timestamps_s = immutable(timestamps)
        poses_path = (
            folder / "poses.txt"
            if pose_source == PoseSource.SLAM
            else self.root / "poses" / f"{sequence}.txt"
        )
        rows = np.loadtxt(poses_path, dtype=np.float64, ndmin=2)
        if rows.shape != (len(self.scan_paths), 12):
            raise ValueError(f"{poses_path}: pose count or row shape does not match scans")
        poses = np.repeat(np.eye(4)[None], len(rows), axis=0)
        poses[:, :3] = rows.reshape(-1, 3, 4)
        calibration_path = folder / "calib.txt"
        self.map_from_sensor = immutable(
            map_sensor_poses(poses, read_calibration(calibration_path))
        )
        self.metadata_hashes = {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in (
                ("calibration", calibration_path),
                ("poses", poses_path),
                ("timestamps", times_path),
            )
        }

    @property
    def frame_count(self) -> int:
        return len(self.scan_paths)

    def frames(self, *, start_frame: int = 0, max_frames: int | None = None) -> Iterator[ScanFrame]:
        if not 0 <= start_frame < self.frame_count:
            raise ValueError(f"start_frame must lie in [0, {self.frame_count})")
        if max_frames is not None and max_frames <= 0:
            raise ValueError("max_frames must be positive")
        end = (
            self.frame_count
            if max_frames is None
            else min(start_frame + max_frames, self.frame_count)
        )
        for index in range(start_frame, end):
            path = self.scan_paths[index]
            byte_count = path.stat().st_size
            if byte_count == 0 or byte_count % 16:
                raise ValueError(f"{path}: invalid scan byte count {byte_count}")
            count = byte_count // 16
            if count > self.max_points:
                raise ValueError(
                    f"{path}: {count} points exceed configured capacity {self.max_points}"
                )
            flat = np.fromfile(path, dtype="<f4")
            if flat.size != count * 4:
                raise ValueError(f"{path}: scan changed while being read")
            annotations = None
            if self.mode == Mode.ORACLE:
                label_path = self.label_paths[index]
                if label_path.stat().st_size != count * 4:
                    raise ValueError(f"{label_path}: label point count does not match scan")
                packed = np.fromfile(label_path, dtype="<u4")
                if len(packed) != count:
                    raise ValueError(f"{label_path}: label count changed while being read")
                annotations = decode_semantickitti(packed)
            yield ScanFrame(
                self.sequence,
                index,
                float(self.timestamps_s[index]),
                flat.reshape(-1, 4),
                np.arange(count, dtype=np.int64),
                self.map_from_sensor[index],
                self.pose_source,
                annotations,
            )
