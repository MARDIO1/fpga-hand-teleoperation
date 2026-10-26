"""Solve the first-board IMU and strain inputs, then send HAND v2 at 100 Hz."""

import argparse
from pathlib import Path
import socket
import struct
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "modules" / "imu" / "software" / "ps"))
sys.path.insert(0, str(ROOT / "modules" / "strain" / "software" / "ps"))

from attitude import Attitude
from run_mpu6050 import read_sample
from strain_uart import Calibration, StrainSerial


HAND = struct.Struct("<IHHIIBBBB13f5HH")
MAGIC = 0x444e4148
DEFAULT_BITSTREAM = ROOT / "modules" / "imu" / "export" / "bitstream" / "acz7015" / "v0.1.0" / "mpu6050.bit"
DEFAULT_CALIBRATION = ROOT / "modules" / "strain" / "data" / "strain_calibration.json"


def packet(sequence, timestamp_us, quaternion, bend, position, reset=False):
    return HAND.pack(MAGIC, 2, 1, sequence, timestamp_us & 0xffffffff,
                     int(reset), 0, 1, 0,
                     position[0], position[1], position[2],
                     quaternion[0], quaternion[1], quaternion[2], quaternion[3],
                     0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
                     bend[0], bend[1], bend[2], bend[3], bend[4], 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bitstream", type=Path, default=DEFAULT_BITSTREAM)
    parser.add_argument("--base", type=lambda value: int(value, 0), default=0x43c10000)
    parser.add_argument("--device", default="/dev/ttyUSB0")
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--host", default="192.168.137.1")
    parser.add_argument("--port", type=int, default=47000)
    parser.add_argument("--rate", type=float, default=100.0)
    parser.add_argument("--position", type=float, nargs=3, default=(0.0, 0.0, 0.31))
    parser.add_argument("--calibration-samples", type=int, default=1000)
    args = parser.parse_args()
    if args.rate <= 0 or args.calibration_samples < 2:
        parser.error("rate must be positive and calibration needs at least two samples")

    from pynq import MMIO, Overlay

    Overlay(str(args.bitstream.resolve()))
    mmio = MMIO(args.base, 0x1000)
    calibration = Calibration.load(args.calibration)
    estimator = Attitude(args.calibration_samples)
    destination = (args.host, args.port)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    latest_strain = None
    last_imu = None
    last_errors = None
    sequence = 0
    sent = 0
    next_send = time.monotonic()
    last_report = next_send

    print("Keep the hand still for the two-second IMU calibration.", file=sys.stderr)
    try:
        with StrainSerial(args.device) as strain:
            while True:
                frames = strain.poll(0.0)
                if frames:
                    latest_strain = frames[-1]

                sample = read_sample(mmio)
                if sample is not None and sample.sequence != last_imu:
                    last_imu = sample.sequence
                    if last_errors is not None and sample.errors != last_errors:
                        estimator = Attitude(args.calibration_samples)
                        print("I2C recovery: restart stationary calibration", file=sys.stderr)
                    last_errors = sample.errors
                    try:
                        pose = estimator.update(sample)
                    except ValueError as error:
                        print(str(error), file=sys.stderr)
                        estimator = Attitude(args.calibration_samples)
                        pose = estimator.update(sample)
                else:
                    pose = None

                now = time.monotonic()
                if pose is not None and latest_strain is not None and now >= next_send:
                    bend = calibration.map(latest_strain.raw)
                    udp.sendto(packet(sequence, pose["timestamp_us"],
                                      pose["quaternion_wxyz"], bend,
                                      args.position, sequence == 0), destination)
                    sequence = (sequence + 1) & 0xffffffff
                    sent += 1
                    next_send += 1.0 / args.rate
                    if next_send < now - 1.0 / args.rate:
                        next_send = now

                if now - last_report >= 1.0:
                    print("sent={} imu_seq={} strain_seq={} uart_rejected={}".format(
                        sent, last_imu,
                        latest_strain.sequence if latest_strain else None,
                        strain.decoder.rejected), file=sys.stderr)
                    last_report = now
                time.sleep(0.0002)
    except KeyboardInterrupt:
        return 0
    finally:
        udp.close()


if __name__ == "__main__":
    main()
