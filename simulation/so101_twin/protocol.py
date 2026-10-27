"""Independent HAND v2 and action-sequence input for the SO-101 demo."""

from __future__ import annotations

import math
import socket
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


MAGIC = 0x444E4148
VERSION = 2
SENSOR = 1
DEFAULT_PORT = 47000
PACKET = struct.Struct("<IHHIIBBBB13f5HH")


@dataclass(slots=True)
class SensorSample:
    timestamp_us: int
    camera_valid: bool
    imu_valid: bool
    reset: bool
    wrist_xyz: np.ndarray
    wrist_quaternion_wxyz: np.ndarray
    bend: np.ndarray
    angular_velocity: np.ndarray = field(default_factory=lambda: np.zeros(3))
    linear_acceleration: np.ndarray = field(default_factory=lambda: np.zeros(3))


def decode_packet(payload: bytes) -> tuple[int, SensorSample]:
    if len(payload) != PACKET.size:
        raise ValueError(f"expected {PACKET.size} bytes, got {len(payload)}")
    values = PACKET.unpack(payload)
    if values[:3] != (MAGIC, VERSION, SENSOR):
        raise ValueError("invalid HAND v2 sensor header")
    return values[3], SensorSample(
        timestamp_us=values[4],
        reset=bool(values[5]),
        camera_valid=bool(values[6]),
        imu_valid=bool(values[7]),
        wrist_xyz=np.asarray(values[9:12], dtype=float),
        wrist_quaternion_wxyz=np.asarray(values[12:16], dtype=float),
        bend=np.clip(np.asarray(values[22:27], dtype=float) / 4095.0, 0.0, 1.0),
        angular_velocity=np.asarray(values[19:22], dtype=float),
        linear_acceleration=np.asarray(values[16:19], dtype=float),
    )


class UdpReceiver:
    def __init__(self, host: str, port: int) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.socket.setblocking(False)
        self.last_sequence: int | None = None
        self.received = 0
        self.rejected = 0

    def close(self) -> None:
        self.socket.close()

    def poll(self) -> SensorSample | None:
        newest = None
        while True:
            try:
                payload, _ = self.socket.recvfrom(2048)
            except BlockingIOError:
                break
            try:
                sequence, sample = decode_packet(payload)
            except ValueError:
                self.rejected += 1
                continue
            if self.last_sequence is not None and not sample.reset:
                delta = (sequence - self.last_sequence) & 0xFFFFFFFF
                if not 0 < delta < 0x80000000:
                    self.rejected += 1
                    continue
            self.last_sequence = sequence
            self.received += 1
            newest = sample
        return newest


def load_sequence(path: Path) -> list[SensorSample]:
    with np.load(path) as data:
        count = len(data["timestamp_us"])
        zeros = np.zeros((count, 5), dtype=float)
        flex = data["flex_raw"] if "flex_raw" in data else zeros
        return [SensorSample(
            int(data["timestamp_us"][i]), bool(data["camera_valid"][i]), True,
            i == 0, data["wrist_xyz"][i].astype(float),
            data["wrist_quaternion_wxyz"][i].astype(float),
            np.clip(flex[i].astype(float) / 4095.0, 0.0, 1.0),
        ) for i in range(count)]


def demo_sequence(frame_count: int = 360, rate_hz: float = 60.0) -> list[SensorSample]:
    samples = []
    for index in range(frame_count):
        t = index / rate_hz
        half = 0.5 * t
        quaternion = _rpy_quaternion(0.08 * math.sin(half),
                                     0.05 * math.sin(0.7 * t),
                                     0.07 * math.sin(0.4 * t))
        bend = np.zeros(5)
        bend[2] = np.clip(0.5 + 0.6 * math.sin(0.8 * t - 1.2), 0.0, 1.0)
        samples.append(SensorSample(
            round(index * 1_000_000 / rate_hz), True, True, index == 0,
            np.array((0.055 * math.sin(0.45 * t),
                      0.035 * math.sin(0.65 * t),
                      0.31 + 0.07 * math.sin(0.35 * t))),
            quaternion, bend,
        ))
    return samples


def _rpy_quaternion(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return np.array((cr * cp * cy + sr * sp * sy,
                     sr * cp * cy - cr * sp * sy,
                     cr * sp * cy + sr * cp * sy,
                     cr * cp * sy - sr * sp * cy))

