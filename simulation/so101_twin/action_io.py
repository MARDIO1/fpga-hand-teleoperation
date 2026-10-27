"""Lossless HAND v2 recording and replay helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from protocol import PACKET, decode_packet


FORMAT_VERSION = 1


@dataclass(slots=True)
class ActionRecording:
    time_s: np.ndarray
    payloads: np.ndarray

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, format_version=np.uint16(FORMAT_VERSION),
                            time_s=self.time_s.astype(np.float64),
                            payloads=self.payloads.astype(np.uint8))

    @classmethod
    def load(cls, path: Path) -> "ActionRecording":
        with np.load(path) as data:
            if int(data["format_version"].item()) != FORMAT_VERSION:
                raise ValueError("unsupported action recording version")
            time_s = data["time_s"].astype(float)
            payloads = data["payloads"].astype(np.uint8)
        if payloads.ndim != 2 or payloads.shape[1] != PACKET.size:
            raise ValueError("invalid HAND v2 payload array")
        if time_s.shape != (len(payloads),) or np.any(np.diff(time_s) < 0):
            raise ValueError("invalid recording timeline")
        for payload in payloads:
            decode_packet(payload.tobytes())
        return cls(time_s, payloads)


def rewrite_payload(payload: np.ndarray, sequence: int, timestamp_us: int,
                    reset: bool) -> bytes:
    values = list(PACKET.unpack(payload.tobytes()))
    values[3] = sequence & 0xFFFFFFFF
    values[4] = timestamp_us & 0xFFFFFFFF
    values[5] = int(reset)
    return PACKET.pack(*values)
