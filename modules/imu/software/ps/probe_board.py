"""Short hardware probe; load the test overlay and report raw sample health."""
import argparse
import json
from pathlib import Path
import time

from pynq import MMIO, Overlay
from run_mpu6050 import read_sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bitstream", type=Path, default=Path(__file__).resolve().parents[2]/"export/bitstream/acz7015/v0.1.0/mpu6050.bit")
    args = parser.parse_args()
    overlay = Overlay(str(args.bitstream.resolve()))
    mmio = MMIO(0x43c10000, 0x1000)
    print("ABI=0x%08x" % mmio.read(0), flush=True)
    start = time.perf_counter()
    first = last = None
    received = 0
    examples = []
    while time.perf_counter()-start < 6:
        sample = read_sample(mmio)
        if sample is not None and (last is None or sample.sequence != last.sequence):
            if first is None:
                first = sample
            last = sample
            received += 1
            if len(examples) < 5:
                examples.append(sample._asdict())
        time.sleep(0.0001)
    result = {"status": mmio.read(4), "errors": mmio.read(0x30),
              "sequence": mmio.read(8), "received": received, "examples": examples}
    if first and last and last.timestamp_us > first.timestamp_us:
        result["hardware_sample_hz"] = (last.sequence-first.sequence)*1e6/(last.timestamp_us-first.timestamp_us)
    print(json.dumps(result, indent=2), flush=True)
    if not received or result["status"] != 3 or result["errors"]:
        raise SystemExit("MPU6050 hardware probe failed; inspect wiring/address/pull-ups")


if __name__ == "__main__":
    main()
