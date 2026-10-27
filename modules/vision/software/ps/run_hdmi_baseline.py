#!/usr/bin/env python3
"""Hold a 720p RGB565 alignment chart on the vendor RAM -> HDMI chain."""

import argparse
import mmap
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

from pynq import Bitstream, MMIO

from run_stereo_hdmi import load_helper


HERE = Path(__file__).resolve().parent



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bitstream", type=Path, required=True)
    args = parser.parse_args()
    bitstream = args.bitstream.resolve()
    if os.geteuid() != 0:
        raise SystemExit("run as root")
    modules = {node.get("INSTANCE") for node in
               ET.parse(bitstream.with_suffix(".hwh")).findall(".//MODULE")}
    if "video_status" not in modules:
        raise SystemExit("deploy the matching baseline bitstream/HWH with video_status")
    hdmi = load_helper()
    hdmi.set_fclk0_100mhz()
    Bitstream(str(bitstream)).download()
    subprocess.run(["systemctl", "restart", "acz7015-usb-host.service"],
                   check=True, timeout=30)
    hdmi.rebind_i2c1()
    i2c_device, _ = hdmi.find_hdmi_i2c_device()
    transmitter = hdmi.Sii9022(i2c_device)
    try:
        transmitter.configure_720p60()
    finally:
        transmitter.close()
    assert (hdmi.FRAME_WIDTH, hdmi.FRAME_HEIGHT) == (1280, 720)

    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        framebuffer = mmap.mmap(fd, hdmi.FRAMEBUFFER_SIZE,
                                flags=mmap.MAP_SHARED,
                                prot=mmap.PROT_READ | mmap.PROT_WRITE,
                                offset=hdmi.FRAMEBUFFER_PHYS)
        try:
            frame = hdmi.frame_view(framebuffer)
            frame[:, :640] = 0x07E0
            frame[:, 640:] = 0x001F
            frame[::80, :] = 0xFFFF
            frame[:, ::80] = 0xFFFF
            frame[:16, :] = 0xFFFF
            frame[-16:, :] = 0x07FF
            frame[:, :16] = 0xF800
            frame[:, -16:] = 0xFFE0
            frame[:, 638:642] = 0xFFFF
            hdmi.flush_framebuffer(framebuffer)
            # The single MM2S channel in the vendor design uses its default
            # internal-genlock configuration (mode 3).
            vdma, control, status = hdmi.start_vdma(control=0x0000000B)
            display = hdmi.pynq.lib._video._display(
                hdmi.VTC_BASE, hdmi.DYNCLK_BASE, 1)
            display.mode(hdmi.DISPLAY_MODE_INDEX)
            display.start()
            vtc = MMIO(hdmi.VTC_BASE, 0x1000)
            vtc.write(0x00, vtc.read(0x00) | 0x06)
            print("official RAM->HDMI chart %dx%d MM2S control=0x%08x "
                  "status=0x%08x" % (hdmi.FRAME_WIDTH, hdmi.FRAME_HEIGHT,
                                      control, status), flush=True)
            print("borders: LEFT red, RIGHT yellow, TOP white, BOTTOM cyan; "
                  "center x=640 white; grid=80 pixels", flush=True)
            bridge = MMIO(0x41200000, 0x1000)
            geometry = MMIO(0x41210000, 0x1000) if "native_geometry" in modules else None
            alignment = MMIO(0x41220000, 0x1000) if "native_alignment" in modules else None
            while True:
                print("mm2s=0x%08x vtc=0x%08x bridge=0x%08x locked=%d" %
                      (vdma.read(4), vtc.read(0), bridge.read(0),
                       bridge.read(8) & 1), flush=True)
                if geometry is not None and alignment is not None:
                    line, frame = geometry.read(0), geometry.read(8)
                    borders, start = alignment.read(0), alignment.read(8)
                    print("NATIVE width=%d height=%d htotal=%d vtotal=%d "
                          "red_x=%d yellow_x=%d hs_to_de=%d vs_to_de=%d" %
                          (line & 0xffff, frame & 0xffff, line >> 16, frame >> 16,
                           borders & 0xffff, borders >> 16, start & 0xffff,
                           start >> 16), flush=True)
                time.sleep(1)
        finally:
            framebuffer.close()
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
