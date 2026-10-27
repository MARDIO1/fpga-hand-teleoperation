#!/usr/bin/env python3
"""Test raw stereo through the direct ch19 DDR-to-HDMI display path."""

import argparse
import mmap
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET

from pynq import MMIO
from run_stereo_hdmi import (initialize_hdmi, load_helper, start_display,
                             start_capture, check_status)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--bitstream", type=Path, required=True)
    args = parser.parse_args()
    bitstream = args.bitstream.resolve()
    root = ET.parse(bitstream.with_suffix(".hwh")).getroot()
    vdma_ip = next(m for m in root.findall(".//MODULE")
                   if m.get("INSTANCE") == "display_vdma")
    params = {p.get("NAME"): p.get("VALUE") for p in
              vdma_ip.findall("./PARAMETERS/PARAMETER")}
    for name, expected in (("C_MM2S_GENLOCK_MODE", "3"),
                           ("C_MM2S_LINEBUFFER_DEPTH", "1024"),
                           ("C_NUM_FSTORES", "1")):
        if params.get(name) != expected:
            raise RuntimeError("wrong ch19 test hardware: %s=%s" %
                               (name, params.get(name)))
    hdmi = load_helper()
    display = initialize_hdmi(hdmi, bitstream=bitstream, defer_display=True)
    osd = MMIO(0x41210000, 0x1000)
    osd.write(8, 0)
    vdma = MMIO(hdmi.VDMA_BASE, 0x1000)
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    memory = mmap.mmap(fd, hdmi.FRAMEBUFFER_SIZE, flags=mmap.MAP_SHARED,
                       prot=mmap.PROT_READ | mmap.PROT_WRITE,
                       offset=hdmi.FRAMEBUFFER_PHYS)
    try:
        frame = hdmi.frame_view(memory)
        frame[:, :640] = 0x07E0
        frame[:, 640:] = 0x001F
        frame[::80, :] = 0xFFFF
        frame[:, ::80] = 0xFFFF
        frame[:16, :] = 0xFFFF
        frame[-16:, :] = 0x07FF
        frame[:, :16] = 0xF800
        frame[:, -16:] = 0xFFE0
        frame[:, 638:642] = 0xFFFF
        hdmi.flush_framebuffer(memory)
        if args.live:
            start_capture(vdma, hdmi)
            deadline = time.monotonic() + 25
            while not vdma.read(0x34) & 0x1000:
                check_status(vdma, 0x34, "S2MM")
                if time.monotonic() > deadline:
                    raise RuntimeError("no complete stereo capture frame")
                time.sleep(0.01)
        hdmi.start_vdma(control=0x0B)
        start_display(hdmi, display)
        print("CH19_DIRECT mode=%s; left red, right yellow, top white, bottom cyan" %
              ("LIVE" if args.live else "STATIC"), flush=True)
        camera = MMIO(0x41200000, 0x1000)
        while True:
            print("mm2s=0x%08x s2mm=0x%08x source=%d overflow=%d" %
                  (vdma.read(4), vdma.read(0x34), camera.read(8), camera.read(0)),
                  flush=True)
            time.sleep(1)
    finally:
        del frame
        memory.close()
        os.close(fd)
        # Keep the display object alive for the entire scanout.
        del display


if __name__ == "__main__":
    main()
