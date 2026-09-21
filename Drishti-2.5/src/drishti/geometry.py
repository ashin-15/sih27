import numpy as np

from drishti.arrays import FloatArray

CAMERA_TO_MAP_AXES = np.array(
    [[0.0, 0.0, 1.0, 0.0], [-1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
)
CAMERA_TO_MAP_AXES.setflags(write=False)


def validate_transform(transform: FloatArray) -> None:
    if transform.shape != (4, 4) or not np.isfinite(transform).all():
        raise ValueError("transform must be a finite 4x4 matrix")
    if not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-12, rtol=0):
        raise ValueError("transform must have homogeneous bottom row [0, 0, 0, 1]")
    rotation = transform[:3, :3]
    if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-3, rtol=0):
        raise ValueError("transform rotation must be orthonormal")
    if not np.isclose(np.linalg.det(rotation), 1, atol=1e-3, rtol=0):
        raise ValueError("transform rotation must be right handed")


def transform_points(points_m: FloatArray, transform: FloatArray) -> FloatArray:
    validate_transform(transform)
    if points_m.ndim != 2 or points_m.shape[1] != 3:
        raise ValueError("points must have shape (N, 3)")
    return np.asarray(points_m @ transform[:3, :3].T + transform[:3, 3], dtype=np.float64)


def sensor_coordinates(points_map_m: FloatArray, map_from_sensor: FloatArray) -> FloatArray:
    validate_transform(map_from_sensor)
    return transform_points(points_map_m, np.linalg.inv(map_from_sensor))


def map_sensor_poses(camera_poses: FloatArray, sensor_to_camera: FloatArray) -> FloatArray:
    validate_transform(sensor_to_camera)
    if camera_poses.ndim != 3 or camera_poses.shape[1:] != (4, 4) or not len(camera_poses):
        raise ValueError("camera poses must have shape (N, 4, 4) with N > 0")
    for pose in camera_poses:
        validate_transform(pose)
    result = np.asarray(CAMERA_TO_MAP_AXES @ camera_poses @ sensor_to_camera, dtype=np.float64)
    result[:, :3, 3] -= result[0, :3, 3].copy()
    return result
