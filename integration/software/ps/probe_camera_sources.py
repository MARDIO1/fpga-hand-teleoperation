"""Read raw and paired camera frame counters from the diagnostic full image."""

import time

from pynq import Clocks, MMIO


def main():
    paired = MMIO(0x41200000, 0x1000)
    raw = MMIO(0x41210000, 0x1000)
    ingress = MMIO(0x43C60000, 0x1000)
    for second in range(6):
        print(
            "t={} fclk0={:.3f} camera1={} camera2={} paired={} overflow={} "
            "ingress=0x{:08x} detail=0x{:08x}".format(
                second,
                Clocks.fclk0_mhz,
                raw.read(0),
                raw.read(8),
                paired.read(8),
                paired.read(0),
                ingress.read(12),
                ingress.read(0x2C),
            ),
            flush=True,
        )
        time.sleep(1)


if __name__ == "__main__":
    main()
