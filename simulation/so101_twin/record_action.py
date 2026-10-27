"""Record the raw board UDP stream with a short guided countdown."""

from __future__ import annotations

import argparse
from pathlib import Path
import socket
import time

import numpy as np

from action_io import ActionRecording
from protocol import PACKET, decode_packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47003)
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("seconds must be positive")

    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind((args.bind, args.port))
    receiver.settimeout(0.2)
    print("准备录制原始动作；MANO 和机械臂可同时保持打开。")
    print(f"录制时长 {args.seconds:.1f} 秒，3 秒后开始……", flush=True)
    for count in (3, 2, 1):
        print(count, flush=True)
        time.sleep(1.0)
    print("开始动作。", flush=True)

    started = time.monotonic()
    times: list[float] = []
    payloads: list[np.ndarray] = []
    while time.monotonic() - started < args.seconds:
        try:
            payload, _ = receiver.recvfrom(2048)
        except TimeoutError:
            continue
        if len(payload) != PACKET.size:
            continue
        try:
            decode_packet(payload)
        except ValueError:
            continue
        times.append(time.monotonic() - started)
        payloads.append(np.frombuffer(payload, dtype=np.uint8).copy())
    receiver.close()
    if not payloads:
        raise RuntimeError("没有收到 HAND v2 数据，请检查 UDP 中继是否包含本端口")
    recording = ActionRecording(np.asarray(times), np.stack(payloads))
    recording.save(args.output)
    print(f"录制完成：{len(payloads)} 帧，文件 {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
