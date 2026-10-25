#!/usr/bin/env python3
"""Bring up the ACZ7015 HDMI_1 (SIL9022A) output under Linux."""

import errno
import fcntl
import os
from pathlib import Path
import time

import numpy as np
from pynq import MMIO
from pynq.ps import Clocks
import pynq.lib._video


FRAMEBUFFER_PHYS = 0x1E000000
FRAMEBUFFER_SIZE = 0x01000000
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
DISPLAY_MODE_INDEX = 2
VDMA_BASE = 0x43000000
DYNCLK_BASE = 0x43C00000
VTC_BASE = 0x43C10000
I2C_SLAVE = 0x0703
SII9022_ADDR = 0x39
I2C1_APER_CLOCK = 1 << 19


def set_fclk0_100mhz():
    unlock = MMIO(0xF8000008, 4)
    lock = MMIO(0xF8000004, 4)
    unlock.write(0, 0x0000DF0D)
    aper_clock = MMIO(0xF800012C, 4)
    aper_clock.write(0, aper_clock.read(0) | I2C1_APER_CLOCK)
    # The running board uses a 1 GHz IOPLL. 5 x 2 gives the 100 MHz clock
    # expected by this FPGA design.
    Clocks.set_pl_clk(0, div0=5, div1=2)
    lock.write(0, 0x0000767B)


def rebind_i2c1():
    driver = Path("/sys/bus/platform/drivers/cdns-i2c")
    device = "e0005000.i2c"
    binding = driver / device
    if binding.exists():
        (driver / "unbind").write_text(device)
    time.sleep(0.1)
    (driver / "bind").write_text(device)
    deadline = time.monotonic() + 2.0
    while not Path("/dev/i2c-0").exists():
        if time.monotonic() > deadline:
            raise RuntimeError("PS I2C1 did not reappear after rebind")
        time.sleep(0.05)


def find_hdmi_i2c_device():
    for adapter in sorted(Path("/sys/class/i2c-adapter").glob("i2c-*")):
        name = (adapter / "name").read_text().strip()
        resolved = str(adapter.resolve())
        if "e0005000" in name.lower() or "e0005000" in resolved.lower():
            return "/dev/" + adapter.name, name
    raise RuntimeError("PS I2C1 (e0005000) adapter was not found")


class Sii9022:
    def __init__(self, device):
        self.fd = os.open(device, os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, SII9022_ADDR)

    def close(self):
        os.close(self.fd)

    def write(self, register, value):
        written = os.write(self.fd, bytes((register, value)))
        if written != 2:
            raise OSError("short SIL9022 I2C write")

    def read(self, register):
        os.write(self.fd, bytes((register,)))
        value = os.read(self.fd, 1)
        if len(value) != 1:
            raise OSError("short SIL9022 I2C read")
        return value[0]

    def configure_720p60(self):
        # Follow the upstream Linux sii902x DRM driver's TPI video-data
        # layout: pixel clock in 10 kHz, refresh in Hz, then active size.
        registers = (
            (0xC7, 0x00),
            # Internal page 1, register 0x82: enable TMDS source termination.
            (0xBC, 0x01), (0xBD, 0x82), (0xBE, 0x01),
            (0x00, 0x01), (0x01, 0x1D),
            (0x02, 0x3C), (0x03, 0x00),
            (0x04, 0x00), (0x05, 0x05),
            (0x06, 0xD0), (0x07, 0x02),
            # 24-bit full-pixel RGB and 1x bus clock. The official bridge
            # timing samples pixel/sync data on the negative edge.
            (0x08, 0x60), (0x09, 0x00), (0x0A, 0x00),
            (0x0B, 0x00), (0x0C, 0x00), (0x0D, 0x00),
            (0x0E, 0x00), (0x0F, 0x00), (0x10, 0x00),
            (0x11, 0x00), (0x12, 0x00), (0x13, 0x00),
            (0x14, 0x00), (0x15, 0x00), (0x16, 0x00),
            (0x17, 0x00), (0x18, 0x00), (0x19, 0x00),
            (0x1E, 0x00),
            (0x60, 0x04), (0x62, 0x00), (0x63, 0x00),
            (0x64, 0x00), (0x65, 0x00), (0x66, 0x00),
            (0x67, 0x00), (0x68, 0x00), (0x69, 0x00),
            (0x1A, 0x00),
        )
        for register, value in registers:
            self.write(register, value)


def fill_color_bars(framebuffer):
    colors = (0xF800, 0x07E0, 0x001F, 0xFFFF,
              0xFFE0, 0xF81F, 0x07FF, 0x0000)
    frame = frame_view(framebuffer)
    width = frame.shape[1] // len(colors)
    for index, color in enumerate(colors):
        begin = index * width
        end = frame.shape[1] if index == len(colors) - 1 else (index + 1) * width
        frame[:, begin:end] = color
    flush_framebuffer(framebuffer)


def frame_view(framebuffer):
    return np.ndarray(
        (FRAME_HEIGHT, FRAME_WIDTH), dtype="<u2", buffer=framebuffer)


def flush_framebuffer(framebuffer):
    try:
        framebuffer.flush()
    except OSError as error:
        # /dev/mem mappings on this 4.14 ARM kernel are uncached and reject
        # msync(2) with EINVAL; stores are already visible to AXI VDMA.
        if error.errno != errno.EINVAL:
            raise


def start_vdma(control=0x00000003):
    vdma = MMIO(VDMA_BASE, 0x1000)
    vdma.write(0x00, 0x00000004)
    deadline = time.monotonic() + 1.0
    while vdma.read(0x00) & 0x4:
        if time.monotonic() > deadline:
            raise RuntimeError("VDMA reset timed out")
    vdma.write(0x04, 0x00007770)
    vdma.write(0x5C, FRAMEBUFFER_PHYS)
    vdma.write(0x54, FRAME_WIDTH * 2)
    vdma.write(0x58, FRAME_WIDTH * 2)
    vdma.write(0x00, control)
    vdma.write(0x50, FRAME_HEIGHT)
    time.sleep(0.2)
    status = vdma.read(0x04)
    if status & 0x71:
        raise RuntimeError("VDMA did not start cleanly (status=0x%08x)" % status)
    return vdma, vdma.read(0x00), status

