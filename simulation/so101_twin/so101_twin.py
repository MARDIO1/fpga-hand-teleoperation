"""Run the independent SO-101 digital-twin demonstration."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import mujoco

from controller import So101Twin
from protocol import DEFAULT_PORT, UdpReceiver, demo_sequence, load_sequence


def run_sequence(args: argparse.Namespace) -> int:
    frames = load_sequence(args.sequence) if args.sequence else demo_sequence(args.frames)
    twin = So101Twin(args.position_scale, args.calibration)
    try:
        if args.headless:
            for frame in frames:
                twin.step(frame)
        else:
            from mujoco import viewer
            with viewer.launch_passive(twin.model, twin.data) as window:
                index = 0
                while window.is_running():
                    twin.step(frames[index])
                    window.sync()
                    index = (index + 1) % len(frames)
                    time.sleep(1.0 / 60.0)
    finally:
        print(f"position_error_mm={twin.position_error * 1000.0:.2f}")
        print(f"axis_error_deg={twin.axis_error * 180.0 / 3.141592653589793:.2f}")
        print(f"reach_limited={twin.reach_limited}")
    return 0


def run_udp(args: argparse.Namespace) -> int:
    receiver = UdpReceiver(args.bind, args.port)
    twin = So101Twin(args.position_scale, args.calibration)
    latest = None
    next_telemetry = time.monotonic()
    print(f"listening udp://{args.bind}:{args.port}")
    try:
        if args.headless:
            started = time.monotonic()
            while time.monotonic() - started < args.seconds:
                packet = receiver.poll()
                if packet is not None:
                    latest = packet
                if latest is not None:
                    twin.step(latest)
                    if args.telemetry and time.monotonic() >= next_telemetry:
                        print(twin.telemetry(), flush=True)
                        next_telemetry = time.monotonic() + 0.2
                time.sleep(1.0 / 60.0)
        else:
            from mujoco import viewer
            with viewer.launch_passive(twin.model, twin.data) as window:
                while window.is_running():
                    packet = receiver.poll()
                    if packet is not None:
                        latest = packet
                    if latest is not None:
                        twin.step(latest)
                        if args.telemetry and time.monotonic() >= next_telemetry:
                            print(twin.telemetry(), flush=True)
                            next_telemetry = time.monotonic() + 0.2
                    window.sync()
                    time.sleep(1.0 / 60.0)
    finally:
        receiver.close()
    print(f"received={receiver.received} rejected={receiver.rejected}")
    if latest is not None:
        print(f"position_error_mm={twin.position_error * 1000.0:.2f}")
        print(f"axis_error_deg={twin.axis_error * 180.0 / 3.141592653589793:.2f}")
        print(f"reach_limited={twin.reach_limited}")
    return 0 if receiver.received else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--udp", action="store_true")
    source.add_argument("--sequence", type=Path)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--position-scale", type=float, default=1.0)
    parser.add_argument("--calibration", type=Path,
                        default=Path(__file__).with_name("orientation_calibration.json"))
    parser.add_argument("--telemetry", action="store_true",
                        help="print IMU and target/actual end-effector data at 5 Hz")
    parser.add_argument("--frames", type=int, default=360)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--seconds", type=float, default=5.0,
                        help="finite duration for --udp --headless")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("seconds must be positive")
    return run_udp(args) if args.udp else run_sequence(args)


if __name__ == "__main__":
    raise SystemExit(main())

