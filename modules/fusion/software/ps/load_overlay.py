"""Load the hand_core bitstream on the existing PYNQ 2.4 system."""
import argparse
from pathlib import Path

from pynq import Overlay


DEFAULT_BITSTREAM = (
    Path(__file__).resolve().parents[2]
    / "export/bitstream/acz7015/v0.1.0/hand_core.bit"
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bitstream", nargs="?", type=Path, default=DEFAULT_BITSTREAM)
    args = parser.parse_args()
    Overlay(str(args.bitstream.resolve()), download=True)
    print("hand_core overlay loaded")


if __name__ == "__main__":
    main()
