"""Measure stationary drift or one-turn closure from live HAND v2 packets."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import time

import numpy as np

from mano_reference import mano_local_rotation
from mapping import matrix_rpy_degrees, rotation_vector
from protocol import UdpReceiver


def collect(receiver: UdpReceiver, seconds: float, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    reference = None
    previous_time = None
    swept_radians = 0.0
    rows = []
    started = time.monotonic()
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(("elapsed_s", "timestamp_us", "qw", "qx", "qy", "qz",
                         "ax_g", "ay_g", "az_g", "gx_rad_s", "gy_rad_s", "gz_rad_s",
                         "roll_deg", "pitch_deg", "yaw_deg", "attitude_error_deg"))
        while time.monotonic()-started < seconds:
            sample = receiver.poll()
            if sample is None:
                time.sleep(0.002)
                continue
            if reference is None:
                reference = sample.wrist_quaternion_wxyz.copy()
            local = mano_local_rotation(sample.wrist_quaternion_wxyz, reference)
            rpy = matrix_rpy_degrees(local)
            error = math.degrees(float(np.linalg.norm(rotation_vector(local))))
            if previous_time is not None:
                dt = ((sample.timestamp_us-previous_time) & 0xffffffff)/1e6
                if 0 < dt < 0.1:
                    swept_radians += float(np.linalg.norm(sample.angular_velocity))*dt
            previous_time = sample.timestamp_us
            row = (time.monotonic()-started, sample.timestamp_us,
                   *sample.wrist_quaternion_wxyz, *sample.linear_acceleration,
                   *sample.angular_velocity, *rpy, error)
            writer.writerow(row)
            rows.append(row)
    return np.asarray(rows), math.degrees(swept_radians)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47003)
    parser.add_argument("--mode", choices=("static", "circle"), default="static")
    parser.add_argument("--seconds", type=float, default=420.0)
    parser.add_argument("--output", type=Path, default=Path(".runtime/imu_validation.csv"))
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("seconds must be positive")

    receiver = UdpReceiver(args.bind, args.port)
    try:
        if args.mode == "static":
            print(f"保持手背向上且完全静止 {args.seconds:.0f} 秒；测试期间不要触碰桌面。")
        else:
            input("保持起始姿态，按 Enter 开始；随后完整旋转一圈并回到原姿态……")
            print(f"请在 {args.seconds:.0f} 秒内完成一圈，最后保持原姿态。")
        rows, swept = collect(receiver, args.seconds, args.output)
    finally:
        receiver.close()

    if len(rows) < 2:
        raise RuntimeError("没有收到足够的 HAND v2 数据")
    rpy = rows[:, 12:15]
    elapsed = rows[-1, 0]-rows[0, 0]
    print(f"duration={elapsed:.1f}s frames={len(rows)}")
    print(f"endpoint_rpy_deg={rpy[-1, 0]:.3f},{rpy[-1, 1]:.3f},{rpy[-1, 2]:.3f}")
    if args.mode == "static":
        result = float(np.max(np.abs(rpy[:, 2])))
        print(f"max_abs_yaw_deg={result:.3f}")
        passed = result <= 1.0
        print("STATIC_7MIN=" + ("PASS" if passed else "FAIL"))
    else:
        result = float(rows[-1, 15])
        print(f"integrated_rotation_deg={swept:.2f}")
        print(f"closure_error_deg={result:.3f}")
        passed = result <= 2.0
        print("ONE_TURN=" + ("PASS" if passed else "FAIL"))
    print(f"csv={args.output.resolve()}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
