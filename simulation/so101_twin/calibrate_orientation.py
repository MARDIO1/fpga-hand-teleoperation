"""Guided live calibration of hand motion axes to robot roll, pitch and yaw."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import time

import numpy as np

from mano_reference import IMU_TO_HAND_ROTATION
from mapping import quaternion_matrix, rotation_vector
from protocol import decode_packet


PROMPTS = (
    ("roll", "手指继续指向正前方；只翻转前臂，让拇指侧下沉、小指侧抬起"),
    ("pitch", "手背继续朝上且不左右转；只抬高手指端，像向上示意"),
    ("yaw", "手背继续朝上且不翻腕；在水平面内让手指方向转向右侧"),
)


def mean_quaternion(quaternions: list[np.ndarray]) -> np.ndarray:
    reference = quaternions[0]
    aligned = [q if q @ reference >= 0.0 else -q for q in quaternions]
    mean = np.mean(aligned, axis=0)
    return mean / np.linalg.norm(mean)


def capture(receiver: socket.socket, seconds: float) -> np.ndarray:
    deadline = time.monotonic() + seconds
    quaternions: list[np.ndarray] = []
    while time.monotonic() < deadline:
        try:
            payload, _ = receiver.recvfrom(2048)
        except TimeoutError:
            continue
        _, sample = decode_packet(payload)
        if sample.imu_valid and np.linalg.norm(sample.wrist_quaternion_wxyz) > 1e-6:
            quaternion = sample.wrist_quaternion_wxyz.copy()
            quaternions.append(quaternion / np.linalg.norm(quaternion))
    if len(quaternions) < 10:
        raise RuntimeError("有效 IMU 样本不足")
    return mean_quaternion(quaternions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47003)
    parser.add_argument("--seconds", type=float, default=1.0)
    parser.add_argument("--output", type=Path,
                        default=Path("orientation_calibration.json"))
    args = parser.parse_args()

    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind((args.bind, args.port))
    receiver.settimeout(0.2)
    print("SO-101 姿态引导校准", flush=True)
    print("每一步先摆好并保持姿态，再按 Enter；采样期间不要移动。", flush=True)
    input("\n手背向上、手指向前，保持标准姿态。按 Enter 采集零点……")
    neutral = capture(receiver, args.seconds)
    neutral_inverse = neutral * np.array((1.0, -1.0, -1.0, -1.0))

    axes = []
    magnitudes = []
    for name, prompt in PROMPTS:
        while True:
            input(f"\n{name.upper()}：{prompt}。只做约 30°，保持后按 Enter 采集……")
            quaternion = capture(receiver, args.seconds)
            qn = quaternion_matrix(quaternion)
            qr = quaternion_matrix(neutral_inverse)
            relative = qn @ qr
            hand_relative = IMU_TO_HAND_ROTATION @ relative @ IMU_TO_HAND_ROTATION.T
            vector = rotation_vector(hand_relative)
            magnitude = float(np.linalg.norm(vector))
            degrees = np.rad2deg(magnitude)
            if degrees < 15.0:
                print(f"动作只有 {degrees:.1f}°，太小；请回到标准姿态后重做。", flush=True)
                continue
            if degrees > 55.0:
                print(f"动作达到 {degrees:.1f}°，太大且容易串轴；请回到标准姿态，只做约 30°。",
                      flush=True)
                continue
            break
        axes.append(vector / magnitude)
        magnitudes.append(degrees)
        print(f"已采集 {name}: {magnitudes[-1]:.1f}°", flush=True)
        input("请回到标准姿态，按 Enter 继续……")

    basis = np.column_stack(axes)
    names = [item[0] for item in PROMPTS]
    for first in range(3):
        print(f"{names[first]} 轴 = {axes[first].round(3).tolist()}")
        for second in range(first + 1, 3):
            separation = np.rad2deg(np.arccos(np.clip(abs(axes[first] @ axes[second]),
                                                    -1.0, 1.0)))
            print(f"  与 {names[second]} 的轴夹角：{separation:.1f}°")
    condition = float(np.linalg.cond(basis))
    if condition > 4.0:
        raise RuntimeError(f"三个动作轴仍难以区分，条件数 {condition:.2f}；"
                           "查看上面的最小轴夹角并重做对应动作")
    sensor_to_control = np.linalg.inv(basis)
    result = {
        "format_version": 1,
        "sensor_to_control": sensor_to_control.tolist(),
        "captured_degrees": dict(zip((p[0] for p in PROMPTS), magnitudes, strict=True)),
        "condition_number": condition,
        "yaw_gain": 1.0,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    receiver.close()
    print(f"\n校准完成：{args.output.resolve()}")
    print(f"轴条件数：{condition:.2f}（越接近 1 越好）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
