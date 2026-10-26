"""Decode STRN v1 UART frames and apply a three-pose bend calibration."""

import json
import os
from pathlib import Path
import select
import struct
import time

try:
    import termios
except ImportError:
    termios = None


MAGIC = b"STRN"
VERSION = 1
FRAME = struct.Struct("<4sBBHII5HH")


def crc16_ccitt(data):
    crc = 0xffff
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xffff if crc & 0x8000 else (crc << 1) & 0xffff
    return crc


class StrainFrame:
    def __init__(self, sequence, timestamp_us, raw):
        self.sequence = sequence
        self.timestamp_us = timestamp_us
        self.raw = tuple(raw)


class Decoder:
    def __init__(self):
        self.buffer = bytearray()
        self.rejected = 0

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while True:
            start = self.buffer.find(MAGIC)
            if start < 0:
                del self.buffer[:-3]
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < FRAME.size:
                break
            payload = bytes(self.buffer[:FRAME.size])
            values = FRAME.unpack(payload)
            if (values[1] != VERSION or values[3] != FRAME.size
                    or crc16_ccitt(payload[:-2]) != values[-1]):
                self.rejected += 1
                del self.buffer[0]
                continue
            frames.append(StrainFrame(values[4], values[5], values[6:11]))
            del self.buffer[:FRAME.size]
        return frames


class StrainSerial:
    def __init__(self, device="/dev/ttyUSB0"):
        if termios is None:
            raise RuntimeError("StrainSerial requires Linux termios")
        self.fd = os.open(device, os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
        settings = termios.tcgetattr(self.fd)
        settings[0] = 0
        settings[1] = 0
        settings[2] = termios.CS8 | termios.CLOCAL | termios.CREAD
        settings[3] = 0
        settings[4] = termios.B115200
        settings[5] = termios.B115200
        termios.tcsetattr(self.fd, termios.TCSANOW, settings)
        termios.tcflush(self.fd, termios.TCIFLUSH)
        self.decoder = Decoder()

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def poll(self, timeout=0.0):
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return []
        try:
            data = os.read(self.fd, 4096)
        except BlockingIOError:
            return []
        return self.decoder.feed(data)

    def read_frame(self, timeout=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            frames = self.poll(max(0.0, deadline - time.monotonic()))
            if frames:
                return frames[-1]
        raise RuntimeError("No valid STRN frame from UART")

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _traceback):
        self.close()


class Calibration:
    def __init__(self, channels, poses):
        self.channels = tuple(channels)
        self.poses = poses
        for channel in self.channels:
            values = [poses[name][channel] for name in ("open", "half", "fist")]
            if not (values[0] < values[1] < values[2] or values[0] > values[1] > values[2]):
                raise ValueError("Channel {} calibration is not monotonic".format(channel))

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != "strain.calibration.v1":
            raise ValueError("Unsupported strain calibration")
        return cls(data["channels"], data["poses"])

    def map(self, raw):
        output = [0] * 5
        for channel in self.channels:
            points = sorted(((self.poses["open"][channel], 0.0),
                             (self.poses["half"][channel], 0.5),
                             (self.poses["fist"][channel], 1.0)))
            value = raw[channel]
            if value <= points[0][0]:
                bend = points[0][1]
            elif value >= points[2][0]:
                bend = points[2][1]
            else:
                left, right = (points[0], points[1]) if value <= points[1][0] else (points[1], points[2])
                bend = left[1] + (value - left[0]) * (right[1] - left[1]) / (right[0] - left[0])
            output[channel] = int(round(max(0.0, min(1.0, bend)) * 4095.0))
        return tuple(output)
