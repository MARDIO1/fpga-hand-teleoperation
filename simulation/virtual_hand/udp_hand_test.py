"""Replay a canonical hand sequence through the PYNQ UDP bridge."""
import argparse
import socket
import struct
import time
from pathlib import Path

from hand_sequence import load_sequence


MAGIC = 0x444E4148
VERSION = 2
REQUEST = 1
REPLY = 2
REQUEST_FORMAT = "<IHHIIBBBB13f5HH"
REPLY_FORMAT = "<IHHII3f9f5f5fHBB"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.2.99")
    parser.add_argument("--port", type=int, default=47000)
    parser.add_argument("--rate", type=float, default=60.0)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()

    frames = load_sequence(args.input)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.02)
    period = 1.0 / args.rate
    latency_ms = []
    lost = 0

    for sequence, frame in enumerate(frames[:args.count]):
        packet = struct.pack(
            REQUEST_FORMAT, MAGIC, VERSION, REQUEST, sequence, frame.timestamp_us,
            sequence == 0, frame.camera_valid, True, 0,
            *frame.wrist_xyz, *frame.wrist_quaternion_wxyz,
            *frame.linear_acceleration, *frame.angular_velocity, *frame.flex_raw, 0,
        )
        started = time.perf_counter()
        sock.sendto(packet, (args.host, args.port))
        try:
            reply = sock.recv(108)
            fields = struct.unpack(REPLY_FORMAT, reply)
            if fields[:4] != (MAGIC, VERSION, REPLY, sequence):
                raise RuntimeError("unexpected reply header")
            latency_ms.append((time.perf_counter() - started) * 1000.0)
        except socket.timeout:
            lost += 1
        remaining = period - (time.perf_counter() - started)
        if remaining > 0:
            time.sleep(remaining)

    if latency_ms:
        print(f"received={len(latency_ms)} lost={lost} "
              f"latency_ms avg={sum(latency_ms) / len(latency_ms):.3f} max={max(latency_ms):.3f}")
    else:
        print(f"received=0 lost={lost}")


if __name__ == "__main__":
    main()
