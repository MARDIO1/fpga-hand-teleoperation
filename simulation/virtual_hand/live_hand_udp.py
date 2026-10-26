"""Receive live HAND v2 sensor packets and map the first-board sensors."""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass

import numpy as np

from hand_sequence import HandFrame, SensorFrame


MAGIC = 0x444E4148
VERSION = 2
SENSOR = 1
PORT = 47000
SENSOR_PACKET = struct.Struct("<IHHIIBBBB13f5HH")
PALM_DOWN_QUATERNION = np.array((2**-0.5, 2**-0.5, 0.0, 0.0))
IMU_TO_HAND_QUATERNION = np.array((0.0, 2**-0.5, 2**-0.5, 0.0))


@dataclass(slots=True)
class ReceivedFrame:
    sequence: int
    reset: bool
    imu_valid: bool
    sensor: SensorFrame


def decode_packet(payload: bytes) -> ReceivedFrame:
    """Decode one little-endian HAND v2 sensor packet."""
    if len(payload) != SENSOR_PACKET.size:
        raise ValueError(f"expected {SENSOR_PACKET.size} bytes, got {len(payload)}")
    values = SENSOR_PACKET.unpack(payload)
    if values[:3] != (MAGIC, VERSION, SENSOR):
        raise ValueError("invalid HAND v2 sensor header")

    sensor = SensorFrame(
        timestamp_us=values[4],
        camera_valid=bool(values[6]),
        wrist_xyz=np.asarray(values[9:12], dtype=float),
        wrist_quaternion_wxyz=np.asarray(values[12:16], dtype=float),
        linear_acceleration=np.asarray(values[16:19], dtype=float),
        angular_velocity=np.asarray(values[19:22], dtype=float),
        flex_raw=np.asarray(values[22:27], dtype=np.uint16),
    )
    return ReceivedFrame(values[3], bool(values[5]), bool(values[7]), sensor)


def _newer(sequence: int, previous: int) -> bool:
    difference = (sequence - previous) & 0xFFFFFFFF
    return 0 < difference < 0x80000000


class UdpSensorReceiver:
    """Non-blocking receiver that returns only the newest valid packet."""

    def __init__(self, host: str = "0.0.0.0", port: int = PORT) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.socket.setblocking(False)
        self.last_sequence: int | None = None
        self.received = 0
        self.dropped = 0
        self.rejected = 0

    def close(self) -> None:
        self.socket.close()

    def poll(self) -> ReceivedFrame | None:
        newest = None
        while True:
            try:
                payload, _ = self.socket.recvfrom(2048)
            except BlockingIOError:
                break
            try:
                frame = decode_packet(payload)
            except ValueError:
                self.rejected += 1
                continue
            if self.last_sequence is not None and not frame.reset:
                if not _newer(frame.sequence, self.last_sequence):
                    self.rejected += 1
                    continue
                self.dropped += ((frame.sequence - self.last_sequence) & 0xFFFFFFFF) - 1
            self.last_sequence = frame.sequence
            self.received += 1
            newest = frame
        return newest


def _multiply_quaternions(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array((
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    ))


class FirstBoardMapper:
    """Map one middle-finger strain channel and one dorsal IMU to MANO inputs."""

    def __init__(self) -> None:
        self.reference_quaternion: np.ndarray | None = None
        self.quaternion = PALM_DOWN_QUATERNION.copy()
        self.position = np.array((0.0, 0.0, 0.31))

    def reset_orientation(self) -> None:
        self.reference_quaternion = None

    def update(self, frame: ReceivedFrame) -> HandFrame:
        bends = np.clip(frame.sensor.flex_raw.astype(float) / 4095.0, 0.0, 1.0)

        if frame.sensor.camera_valid:
            self.position = np.asarray(frame.sensor.wrist_xyz, dtype=float).copy()

        if frame.reset:
            self.reset_orientation()
        if frame.imu_valid:
            quaternion = np.asarray(frame.sensor.wrist_quaternion_wxyz, dtype=float)
            norm = float(np.linalg.norm(quaternion))
            if norm > 1e-6:
                quaternion /= norm
                if self.reference_quaternion is None:
                    self.reference_quaternion = quaternion.copy()
                reference_inverse = self.reference_quaternion * np.array((1.0, -1.0, -1.0, -1.0))
                relative = _multiply_quaternions(quaternion, reference_inverse)
                mount_inverse = IMU_TO_HAND_QUATERNION * np.array((1.0, -1.0, -1.0, -1.0))
                relative = _multiply_quaternions(
                    _multiply_quaternions(IMU_TO_HAND_QUATERNION, relative), mount_inverse)
                self.quaternion = _multiply_quaternions(relative, PALM_DOWN_QUATERNION)
                self.quaternion /= np.linalg.norm(self.quaternion)

        return HandFrame(frame.sensor.timestamp_us, self.position.copy(),
                         self.quaternion.copy(), bends)
