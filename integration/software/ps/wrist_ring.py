"""Recover the wrist centre from a calibrated, partly visible marker ring."""

import itertools
import json
import math
from pathlib import Path
from statistics import median
from typing import NamedTuple


class RingMarker(NamedTuple):
    marker_id: str
    color: str
    offset_sensor_m: tuple


class WristEstimate(NamedTuple):
    xyz_camera_m: tuple
    used_markers: int
    residual_m: float


def _matrix(document, name):
    value = document[name]
    if (not isinstance(value, list) or len(value) != 3
            or any(not isinstance(row, list) or len(row) != 3 for row in value)):
        raise ValueError(name + " must be 3x3")
    result = tuple(tuple(float(item) for item in row) for row in value)
    if not all(math.isfinite(item) for row in result for item in row):
        raise ValueError(name + " must be finite")
    return result


def _matmul(a, b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def _matvec(matrix, vector):
    return tuple(sum(row[i]*vector[i] for i in range(3)) for row in matrix)


def _sub(a, b):
    return tuple(x-y for x, y in zip(a, b))


def _distance(a, b):
    return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def quaternion_matrix(quaternion):
    w, x, y, z = (float(value) for value in quaternion)
    norm = math.sqrt(w*w+x*x+y*y+z*z)
    if not math.isfinite(norm) or norm < 1e-9:
        raise ValueError("invalid quaternion")
    w, x, y, z = (value/norm for value in (w, x, y, z))
    return (
        (1-2*(y*y+z*z), 2*(x*y-w*z), 2*(x*z+w*y)),
        (2*(x*y+w*z), 1-2*(x*x+z*z), 2*(y*z-w*x)),
        (2*(x*z-w*y), 2*(y*z+w*x), 1-2*(x*x+y*y)),
    )


class RingCalibration:
    def __init__(self, camera_from_imu_world, markers,
                 max_residual_m=0.015, max_jump_m=0.15):
        self.camera_from_imu_world = camera_from_imu_world
        self.markers = tuple(markers)
        self.max_residual_m = float(max_residual_m)
        self.max_jump_m = float(max_jump_m)
        if len(self.markers) < 3 or self.max_residual_m <= 0 or self.max_jump_m <= 0:
            raise ValueError("ring needs >=3 markers and positive limits")
        if len({marker.marker_id for marker in self.markers}) != len(self.markers):
            raise ValueError("marker ids must be unique")

    @classmethod
    def load(cls, path):
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if document.get("schema") != "wrist-ring-calibration.v1":
            raise ValueError("unsupported wrist ring calibration")
        markers = []
        for item in document["markers"]:
            offset = tuple(float(value) for value in item["offset_sensor_m"])
            if len(offset) != 3 or not all(math.isfinite(value) for value in offset):
                raise ValueError("invalid marker offset")
            markers.append(RingMarker(str(item["id"]), str(item["color"]), offset))
        return cls(_matrix(document, "camera_from_imu_world"), markers,
                   document.get("max_residual_m", 0.015),
                   document.get("max_jump_m", 0.15))


class WristRingTracker:
    def __init__(self, calibration):
        self.calibration = calibration
        self.previous = None

    def update(self, observations, quaternion_wxyz):
        observations = tuple(marker for marker in observations
                             if marker.color in {item.color for item in self.calibration.markers})
        if not observations:
            return None
        rotation = _matmul(self.calibration.camera_from_imu_world,
                           quaternion_matrix(quaternion_wxyz))
        candidates = []
        # A moving finger marker may share a colour with the rigid cuff. Try
        # subsets so one extra yellow observation cannot invalidate the ring.
        maximum = min(len(observations), len(self.calibration.markers))
        for used in range(maximum, 0, -1):
            for selected in itertools.combinations(observations, used):
                compatible = [tuple(index for index, model in enumerate(self.calibration.markers)
                                    if model.color == observation.color)
                              for observation in selected]
                if any(not indexes for indexes in compatible):
                    continue
                for assignment in itertools.product(*compatible):
                    if len(set(assignment)) != len(assignment):
                        continue
                    centres = []
                    for observation, model_index in zip(selected, assignment):
                        offset = _matvec(rotation,
                                         self.calibration.markers[model_index].offset_sensor_m)
                        centres.append(_sub(observation.xyz_m, offset))
                    centre = tuple(median(point[axis] for point in centres) for axis in range(3))
                    residual = max(_distance(point, centre) for point in centres)
                    if residual > self.calibration.max_residual_m:
                        continue
                    jump = _distance(centre, self.previous) if self.previous is not None else 0.0
                    unique_color = len(compatible[0]) == 1 if used == 1 else True
                    if used == 1 and self.previous is None and not unique_color:
                        continue
                    score = residual + 0.1*jump
                    candidates.append((-used, score, centre, residual))
            if candidates:
                break
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        _, _, centre, residual = candidates[0]
        if (self.previous is not None
                and _distance(centre, self.previous) > self.calibration.max_jump_m):
            return None
        # Reject unresolved repeated-colour symmetry rather than jump between solutions.
        if len(candidates) > 1 and _distance(centre, candidates[1][2]) > 0.02:
            if abs(candidates[1][1]-candidates[0][1]) < 0.001:
                return None
        self.previous = centre
        return WristEstimate(centre, -candidates[0][0], residual)
