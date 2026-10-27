"""Relative camera/IMU mapping into an SO-101 end-effector target."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from protocol import SensorSample
from mano_reference import IMU_TO_HAND_ROTATION, mano_local_rotation


# Camera x/right, y/down, z/forward -> robot y/right, z/up, x/forward.
CAMERA_TO_ROBOT = np.array(((0.0, 0.0, 1.0),
                            (1.0, 0.0, 0.0),
                            (0.0, -1.0, 0.0)))


def quaternion_matrix(quaternion_wxyz: np.ndarray) -> np.ndarray:
    q = np.asarray(quaternion_wxyz, dtype=float)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array(((1 - 2 * (y*y + z*z), 2 * (x*y - w*z), 2 * (x*z + w*y)),
                     (2 * (x*y + w*z), 1 - 2 * (x*x + z*z), 2 * (y*z - w*x)),
                     (2 * (x*z - w*y), 2 * (y*z + w*x), 1 - 2 * (x*x + y*y))))


def matrix_rpy_degrees(rotation: np.ndarray) -> np.ndarray:
    """Return intrinsic XYZ roll, pitch and yaw for concise diagnostics."""
    pitch = np.arcsin(np.clip(-rotation[2, 0], -1.0, 1.0))
    roll = np.arctan2(rotation[2, 1], rotation[2, 2])
    yaw = np.arctan2(rotation[1, 0], rotation[0, 0])
    return np.rad2deg((roll, pitch, yaw))


def rotation_vector(rotation: np.ndarray) -> np.ndarray:
    angle = float(np.arccos(np.clip((np.trace(rotation) - 1.0) * 0.5, -1.0, 1.0)))
    if angle < 1e-7:
        return np.zeros(3)
    axis = np.array((rotation[2, 1] - rotation[1, 2],
                     rotation[0, 2] - rotation[2, 0],
                     rotation[1, 0] - rotation[0, 1])) / (2.0 * np.sin(angle))
    return axis * angle


def load_axis_calibration(path: Path | None) -> tuple[np.ndarray, float]:
    if path is None or not path.exists():
        return np.eye(3), 1.0
    data = json.loads(path.read_text(encoding="utf-8"))
    matrix = np.asarray(data["sensor_to_control"], dtype=float)
    if matrix.shape != (3, 3) or not np.isfinite(matrix).all():
        raise ValueError("sensor_to_control must be a finite 3x3 matrix")
    return matrix, float(data.get("yaw_gain", 1.0))


class EndEffectorMapper:
    def __init__(self, origin_position: np.ndarray, origin_rotation: np.ndarray,
                 position_scale: float = 1.0, yaw_scale: float = 1.0,
                 sensor_to_control: np.ndarray | None = None) -> None:
        self.origin_position = np.asarray(origin_position, dtype=float).copy()
        self.origin_rotation = np.asarray(origin_rotation, dtype=float).copy()
        self.position_scale = position_scale
        self.yaw_scale = yaw_scale
        self.sensor_to_control = (np.eye(3) if sensor_to_control is None
                                  else np.asarray(sensor_to_control, dtype=float))
        self.yaw_limit = np.deg2rad(180.0)
        self.yaw_deadzone = 0.0
        self.filtered_control = np.zeros(3)
        self.relative_rpy_degrees = np.zeros(3)
        self.position_reference: np.ndarray | None = None
        self.rotation_reference: np.ndarray | None = None
        self.quaternion_reference: np.ndarray | None = None
        self.sensor_position: np.ndarray | None = None
        self.sensor_rotation: np.ndarray | None = None
        self.sensor_quaternion: np.ndarray | None = None

    def reset(self) -> None:
        self.position_reference = None
        self.rotation_reference = None
        self.sensor_position = None
        self.sensor_rotation = None
        self.sensor_quaternion = None
        self.quaternion_reference = None
        self.filtered_control[:] = 0.0
        self.relative_rpy_degrees[:] = 0.0

    def update(self, sample: SensorSample) -> tuple[np.ndarray, np.ndarray]:
        if sample.reset:
            self.reset()
        new_imu = False
        if sample.camera_valid:
            self.sensor_position = sample.wrist_xyz.copy()
            if self.position_reference is None:
                self.position_reference = self.sensor_position.copy()
        quaternion_norm = float(np.linalg.norm(sample.wrist_quaternion_wxyz))
        if sample.imu_valid and quaternion_norm > 1e-8:
            self.sensor_rotation = quaternion_matrix(sample.wrist_quaternion_wxyz)
            self.sensor_quaternion = sample.wrist_quaternion_wxyz.copy()
            new_imu = True
            if self.rotation_reference is None:
                self.rotation_reference = self.sensor_rotation.copy()
                self.quaternion_reference = sample.wrist_quaternion_wxyz.copy()

        position = self.origin_position.copy()
        if self.position_reference is not None and self.sensor_position is not None:
            delta = self.sensor_position - self.position_reference
            position += self.position_scale * CAMERA_TO_ROBOT @ delta

        rotation = self.origin_rotation.copy()
        if self.quaternion_reference is not None and self.sensor_quaternion is not None:
            mapped = mano_local_rotation(self.sensor_quaternion, self.quaternion_reference)
            self.relative_rpy_degrees = matrix_rpy_degrees(mapped)
            roll, pitch, yaw = self.sensor_to_control @ rotation_vector(mapped)
            yaw = 0.0 if abs(yaw) < self.yaw_deadzone else yaw
            yaw = float(np.clip(self.yaw_scale * yaw, -self.yaw_limit, self.yaw_limit))
            command = np.array((roll, pitch, yaw))
            if new_imu:
                self.filtered_control += 0.18 * (command - self.filtered_control)
            roll, pitch, yaw = self.filtered_control
            cy, sy = np.cos(yaw), np.sin(yaw)
            cp, sp = np.cos(pitch), np.sin(pitch)
            cr, sr = np.cos(roll), np.sin(roll)
            orbit = np.array(((cy, -sy, 0.0),
                              (sy, cy, 0.0),
                              (0.0, 0.0, 1.0)))
            pitch_rotation = np.array(((cp, 0.0, sp),
                                       (0.0, 1.0, 0.0),
                                       (-sp, 0.0, cp)))
            roll_rotation = np.array(((1.0, 0.0, 0.0),
                                      (0.0, cr, -sr),
                                      (0.0, sr, cr)))
            camera_offset = position - self.origin_position
            position = orbit @ self.origin_position + camera_offset
            rotation = orbit @ pitch_rotation @ roll_rotation @ self.origin_rotation
        return position, rotation


def gripper_command(bend: np.ndarray, joint_range: np.ndarray,
                    use_mean: bool = False) -> float:
    value = float(np.mean(bend) if use_mean else bend[2])
    value = np.clip((value - 0.05) / 0.90, 0.0, 1.0)
    closed, opened = float(joint_range[0]), float(joint_range[1])
    return opened + value * (closed - opened)

