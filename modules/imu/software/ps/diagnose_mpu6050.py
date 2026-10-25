"""Read actual MPU6050 registers through the PL diagnostic command port."""
import argparse
import json
from pathlib import Path
import time

from pynq import MMIO, Overlay


def transaction(mmio, address, value=None):
    deadline = time.perf_counter()+3
    while mmio.read(0x90) & 1:
        if time.perf_counter() > deadline:
            raise RuntimeError("Diagnostic bus busy")
        time.sleep(0.001)
    count, errors = mmio.read(0x98), mmio.read(0x30)
    command = (address << 8) | 1
    if value is not None:
        command |= (value << 16) | 2
    mmio.write(0x90, command)
    while mmio.read(0x98) == count:
        if time.perf_counter() > deadline:
            raise RuntimeError("Diagnostic transaction timeout")
        time.sleep(0.001)
    if mmio.read(0x30) != errors:
        raise RuntimeError("I2C NACK/timeout during diagnostic transfer")
    return mmio.read(0x94) & 255


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", action="store_true")
    parser.add_argument("--bitstream", type=Path, default=Path(__file__).resolve().parents[2]/"export/bitstream/acz7015/v0.1.0/mpu6050.bit")
    parser.add_argument("--write", nargs=2, type=lambda s: int(s, 0))
    args = parser.parse_args()
    if args.load:
        overlay = Overlay(str(args.bitstream.resolve()))
        time.sleep(1)
    mmio = MMIO(0x43c10000, 0x1000)
    if args.write:
        transaction(mmio, *args.write)
    registers = [0x75, 0x6b, 0x6c, 0x19, 0x1a, 0x1b, 0x1c, 0x37, 0x38, 0x3a]
    print(json.dumps({hex(a): hex(transaction(mmio, a)) for a in registers}, indent=2), flush=True)
    print("raw_registers", [transaction(mmio, a) for a in range(0x3b, 0x49)], flush=True)
    print("status", mmio.read(4), "sequence", mmio.read(8), "errors", mmio.read(0x30), flush=True)


if __name__ == "__main__":
    main()
