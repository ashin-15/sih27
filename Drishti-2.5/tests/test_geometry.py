import numpy as np
import pytest

from drishti.geometry import map_sensor_poses, sensor_coordinates, transform_points


def test_sensor_projection_uses_full_inverse_pose_at_ninety_degrees() -> None:
    pose = np.array([[0, -1, 0, 12], [1, 0, 0, -8], [0, 0, 1, 3], [0, 0, 0, 1]], float)
    original = np.array([[15.0, 0.0, -1.2], [30.0, 2.0, 0.0]])
    world = transform_points(original, pose)
    np.testing.assert_allclose(sensor_coordinates(world, pose), original, atol=1e-12)
    assert not np.allclose(world - pose[:3, 3], original)


def test_map_origin_is_first_sensor_and_camera_axes_are_converted() -> None:
    camera_poses = np.repeat(np.eye(4)[None], 2, axis=0)
    camera_poses[1, 2, 3] = 5.0
    sensor_to_camera = np.array(
        [[0, -1, 0, 0.2], [0, 0, -1, -0.1], [1, 0, 0, 0.3], [0, 0, 0, 1]], float
    )
    poses = map_sensor_poses(camera_poses, sensor_to_camera)
    np.testing.assert_allclose(poses[0], np.eye(4), atol=1e-12)
    np.testing.assert_allclose(poses[1, :3, 3], [5, 0, 0], atol=1e-12)


def test_nonrigid_pose_is_rejected() -> None:
    pose = np.eye(4)
    pose[0, 0] = 2
    with pytest.raises(ValueError, match="rotation"):
        transform_points(np.zeros((1, 3)), pose)
