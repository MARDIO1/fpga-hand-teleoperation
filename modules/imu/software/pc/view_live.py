"""PC live viewer: SSH reads board pose JSONL; saves every received frame locally."""
import argparse
import getpass
from collections import deque
import json
import math
import os
from pathlib import Path
import queue
import shlex
import threading
import time
import tkinter as tk
from tkinter import ttk


def parse_pose(line):
    pose = json.loads(line)
    if pose.get("schema") != "mpu6050.attitude.v1" or not pose.get("valid"):
        raise ValueError("Unsupported or invalid pose frame")
    values = [pose[k] for k in ("yaw_deg", "pitch_deg", "roll_deg")]
    values += list(pose["raw_accel"]) + list(pose["raw_gyro"])
    if len(pose["raw_accel"]) != 3 or len(pose["raw_gyro"]) != 3 or not all(math.isfinite(v) for v in values):
        raise ValueError("Invalid sensor axes or angles")
    if not isinstance(pose["timestamp_us"], int) or pose["timestamp_us"] < 0:
        raise ValueError("Invalid timestamp")
    return pose


def load_ssh():
    import paramiko
    return paramiko


class Viewer:
    def __init__(self, args):
        self.args = args
        self.events = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.client = None
        self.received = 0
        self.history = deque(maxlen=200)
        self.status = "Connecting; keep sensor still during calibration..."
        self.root = tk.Tk()
        self.root.title("MPU6050 · Live hand attitude")
        self.root.geometry("900x650")
        self.root.configure(bg="#101827")
        ttk.Label(self.root, text="MPU6050  |  Raw + Attitude + Timestamp", font=("Segoe UI", 19, "bold")).pack(pady=14)
        self.summary = ttk.Label(self.root, text=self.status, font=("Consolas", 11))
        self.summary.pack()
        self.angles = ttk.Label(self.root, text="Yaw --     Pitch --     Roll --", font=("Consolas", 24, "bold"))
        self.angles.pack(pady=14)
        self.details = ttk.Label(self.root, text="Awaiting valid pose frames", font=("Consolas", 13), justify="left")
        self.details.pack()
        self.canvas = tk.Canvas(self.root, height=260, bg="#111c2d", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=18, pady=14)
        ttk.Label(self.root, text="Yaw is relative and drifts. Angles use sensor axes. Close window to stop PC reception.", font=("Segoe UI", 10)).pack(pady=4)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        threading.Thread(target=self.receive, daemon=True).start()
        self.root.after(100, self.refresh)

    def receive(self):
        try:
            paramiko = load_ssh()
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            self.client = client
            client.connect(self.args.host, username=self.args.user,
                           password=self.args.password, timeout=10, banner_timeout=10, auth_timeout=10)
            client.get_transport().set_keepalive(15)
            self.status = "Connected; waiting for valid frames. Keep the module stationary."
            command = "tail -n 1 -s 0.05 -F -- " + shlex.quote(self.args.remote)
            _, stream, errors = client.exec_command(command)
            self.args.save.parent.mkdir(parents=True, exist_ok=True)
            with self.args.save.open("a", encoding="utf-8") as saved:
                for line in stream:
                    if self.stop.is_set():
                        break
                    try:
                        pose = parse_pose(line)
                    except (ValueError, KeyError, TypeError):
                        continue
                    saved.write(json.dumps(pose, separators=(",", ":"))+"\n")
                    self.received += 1
                    self.status = "Connected  |  %s  |  saved %d frames" % (self.args.host, self.received)
                    if self.events.full():
                        try:
                            self.events.get_nowait()
                        except queue.Empty:
                            pass
                    self.events.put_nowait((pose, time.perf_counter()))
            if not self.stop.is_set():
                self.status = "Disconnected: " + errors.read().decode("utf-8", "replace")[:160]
        except Exception as exc:
            self.status = "Connection error: " + str(exc)
        finally:
            if self.client:
                self.client.close()

    def refresh(self):
        try:
            pose, received_at = self.events.get_nowait()
            self.history.append((received_at, pose))
            self.last = (pose, received_at)
        except queue.Empty:
            pass
        if hasattr(self, "last"):
            pose, received_at = self.last
            age = time.perf_counter()-received_at
            state = self.status if age < 1 else "STALE: no new frames for %.1f seconds" % age
            self.summary.config(text=state)
            self.angles.config(text="Yaw %8.2f   Pitch %8.2f   Roll %8.2f" % tuple(pose[k] for k in ("yaw_deg", "pitch_deg", "roll_deg")))
            self.details.config(text=("PL timestamp: %d us   |   Sequence: %d\n"
                                      "Raw accel: %7d %7d %7d  (8192 LSB/g)\n"
                                      "Raw gyro : %7d %7d %7d  (65.5 LSB/deg/s)\n"
                                      "I2C errors: %d   Dropped: %d   Epoch: %d") %
                                     (pose["timestamp_us"], pose["sequence"], *pose["raw_accel"], *pose["raw_gyro"],
                                      pose["i2c_errors"], pose["dropped_samples"], pose["attitude_epoch"]))
            self.draw()
        else:
            self.summary.config(text=self.status)
        self.root.after(100, self.refresh)

    def draw(self):
        c = self.canvas
        c.delete("all")
        width, height = max(400, c.winfo_width()), max(200, c.winfo_height())
        top, bottom = 28, height-25
        for angle in (-180, -90, 0, 90, 180):
            y = top+(180-angle)/360*(bottom-top)
            c.create_line(42, y, width-15, y, fill="#26344b")
            c.create_text(24, y, text=str(angle), fill="#91a4bf", font=("Consolas", 9))
        for key, color in [("yaw_deg", "#53b8ff"), ("pitch_deg", "#5ee3ae"), ("roll_deg", "#ffbf69")]:
            coords = []
            for i, (_, pose) in enumerate(self.history):
                coords.extend((42+i/199*(width-60), top+(180-pose[key])/360*(bottom-top)))
            if len(coords) >= 4:
                c.create_line(*coords, fill=color, width=2)
        c.create_text(width/2, 12, text="Yaw (blue)   Pitch (green)   Roll (orange) — latest 20 seconds", fill="#cfdaea")

    def close(self):
        self.stop.set()
        if self.client:
            self.client.close()
        self.root.destroy()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", required=True)
    p.add_argument("--user", default="xilinx")
    p.add_argument("--remote", default="/home/xilinx/overlays/mpu6050_studio/pose.jsonl")
    p.add_argument("--save", type=Path, default=Path(__file__).resolve().parents[2]/"data/raw/pc_pose.jsonl")
    args = p.parse_args()
    args.password = os.environ.get("MPU_SSH_PASSWORD") or getpass.getpass("SSH password: ")
    viewer = Viewer(args)
    viewer.root.mainloop()


if __name__ == "__main__":
    main()
