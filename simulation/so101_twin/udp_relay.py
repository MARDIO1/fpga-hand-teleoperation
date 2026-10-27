"""Mirror one board UDP stream to multiple local visualization ports."""

from __future__ import annotations

import argparse
import socket


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=47000)
    parser.add_argument("--targets", type=int, nargs="+", default=(47001, 47002))
    args = parser.parse_args()

    incoming = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    outgoing = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    incoming.bind((args.bind, args.port))
    print(f"relay udp://{args.bind}:{args.port} -> {args.targets}", flush=True)
    while True:
        payload, _ = incoming.recvfrom(2048)
        for port in args.targets:
            outgoing.sendto(payload, ("127.0.0.1", port))


if __name__ == "__main__":
    main()
