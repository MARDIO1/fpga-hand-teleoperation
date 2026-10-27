"""Live window showing every raw field in the HAND v2 sensor packet."""

from __future__ import annotations

import argparse
import socket
import time
import tkinter as tk
from tkinter import ttk

import numpy as np

from mano_reference import mano_local_rotation
from mapping import matrix_rpy_degrees, rotation_vector
from protocol import PACKET, decode_packet


class SensorMonitor:
    def __init__(self, root: tk.Tk, host: str, port: int) -> None:
        self.root = root
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((host, port))
        self.socket.setblocking(False)
        self.reference = None
        self.last_sequence = None
        self.received = 0
        self.dropped = 0
        self.started = time.monotonic()
        self.latest = None

        root.title("HAND v2 原始传感器监视器")
        root.geometry("760x520")
        frame = ttk.Frame(root, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="HAND v2 实时原始数据",
                  font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text="原始字段不经过机械臂映射；MANO 局部姿态仅作对照。",
                  foreground="#555555").pack(anchor="w", pady=(2, 14))
        self.labels: dict[str, ttk.Label] = {}
        for name in ("状态", "包统计", "时间戳", "视觉 XYZ", "四元数 WXYZ",
                     "加速度 XYZ", "角速度 XYZ", "应变原始值",
                     "MANO 局部 RPY", "MANO 旋转向量"):
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=5)
            ttk.Label(row, text=name, width=18).pack(side="left")
            label = ttk.Label(row, text="等待数据……", font=("Consolas", 11))
            label.pack(side="left", fill="x")
            self.labels[name] = label
        ttk.Button(frame, text="重新设定姿态零点", command=self.reset).pack(anchor="w", pady=14)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(10, self.poll)

    def reset(self) -> None:
        self.reference = None

    @staticmethod
    def vector(values, digits=4) -> str:
        return "[" + ", ".join(f"{float(value): .{digits}f}" for value in values) + "]"

    def poll(self) -> None:
        while True:
            try:
                payload, address = self.socket.recvfrom(2048)
            except BlockingIOError:
                break
            try:
                sequence, sample = decode_packet(payload)
                values = PACKET.unpack(payload)
            except ValueError:
                continue
            if self.last_sequence is not None:
                delta = (sequence - self.last_sequence) & 0xFFFFFFFF
                if 0 < delta < 0x80000000:
                    self.dropped += max(0, delta - 1)
            self.last_sequence = sequence
            self.received += 1
            self.latest = (address, sequence, sample, values)
        if self.latest is not None:
            address, sequence, sample, values = self.latest
            quaternion = sample.wrist_quaternion_wxyz
            if self.reference is None or sample.reset:
                self.reference = quaternion.copy()
            local = mano_local_rotation(quaternion, self.reference)
            rpy = matrix_rpy_degrees(local)
            rotvec = np.rad2deg(rotation_vector(local))
            elapsed = max(time.monotonic() - self.started, 1e-6)
            flags = (f"reset={int(sample.reset)} camera={int(sample.camera_valid)} "
                     f"imu={int(sample.imu_valid)} source={address[0]}:{address[1]}")
            self.labels["状态"].configure(text=flags)
            self.labels["包统计"].configure(
                text=f"seq={sequence} received={self.received} dropped={self.dropped} rate={self.received/elapsed:.1f} Hz")
            self.labels["时间戳"].configure(text=f"{sample.timestamp_us} us")
            self.labels["视觉 XYZ"].configure(text=self.vector(sample.wrist_xyz))
            self.labels["四元数 WXYZ"].configure(text=self.vector(quaternion, 6))
            self.labels["加速度 XYZ"].configure(text=self.vector(sample.linear_acceleration))
            self.labels["角速度 XYZ"].configure(text=self.vector(sample.angular_velocity))
            self.labels["应变原始值"].configure(text=str(list(values[22:27])))
            self.labels["MANO 局部 RPY"].configure(text=self.vector(rpy, 2) + " deg")
            self.labels["MANO 旋转向量"].configure(text=self.vector(rotvec, 2) + " deg")
        self.root.after(50, self.poll)

    def close(self) -> None:
        self.socket.close()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47004)
    args = parser.parse_args()
    root = tk.Tk()
    SensorMonitor(root, args.bind, args.port)
    root.mainloop()


if __name__ == "__main__":
    main()
