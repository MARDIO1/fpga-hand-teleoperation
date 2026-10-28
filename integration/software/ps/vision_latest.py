"""Read the optimized stereo module's atomic latest.json output."""

import json
import math
from pathlib import Path
import time
from typing import NamedTuple


class VisionMarker(NamedTuple):
    color: str
    xyz_m: tuple


class VisionSample(NamedTuple):
    sequence: int
    timestamp_us: int
    markers: tuple


class LatestVision:
    def __init__(self, path, max_age=0.2, colors=()):
        self.path = Path(path)
        self.max_age = max_age
        self.colors = set(colors)
        self.mtime_ns = None
        self.received_at = None
        self.sample = None

    def poll(self, now=None):
        now = time.monotonic() if now is None else now
        try:
            mtime_ns = self.path.stat().st_mtime_ns
            if mtime_ns != self.mtime_ns:
                document = json.loads(self.path.read_text(encoding="utf-8"))
                self.sample = self._decode(document)
                self.mtime_ns = mtime_ns
                self.received_at = now
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.sample = None
        if (self.sample is not None and self.received_at is not None
                and now-self.received_at <= self.max_age):
            return self.sample
        return None

    def _decode(self, document):
        if document.get("frame_errors") or not document.get("metric_coordinates_available"):
            raise ValueError("invalid stereo frame")
        selected = document.get("selected", {}).get("L", [])
        markers = []
        for match in document.get("matches", []):
            if not match.get("xyz_valid"):
                continue
            left_index = int(match["left"])
            color = match.get("color")
            if color is None and 0 <= left_index < len(selected):
                color = selected[left_index].get("color")
            if self.colors and color not in self.colors:
                continue
            xyz = match.get("xyz_mm")
            if (not isinstance(xyz, list) or len(xyz) != 3
                    or not all(isinstance(value, (int, float)) and math.isfinite(value)
                               for value in xyz)):
                raise ValueError("invalid stereo XYZ")
            markers.append(VisionMarker(color, tuple(value*0.001 for value in xyz)))
        if not markers:
            raise ValueError("no selected stereo marker")
        sequence = int(document.get("source_frame_id", document["snapshot_sequence"]))
        timestamp = int(document["capture_boundary_timestamp_us"])
        if sequence < 0 or timestamp < 0:
            raise ValueError("invalid stereo sequence or timestamp")
        return VisionSample(sequence & 0xffffffff, timestamp & 0xffffffff,
                            tuple(markers))
