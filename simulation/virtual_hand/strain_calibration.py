"""Three-pose calibration for five raw strain channels."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


FINGERS = ("thumb", "index", "middle", "ring", "little")
BEND_POINTS = np.array((0.0, 0.5, 1.0))


@dataclass(slots=True)
class StrainCalibration:
    raw_points: np.ndarray  # finger x (open, half, fist)

    def __post_init__(self) -> None:
        self.raw_points = np.asarray(self.raw_points, dtype=float)
        if self.raw_points.shape != (5, 3):
            raise ValueError("raw_points must have shape [5,3]")
        first = self.raw_points[:, 1] - self.raw_points[:, 0]
        second = self.raw_points[:, 2] - self.raw_points[:, 1]
        if np.any(first * second <= 0):
            raise ValueError("each finger must change monotonically from open to half to fist")

    @classmethod
    def default(cls) -> "StrainCalibration":
        return cls(np.tile(np.array((300.0, 2000.0, 3700.0)), (5, 1)))

    @classmethod
    def fit(cls, opened: np.ndarray, half: np.ndarray, fist: np.ndarray) -> "StrainCalibration":
        samples = [np.asarray(values, dtype=float) for values in (opened, half, fist)]
        if any(values.ndim != 2 or values.shape[1] != 5 for values in samples):
            raise ValueError("open, half and fist samples must each have shape [N,5]")
        return cls(np.stack([np.median(values, axis=0) for values in samples], axis=1))

    def decode(self, flex_raw: np.ndarray) -> np.ndarray:
        raw = np.asarray(flex_raw, dtype=float)
        if raw.shape != (5,):
            raise ValueError("expected flex_raw[5]")
        bend = np.empty(5)
        for finger in range(5):
            points = self.raw_points[finger]
            order = np.argsort(points)
            bend[finger] = np.interp(raw[finger], points[order], BEND_POINTS[order])
        return bend

    def encode(self, bend: np.ndarray) -> np.ndarray:
        values = np.clip(np.asarray(bend, dtype=float), 0.0, 1.0)
        return np.array([np.interp(values[i], BEND_POINTS, self.raw_points[i]) for i in range(5)])

    def save(self, path: Path) -> None:
        payload = {"version": 1, "fingers": FINGERS, "raw_points": self.raw_points.tolist()}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "StrainCalibration":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or tuple(payload.get("fingers", ())) != FINGERS:
            raise ValueError("unsupported strain calibration")
        points = np.asarray(payload["raw_points"], dtype=float)
        return cls(points)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path, help="NPZ containing open, half and fist arrays [N,5]")
    parser.add_argument("--output", type=Path, default=Path("strain_calibration.json"))
    args = parser.parse_args()
    with np.load(args.samples) as data:
        calibration = StrainCalibration.fit(data["open"], data["half"], data["fist"])
    calibration.save(args.output)
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
