"""Canonical camera + dorsal-IMU + five-flex action sequence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from strain_calibration import StrainCalibration


FORMAT_VERSION = 1
FINGERS = ("thumb", "index", "middle", "ring", "little")


@dataclass(slots=True)
class SensorFrame:
    timestamp_us: int
    camera_valid: bool
    wrist_xyz: np.ndarray
    wrist_quaternion_wxyz: np.ndarray
    flex_raw: np.ndarray
    linear_acceleration: np.ndarray
    angular_velocity: np.ndarray


@dataclass(slots=True)
class HandFrame:
    timestamp_us: int
    wrist_xyz: np.ndarray
    wrist_quaternion_wxyz: np.ndarray
    bend: np.ndarray


def quaternion_to_rotation(quaternion_wxyz: np.ndarray) -> np.ndarray:
    q = np.asarray(quaternion_wxyz, dtype=np.float64)
    q = q / np.linalg.norm(q)
    w, x, y, z = q
    return np.array(
        (
            (1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)),
            (2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)),
            (2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)),
        ),
        dtype=np.float64,
    )


def _quaternion_xyz(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return np.array(
        (cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy,
         cr * sp * cy + sr * cp * sy, cr * cp * sy - sr * sp * cy),
        dtype=np.float64,
    )


def demo_sequence(frame_count: int = 240, rate_hz: float = 60.0) -> list[SensorFrame]:
    frames = []
    calibration = StrainCalibration.default()
    phases = np.array((0.2, 0.0, 0.35, 0.7, 1.05))
    for index in range(frame_count):
        seconds = index / rate_hz
        bend = np.clip(0.5 + 0.5 * np.sin(1.25 * seconds + phases), 0.0, 1.0)
        position = np.array((0.035 * math.sin(0.7 * seconds),
                             0.018 * math.sin(0.9 * seconds),
                             0.31 + 0.012 * math.cos(0.6 * seconds)))
        quaternion = _quaternion_xyz(0.12 * math.sin(0.8 * seconds),
                                     0.10 * math.sin(0.6 * seconds),
                                     0.18 * math.sin(0.5 * seconds))
        frames.append(SensorFrame(
            round(index * 1_000_000 / rate_hz),
            not (150 <= index < 162),
            position,
            quaternion,
            np.rint(calibration.encode(bend)).astype(np.uint16),
            np.zeros(3),
            np.array((0.0, 0.0, 0.09 * math.cos(0.5 * seconds))),
        ))
    return frames


def static_frame(name: str) -> HandFrame:
    bends = {
        "open": (0, 0, 0, 0, 0),
        "relaxed": (0.18, 0.12, 0.16, 0.20, 0.24),
        "fist": (1, 1, 1, 1, 1),
        "point": (0.75, 0, 1, 1, 1),
        "thumb": (0, 1, 1, 1, 1),
    }
    return HandFrame(0, np.array((0.0, 0.0, 0.31)),
                     _quaternion_xyz(-0.14, 0.05, 0.07), np.array(bends[name], dtype=float))


def save_sequence(path: Path, frames: list[SensorFrame]) -> None:
    np.savez_compressed(
        path,
        format_version=np.array(FORMAT_VERSION, dtype=np.uint16),
        timestamp_us=np.array([frame.timestamp_us for frame in frames], dtype=np.uint64),
        camera_valid=np.array([frame.camera_valid for frame in frames], dtype=np.bool_),
        wrist_xyz=np.stack([frame.wrist_xyz for frame in frames]).astype(np.float32),
        wrist_quaternion_wxyz=np.stack([frame.wrist_quaternion_wxyz for frame in frames]).astype(np.float32),
        flex_raw=np.stack([frame.flex_raw for frame in frames]).astype(np.uint16),
        linear_acceleration=np.stack([frame.linear_acceleration for frame in frames]).astype(np.float32),
        angular_velocity=np.stack([frame.angular_velocity for frame in frames]).astype(np.float32),
    )


def load_sequence(path: Path) -> list[SensorFrame]:
    with np.load(path) as data:
        if int(data["format_version"].item()) != FORMAT_VERSION:
            raise ValueError("unsupported hand sequence version")
        count = len(data["timestamp_us"])
        return [SensorFrame(int(data["timestamp_us"][i]), bool(data["camera_valid"][i]),
                            data["wrist_xyz"][i].astype(float),
                            data["wrist_quaternion_wxyz"][i].astype(float),
                            data["flex_raw"][i].astype(np.uint16),
                            data["linear_acceleration"][i].astype(float),
                            data["angular_velocity"][i].astype(float)) for i in range(count)]


class WristTracker:
    """Use fresh visual positions and hold through missing 20 Hz updates."""

    def __init__(self, calibration: StrainCalibration | None = None) -> None:
        self.calibration = calibration or StrainCalibration.default()
        self.position = np.zeros(3)
        self.camera_known = False

    def update(self, frame: SensorFrame) -> HandFrame:
        if frame.camera_valid:
            if not self.camera_known:
                self.position[:] = frame.wrist_xyz
                self.camera_known = True
            else:
                self.position += 0.75 * (frame.wrist_xyz - self.position)
        return HandFrame(frame.timestamp_us, self.position.copy(),
                         frame.wrist_quaternion_wxyz.copy(),
                         self.calibration.decode(frame.flex_raw))
