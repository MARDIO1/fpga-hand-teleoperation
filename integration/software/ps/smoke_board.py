"""Smoke-test the combined hand_core, MPU6050 and strain UART interfaces."""

import argparse
import json
import math
from pathlib import Path
import struct
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "modules" / "imu" / "software" / "ps"))
sys.path.insert(0, str(ROOT / "modules" / "strain" / "software" / "ps"))

from run_mpu6050 import read_sample
from strain_uart import StrainSerial


DEFAULT_BITSTREAM = (ROOT / "integration" / "export" / "bitstream" / "acz7015" /
                     "v0.1.0" / "first_board.bit")
HAND_INPUT = struct.Struct("<IBBH3f4f3f3f5HH")
HAND_OUTPUT = struct.Struct("<3f9f5f5fHBx")


def run_hand_core(mmio, timeout=0.02):
    payload = HAND_INPUT.pack(0, 0, 1, 0, *(0.0,) * 3, 1.0, 0.0, 0.0, 0.0,
                              *(0.0,) * 6, *(0,) * 6)
    for index, word in enumerate(struct.unpack("<18I", payload)):
        mmio.write(0x80 + 4 * index, word)
    mmio.write(0x18, 1)
    mmio.write(0x00, 1)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if mmio.read(0x00) & 2:
            output = struct.pack("<23I", *(mmio.read(0x100 + 4 * i) for i in range(23)))
            values = HAND_OUTPUT.unpack(output)
            if not all(math.isfinite(value) for value in values[:22]):
                raise RuntimeError("hand_core returned a non-finite value")
            return {"valid": values[22], "state": values[23]}
    raise RuntimeError("hand_core did not finish")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bitstream", type=Path, default=DEFAULT_BITSTREAM)
    parser.add_argument("--reuse-overlay", action="store_true")
    parser.add_argument("--hand-base", type=lambda value: int(value, 0), default=0x43C00000)
    parser.add_argument("--imu-base", type=lambda value: int(value, 0), default=0x43C10000)
    parser.add_argument("--device", default="/dev/ttyUSB0")
    parser.add_argument("--seconds", type=float, default=3.0)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("seconds must be positive")

    from pynq import MMIO, Overlay

    if not args.reuse_overlay:
        Overlay(str(args.bitstream.resolve()))
    hand = run_hand_core(MMIO(args.hand_base, 0x1000))
    imu = MMIO(args.imu_base, 0x1000)
    started = time.monotonic()
    imu_first = imu_last = None
    imu_count = 0
    with StrainSerial(args.device) as strain:
        strain_first = strain.read_frame(2.0)
        strain_last = strain_first
        strain_count = 1
        while time.monotonic() - started < args.seconds:
            sample = read_sample(imu)
            if sample is not None and (imu_last is None or sample.sequence != imu_last.sequence):
                imu_first = sample if imu_first is None else imu_first
                imu_last = sample
                imu_count += 1
            frames = strain.poll(0.0)
            if frames:
                strain_last = frames[-1]
                strain_count += len(frames)
            time.sleep(0.0002)

        result = {
            "hand_core": hand,
            "imu": {"samples": imu_count,
                    "errors": None if imu_last is None else imu_last.errors,
                    "first_sequence": None if imu_first is None else imu_first.sequence,
                    "last_sequence": None if imu_last is None else imu_last.sequence},
            "uart": {"frames": strain_count, "rejected": strain.decoder.rejected,
                     "first_sequence": strain_first.sequence,
                     "last_sequence": strain_last.sequence},
        }
    print(json.dumps(result, indent=2))
    if imu_count < 2 or imu_last.errors or strain_count < 2 or strain.decoder.rejected:
        raise SystemExit("BOARD_SMOKE_FAIL")
    print("BOARD_SMOKE_PASS")


if __name__ == "__main__":
    main()
