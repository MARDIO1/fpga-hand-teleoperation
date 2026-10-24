"""Send exported hand packets to the PYNQ UDP bridge and measure replies."""
import argparse
import socket
import struct
import time
from pathlib import Path


MAGIC = 0x444E4148
VERSION = 1
REQUEST = 1
REPLY = 2
REQUEST_FORMAT = "<IHHIIBBH27f5HH"
REPLY_FORMAT = "<IHHII3f9f5f5fHBB"


def rows(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        values = line.split()
        reset = int(values[0])
        timestamp = int(values[1])
        marker_valid = int(values[2])
        xyz = [float(value) for value in values[3:30]]
        flex = [int(value) for value in values[30:35]]
        yield reset, timestamp, marker_valid, xyz, flex


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.2.99")
    parser.add_argument("--port", type=int, default=47000)
    parser.add_argument("--rate", type=float, default=100.0)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument(
        "--input",
        type=Path,
        default=(
            Path(__file__).resolve().parents[2]
            / "modules/fusion/tests/data/packets.txt"
        ),
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.02)
    period = 1.0 / args.rate
    received = 0
    lost = 0
    latency_ms = []

    for sequence, packet in enumerate(rows(args.input)):
        if sequence >= args.count:
            break
        reset, timestamp, marker_valid, xyz, flex = packet
        request = struct.pack(
            REQUEST_FORMAT,
            MAGIC,
            VERSION,
            REQUEST,
            sequence,
            timestamp,
            reset,
            0,
            marker_valid,
            *xyz,
            *flex,
            0,
        )
        start = time.perf_counter()
        sock.sendto(request, (args.host, args.port))
        try:
            reply = sock.recv(108)
            fields = struct.unpack(REPLY_FORMAT, reply)
            if fields[:4] != (MAGIC, VERSION, REPLY, sequence):
                raise RuntimeError("unexpected reply header")
            latency_ms.append((time.perf_counter() - start) * 1000.0)
            received += 1
        except socket.timeout:
            lost += 1
        elapsed = time.perf_counter() - start
        if elapsed < period:
            time.sleep(period - elapsed)

    if latency_ms:
        print(
            f"received={received} lost={lost} "
            f"latency_ms avg={sum(latency_ms) / len(latency_ms):.3f} "
            f"max={max(latency_ms):.3f}"
        )
    else:
        print(f"received=0 lost={lost}")


if __name__ == "__main__":
    main()
