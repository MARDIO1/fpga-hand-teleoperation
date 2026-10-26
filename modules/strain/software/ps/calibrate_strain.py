"""Interactively record open, half-bent and fist strain calibration poses."""

import argparse
import json
from pathlib import Path
import statistics
import sys

from strain_uart import StrainSerial


DEFAULT_OUTPUT = Path(__file__).resolve().parents[2] / "data" / "strain_calibration.json"


def capture(reader, count):
    values = [[] for _ in range(5)]
    for _ in range(count):
        frame = reader.read_frame(2.0)
        for channel, value in enumerate(frame.raw):
            values[channel].append(value)
    return [int(statistics.median(channel)) for channel in values]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="/dev/ttyUSB0")
    parser.add_argument("--channels", type=int, nargs="+", default=[2])
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.samples < 10 or not args.channels or any(channel not in range(5) for channel in args.channels):
        parser.error("use at least 10 samples and channel indices 0..4")

    poses = {}
    with StrainSerial(args.device) as reader:
        reader.read_frame(2.0)
        for name, prompt in (("open", "Fully open and relax the hand"),
                             ("half", "Bend to a comfortable half pose"),
                             ("fist", "Close the hand into a fist")):
            input(prompt + ", then press Enter: ")
            poses[name] = capture(reader, args.samples)
            print("{}: {}".format(name, poses[name]))

    for channel in args.channels:
        values = [poses[name][channel] for name in ("open", "half", "fist")]
        if not (values[0] < values[1] < values[2] or values[0] > values[1] > values[2]):
            raise SystemExit("channel {} is not monotonic: {}".format(channel, values))

    document = {"schema": "strain.calibration.v1", "channels": args.channels,
                "samples_per_pose": args.samples, "poses": poses}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print("saved {}".format(args.output))


if __name__ == "__main__":
    main()
