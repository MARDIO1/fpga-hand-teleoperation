"""Capture a rich CSV trace across raw IMU, MANO reference and SO-101 layers."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import time

import numpy as np

from controller import So101Twin
from mano_reference import mano_local_rotation
from mapping import matrix_rpy_degrees, rotation_vector
from protocol import UdpReceiver


HEADER = (
    "pc_time_s", "sensor_time_us",
    "qw", "qx", "qy", "qz", "gx", "gy", "gz",
    "mano_roll_deg", "mano_pitch_deg", "mano_yaw_deg",
    "rotvec_x_deg", "rotvec_y_deg", "rotvec_z_deg",
    "target_x", "target_y", "target_z",
    "actual_x", "actual_y", "actual_z",
    "target_roll_deg", "target_pitch_deg", "target_yaw_deg",
    "actual_roll_deg", "actual_pitch_deg", "actual_yaw_deg",
    "position_error_mm", "axis_error_deg",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47003)
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--output", type=Path, default=Path(".runtime/live_debug.csv"))
    args = parser.parse_args()

    receiver = UdpReceiver(args.bind, args.port)
    twin = So101Twin()
    reference = None
    rows = []
    started = time.monotonic()
    next_print = started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(HEADER)
            while time.monotonic() - started < args.seconds:
                sample = receiver.poll()
                if sample is None:
                    time.sleep(0.002)
                    continue
                quaternion = sample.wrist_quaternion_wxyz
                if reference is None or sample.reset:
                    reference = quaternion.copy()
                local = mano_local_rotation(quaternion, reference)
                mano_rpy = matrix_rpy_degrees(local)
                rotvec = np.rad2deg(rotation_vector(local))
                twin.step(sample)
                actual = twin.data.site("gripperframe")
                target_rpy = matrix_rpy_degrees(twin.target_rotation)
                actual_rpy = matrix_rpy_degrees(actual.xmat.reshape(3, 3))
                now = time.monotonic() - started
                row = np.concatenate((
                    (now, sample.timestamp_us), quaternion, sample.angular_velocity,
                    mano_rpy, rotvec, twin.target_position, actual.xpos,
                    target_rpy, actual_rpy,
                    (twin.position_error * 1000.0, np.rad2deg(twin.axis_error)),
                ))
                writer.writerow(row)
                stream.flush()
                rows.append(row)
                if time.monotonic() >= next_print:
                    print("MANO_RPY=" + ",".join(f"{v:.2f}" for v in mano_rpy)
                          + " gyro=" + ",".join(f"{v:.3f}" for v in sample.angular_velocity)
                          + " target_RPY=" + ",".join(f"{v:.2f}" for v in target_rpy),
                          flush=True)
                    next_print = time.monotonic() + 0.5
    finally:
        receiver.close()

    data = np.asarray(rows)
    if len(data) >= 2:
        elapsed = data[-1, 0] - data[0, 0]
        yaw_drift = (data[-1, 11] - data[0, 11]) / max(elapsed, 1e-6)
        print(f"frames={len(data)} yaw_drift_deg_s={yaw_drift:.4f}")
    print(f"csv={args.output.resolve()}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
