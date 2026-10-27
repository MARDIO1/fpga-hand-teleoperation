"""Load capture-only compact overlay; no HDMI, buttons or full-frame rendering."""
import argparse,time
from pathlib import Path
from pynq import Bitstream,MMIO
from pynq.ps import Clocks
p=argparse.ArgumentParser();p.add_argument('--bitstream',default=str(Path(__file__).with_name('pl_stereo_compact_xyz.bit')));a=p.parse_args()
Clocks.fclk0_mhz=100
Bitstream(a.bitstream).download()
v=MMIO(0x43000000,4096);v.write(0x30,4)
deadline=time.monotonic()+2
while v.read(0x30)&4:
 if time.monotonic()>deadline:raise RuntimeError('capture reset timeout')
v.write(0x34,0x7770);v.write(0xac,0x1e000000);v.write(0xa4,2560);v.write(0xa8,2560);v.write(0x30,0x1003);v.write(0xa0,720)
deadline=time.monotonic()+25
while not v.read(0x34)&0x1000:
 if time.monotonic()>deadline:raise RuntimeError('no stereo capture frame')
 time.sleep(.01)
print('COMPACT CAPTURE PASS',hex(v.read(0x34)),flush=True)
