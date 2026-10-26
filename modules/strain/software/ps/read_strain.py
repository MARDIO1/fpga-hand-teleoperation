"""Read a short STRN stream and report rate, sequence and latest raw values."""

import argparse
import time

from strain_uart import StrainSerial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="/dev/ttyUSB0")
    parser.add_argument("--seconds", type=float, default=2.0)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("seconds must be positive")

    frames = []
    deadline = time.monotonic() + args.seconds
    with StrainSerial(args.device) as reader:
        while time.monotonic() < deadline:
            frames.append(reader.read_frame(1.0))
        rejected = reader.decoder.rejected
    if len(frames) < 2:
        raise SystemExit("not enough valid frames")
    elapsed = (frames[-1].timestamp_us - frames[0].timestamp_us) & 0xffffffff
    rate = (len(frames) - 1) * 1000000.0 / elapsed
    print("frames={} rate_hz={:.2f} first_seq={} last_seq={} rejected={} raw={}".format(
        len(frames), rate, frames[0].sequence, frames[-1].sequence,
        rejected, frames[-1].raw))


if __name__ == "__main__":
    main()
