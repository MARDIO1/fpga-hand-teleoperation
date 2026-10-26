"""Map camera, dorsal IMU and five bends to the 45-DoF MANO hand."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hand_sequence import HandFrame, quaternion_to_rotation


FINGERS = ("thumb", "index", "middle", "ring", "little")
MANO_FINGERS = ("thumb", "index", "middle", "ring", "pinky")
BEND_GAIN = (1.05, 1.20, 0.85)
SPREAD_GAIN = 0.42
SPREAD_OPEN = np.array((0.45, 0.55, 0.18, -0.18, -0.55))
SPREAD_CLOSED = np.array((-0.18, 0.08, 0.03, -0.03, -0.08))
MANO_TO_HAND_FRAME = np.array(
    ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
    dtype=np.float64,
)


@dataclass(slots=True)
class ManoFrame:
    wrist_xyz: np.ndarray
    wrist_rpy: np.ndarray
    joint_angles: dict[str, float]

    def as_upstream_frame(self) -> dict:
        return {
            "wrist_xyz": self.wrist_xyz.tolist(),
            "wrist_rpy": self.wrist_rpy.tolist(),
            "joint_angles": self.joint_angles,
        }


def _rotation_to_xyz(rotation: np.ndarray) -> np.ndarray:
    """Convert a rotation matrix to intrinsic XYZ Euler angles."""
    sy = float(np.clip(rotation[0, 2], -1.0, 1.0))
    pitch = np.arcsin(sy)
    if abs(np.cos(pitch)) > 1e-7:
        roll = np.arctan2(-float(rotation[1, 2]), float(rotation[2, 2]))
        yaw = np.arctan2(-float(rotation[0, 1]), float(rotation[0, 0]))
    else:
        roll = np.arctan2(float(rotation[2, 1]), float(rotation[1, 1]))
        yaw = 0.0
    return np.array((roll, pitch, yaw), dtype=np.float64)


def map_hand_pose(frame: HandFrame) -> ManoFrame:
    """Map camera XYZ, dorsal IMU quaternion and five bends to MANO."""
    position = np.asarray(frame.wrist_xyz, dtype=np.float64)
    bend = np.clip(np.asarray(frame.bend, dtype=np.float64), 0.0, 1.0)
    quaternion = np.asarray(frame.wrist_quaternion_wxyz, dtype=np.float64)
    if position.shape != (3,) or bend.shape != (5,) or quaternion.shape != (4,):
        raise ValueError("expected wrist_xyz[3], quaternion_wxyz[4], bend[5]")
    rotation = quaternion_to_rotation(quaternion)
    spread = SPREAD_OPEN + bend * (SPREAD_CLOSED - SPREAD_OPEN)

    joints: dict[str, float] = {}
    for index, finger in enumerate(MANO_FINGERS):
        for segment, gain in enumerate(BEND_GAIN, start=1):
            prefix = f"right_{finger}{segment}"
            joints[f"{prefix}_x"] = 0.0
            joints[f"{prefix}_y"] = SPREAD_GAIN * float(spread[index]) if segment == 1 else 0.0
            joints[f"{prefix}_z"] = gain * float(bend[index])

    # Thumb opposition is shared by its base spread and bend components.
    joints["right_thumb1_x"] = 1.15 * float(bend[0])
    joints["right_thumb1_y"] = 0.55 * float(spread[0])
    joints["right_thumb1_z"] = 0.65 * float(bend[0])
    joints["right_thumb2_z"] = 1.00 * float(bend[0])
    joints["right_thumb3_z"] = 0.75 * float(bend[0])
    mano_rotation = rotation @ MANO_TO_HAND_FRAME
    return ManoFrame(position.copy(), _rotation_to_xyz(mano_rotation), joints)
