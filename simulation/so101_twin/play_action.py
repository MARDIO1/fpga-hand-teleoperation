"""GUI player for recorded HAND v2 actions."""

from __future__ import annotations

import argparse
from pathlib import Path
import socket
import tkinter as tk
from tkinter import ttk

from action_io import ActionRecording, rewrite_payload


class Player:
    def __init__(self, root: tk.Tk, recording: ActionRecording,
                 targets: list[int]) -> None:
        self.root = root
        self.recording = recording
        self.targets = targets
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.index = 0
        self.sequence = 0
        self.playing = False
        self.loop = tk.BooleanVar(value=True)
        self.speed = tk.DoubleVar(value=1.0)

        root.title("HAND v2 动作播放器")
        root.geometry("620x190")
        ttk.Label(root, text=f"{len(recording.payloads)} 帧  |  "
                 f"{recording.time_s[-1]:.2f} 秒  |  输出端口 {targets}").pack(pady=12)
        self.scale = ttk.Scale(root, from_=0, to=max(0, len(recording.payloads) - 1),
                               command=self.seek)
        self.scale.pack(fill="x", padx=24)
        self.status = ttk.Label(root, text="已暂停")
        self.status.pack(pady=8)
        row = ttk.Frame(root)
        row.pack()
        ttk.Button(row, text="播放 / 暂停", command=self.toggle).pack(side="left", padx=5)
        ttk.Button(row, text="回到开头", command=self.rewind).pack(side="left", padx=5)
        ttk.Checkbutton(row, text="循环", variable=self.loop).pack(side="left", padx=10)
        ttk.Label(row, text="速度").pack(side="left")
        ttk.Combobox(row, textvariable=self.speed, width=6, state="readonly",
                     values=(0.25, 0.5, 1.0, 1.5, 2.0)).pack(side="left", padx=5)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def seek(self, value: str) -> None:
        self.index = int(float(value))
        self.status.configure(text=f"帧 {self.index + 1}/{len(self.recording.payloads)}")

    def toggle(self) -> None:
        self.playing = not self.playing
        if self.playing:
            self.status.configure(text="播放中")
            self.root.after(0, self.tick)
        else:
            self.status.configure(text="已暂停")

    def rewind(self) -> None:
        self.index = 0
        self.scale.set(0)

    def tick(self) -> None:
        if not self.playing:
            return
        count = len(self.recording.payloads)
        if self.index >= count:
            if not self.loop.get():
                self.playing = False
                self.status.configure(text="播放完成")
                return
            self.index = 0
        reset = self.index == 0
        timestamp_us = int(self.recording.time_s[self.index] * 1_000_000)
        payload = rewrite_payload(self.recording.payloads[self.index], self.sequence,
                                  timestamp_us, reset)
        self.sequence += 1
        for port in self.targets:
            self.socket.sendto(payload, ("127.0.0.1", port))
        self.scale.set(self.index)
        current = self.index
        self.index += 1
        if self.index < count:
            delay = self.recording.time_s[self.index] - self.recording.time_s[current]
        else:
            delay = 1.0 / 60.0
        self.root.after(max(1, round(1000.0 * delay / self.speed.get())), self.tick)

    def close(self) -> None:
        self.socket.close()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--targets", type=int, nargs="+", default=(47001, 47002))
    args = parser.parse_args()
    root = tk.Tk()
    Player(root, ActionRecording.load(args.recording), list(args.targets))
    root.mainloop()


if __name__ == "__main__":
    main()
