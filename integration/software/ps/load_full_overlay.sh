#!/bin/sh
# Load the combined image into volatile PL configuration for a board smoke test.
set -eu

overlay=/home/xilinx/overlays/full_hand_20261028/full_board.bit
sha256sum "$overlay"
python3 - <<'PY'
from pynq import Clocks, Overlay

overlay = Overlay('/home/xilinx/overlays/full_hand_20261028/full_board.bit')
Clocks.set_pl_clk(0, div0=5, div1=2)
print('ips=' + ','.join(sorted(overlay.ip_dict)))
print('fclk0_mhz={:.3f}'.format(Clocks.fclk0_mhz))
PY
