#!/bin/sh
# Read-only source-frame probe; safe when no capture owner is running.
set -eu
python3 - <<'PY'
import time
from pynq import Clocks, MMIO

camera = MMIO(0x41200000, 0x1000)
ingress = MMIO(0x43c60000, 0x1000)
for second in range(6):
    print('t={} fclk0={:.3f} frames={} overflow={} ingress=0x{:08x} detail=0x{:08x}'
          .format(second, Clocks.fclk0_mhz, camera.read(8), camera.read(0),
                  ingress.read(12), ingress.read(0x2c)))
    time.sleep(1)
PY
