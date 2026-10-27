#!/usr/bin/env python3
"""Dual OV5640 -> PL video stream -> DDR frame buffer -> HDMI_1.

PROC is counted from completed VDMA S2MM frame writes on this Zynq board.
HDMI is the configured 720p60 output timing, not the acquisition rate.
"""

import importlib.machinery
import mmap
import os
from pathlib import Path
import subprocess
import time
import zlib

from pynq import Bitstream, MMIO


HERE = Path(__file__).resolve().parent
BITSTREAM = HERE / "pl_stereo_hdmi.bit"
HDMI_HELPER = HERE / "hdmi_helper.py"
VDMA_BASE = 0x43000000
OSD_BASE = 0x41210000
CAMERA_BASE = 0x41200000
PROBE_BASE = 0x41220000
IOC_IRQ = 0x1000
VDMA_FATAL_ERRORS = 0x00000060


def bcd(value, digits=3):
    result = 0
    for offset in range(digits):
        result |= (value % 10) << (4 * offset)
        value //= 10
    return result


def load_helper():
    loader = importlib.machinery.SourceFileLoader("acz7015_hdmi_stereo",
                                                  str(HDMI_HELPER))
    return loader.load_module()


def wait_reset(vdma, control_offset):
    vdma.write(control_offset, 4)
    deadline = time.monotonic() + 1.0
    while vdma.read(control_offset) & 4:
        if time.monotonic() > deadline:
            raise RuntimeError("VDMA reset timed out at 0x%x" % control_offset)


def check_status(vdma, status_offset, name):
    status = vdma.read(status_offset)
    # Frame/line timing flags are sticky and do not halt the VDMA. They can
    # arise from a partial frame while the camera and capture engine start.
    if status & VDMA_FATAL_ERRORS or status & 1:
        raise RuntimeError("%s VDMA status error 0x%08x" % (name, status))
    return status


def start_capture(vdma, hdmi):
    wait_reset(vdma, 0x30)
    vdma.write(0x34, 0x00007770)
    vdma.write(0xAC, hdmi.FRAMEBUFFER_PHYS)
    vdma.write(0xA4, hdmi.FRAME_WIDTH * 2)
    vdma.write(0xA8, hdmi.FRAME_WIDTH * 2)
    vdma.write(0x30, 0x00001003)  # run, circular, frame-done IRQ status
    vdma.write(0xA0, hdmi.FRAME_HEIGHT)
    return check_status(vdma, 0x34, "S2MM")


def start_display(hdmi, display):
    """Follow ch19: start the VTC only after MM2S has been armed."""
    display.mode(hdmi.DISPLAY_MODE_INDEX)
    display.start()
    vtc = MMIO(hdmi.VTC_BASE, 0x1000)
    vtc.write(0x00, vtc.read(0x00) | 0x06)


def initialize_hdmi(hdmi, bitstream=BITSTREAM, defer_display=False):
    hdmi.set_fclk0_100mhz()
    Bitstream(str(bitstream)).download()
    # The board's USB and SIL9022 reset path is shared. The known-good HDMI
    # sequence restores that reset after reprogramming the PL.
    subprocess.run(["systemctl", "restart", "acz7015-usb-host.service"],
                   check=True, timeout=30)
    hdmi.rebind_i2c1()
    i2c_device, i2c_name = hdmi.find_hdmi_i2c_device()
    transmitter = hdmi.Sii9022(i2c_device)
    try:
        chip_id = transmitter.read(0x1B)
        transmitter.configure_720p60()
    finally:
        transmitter.close()
    display = hdmi.pynq.lib._video._display(
        hdmi.VTC_BASE, hdmi.DYNCLK_BASE, 1)
    if not defer_display:
        start_display(hdmi, display)
    print("HDMI_1 %s (%s) SIL9022 id=0x%02x configured 1280x720@60" %
          (i2c_device, i2c_name, chip_id), flush=True)
    return display


def run():
    if os.geteuid() != 0:
        raise SystemExit("run as root")
    if not BITSTREAM.is_file():
        raise SystemExit("missing bitstream: %s" % BITSTREAM)
    hdmi = load_helper()
    display = initialize_hdmi(hdmi)

    vdma = MMIO(VDMA_BASE, 0x1000)
    osd = MMIO(OSD_BASE, 0x1000)
    camera = MMIO(CAMERA_BASE, 0x1000)
    probe = MMIO(PROBE_BASE, 0x1000)
    osd.write(0x04, 0)
    osd.write(0x0C, 0)
    osd.write(0x00, bcd(60))  # HDMI label uses configured output timing
    osd.write(0x08, 0x80000000 | bcd(0))

    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    framebuffer = None
    try:
        framebuffer = mmap.mmap(fd, hdmi.FRAMEBUFFER_SIZE,
                                flags=mmap.MAP_SHARED,
                                prot=mmap.PROT_READ | mmap.PROT_WRITE,
                                offset=hdmi.FRAMEBUFFER_PHYS)
        hdmi.fill_color_bars(framebuffer)
        print("S2MM start status=0x%08x" % start_capture(vdma, hdmi),
              flush=True)

        first_deadline = time.monotonic() + 25.0
        while True:
            status = check_status(vdma, 0x34, "S2MM")
            if status & IOC_IRQ:
                vdma.write(0x34, IOC_IRQ)
                break
            if time.monotonic() > first_deadline:
                raise RuntimeError("no complete stereo frame reached DDR; "
                                   "source=%d overflow=%d status=0x%08x" %
                                   (camera.read(0x08), camera.read(0x00), status))
            time.sleep(0.005)

        first_status = vdma.read(0x34)
        vdma.write(0x34, 0x00008990)
        mm2s, _, _ = hdmi.start_vdma()
        print("first stereo frame in DDR; S2MM=0x%08x HDMI MM2S=0x%08x" %
              (first_status, mm2s.read(0x04)), flush=True)

        frame_count = 0
        epoch = time.monotonic()
        last_crc = None
        while True:
            status = check_status(vdma, 0x34, "S2MM")
            if status & IOC_IRQ:
                vdma.write(0x34, IOC_IRQ)
                frame_count += 1
            elapsed = time.monotonic() - epoch
            if elapsed >= 1.0:
                fps = int(round(frame_count / elapsed))
                osd.write(0x08, 0x80000000 | bcd(min(fps, 999)))
                # Sparse CRC confirms the RAM content is changing without
                # copying a full 1.8 MB frame through the CPU each second.
                sample = (framebuffer[0x20000:0x22000] +
                          framebuffer[0x90000:0x92000])
                crc = zlib.crc32(sample)
                print("proc_fps=%d hdmi_configured_hz=60 "
                      "source_frames=%d overflow=%d "
                      "ddr_sample_crc=%08x changed=%d "
                      "output_line_pixels=%d output_current_line=%d "
                      "s2mm=0x%08x mm2s=0x%08x" %
                      (fps, camera.read(0x08), camera.read(0x00), crc,
                       int(last_crc is not None and crc != last_crc),
                       probe.read(0x00), probe.read(0x08), status,
                       mm2s.read(0x04)), flush=True)
                last_crc = crc
                frame_count = 0
                epoch = time.monotonic()
            time.sleep(0.005)
    finally:
        if framebuffer is not None:
            framebuffer.close()
        os.close(fd)


if __name__ == "__main__":
    run()
