"""Send a programmed HAND v2 sequence to the live MANO viewer."""

import argparse
import socket
import time

import numpy as np

from hand_sequence import WristTracker, demo_sequence
from live_hand_udp import MAGIC, SENSOR, SENSOR_PACKET, VERSION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=47000)
    parser.add_argument("--rate", type=float, default=60.0)
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()
    if args.rate <= 0 or args.seconds <= 0:
        parser.error("rate and seconds must be positive")

    count = round(args.rate * args.seconds)
    frames = demo_sequence(count, args.rate)
    tracker = WristTracker()
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    deadline = time.perf_counter()
    try:
        for sequence, sensor in enumerate(frames):
            hand = tracker.update(sensor)
            bend = np.rint(np.clip(hand.bend, 0.0, 1.0) * 4095.0).astype(np.uint16)
            payload = SENSOR_PACKET.pack(
                MAGIC, VERSION, SENSOR, sequence, sensor.timestamp_us,
                sequence == 0, sensor.camera_valid, 1, 0,
                *hand.wrist_xyz, *hand.wrist_quaternion_wxyz,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                *bend, 0,
            )
            udp.sendto(payload, (args.host, args.port))
            deadline += 1.0 / args.rate
            time.sleep(max(0.0, deadline - time.perf_counter()))
    finally:
        udp.close()
    print("sent={} rate_hz={:.1f}".format(count, args.rate))


if __name__ == "__main__":
    main()
