"""Use the proven MANO receiver's orientation convention as the reference."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np


VIRTUAL_HAND = Path(__file__).resolve().parent.parent / "virtual_hand"
if str(VIRTUAL_HAND) not in sys.path:
    sys.path.insert(0, str(VIRTUAL_HAND))

from hand_sequence import quaternion_to_rotation  # noqa: E402
from live_hand_udp import (IMU_TO_HAND_QUATERNION, PALM_DOWN_QUATERNION,
                           _multiply_quaternions)  # noqa: E402
from mano_mapping import MANO_TO_HAND_FRAME  # noqa: E402


MANO_NEUTRAL_ROTATION = (
    quaternion_to_rotation(PALM_DOWN_QUATERNION) @ MANO_TO_HAND_FRAME
)
IMU_TO_HAND_ROTATION = quaternion_to_rotation(IMU_TO_HAND_QUATERNION)


def mano_relative_rotation(current: np.ndarray, reference: np.ndarray) -> np.ndarray:
    reference_inverse = reference * np.array((1.0, -1.0, -1.0, -1.0))
    relative = _multiply_quaternions(current, reference_inverse)
    mount_inverse = IMU_TO_HAND_QUATERNION * np.array((1.0, -1.0, -1.0, -1.0))
    corrected = _multiply_quaternions(
        _multiply_quaternions(IMU_TO_HAND_QUATERNION, relative), mount_inverse)
    return quaternion_to_rotation(corrected)


def mano_local_rotation(current: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Express MANO's live palm rotation in its neutral palm-local frame."""
    relative = mano_relative_rotation(current, reference)
    return MANO_NEUTRAL_ROTATION.T @ relative @ MANO_NEUTRAL_ROTATION
