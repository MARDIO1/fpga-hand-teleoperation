# ACZ7015 standalone display test runners

These scripts belong to the vision module's standalone tests, not the combined
integration design. Run only on the matching ACZ7015/PYNQ Linux installation as
root. They load PL, configure clocks/I2C/SiI9022 and use physical video memory.

## Exported static baseline

Copy the entire `modules/vision` directory to the board, or preserve equivalent
relative paths for scripts and exported files. Stop any existing camera/display
program before loading another overlay; the runner does not kill other processes.
From the repository root on the board:

```sh
sudo python3 modules/vision/software/ps/run_hdmi_baseline.py --bitstream modules/vision/export/bitstream/acz7015/hdmi-baseline-v0.1.0/pl_hdmi_official_baseline.bit
```

The grid uses left red/right yellow/top white/bottom cyan borders, a white center
at x=640, and 80-pixel grid spacing. Its left half is green, right half blue.
The script retains the PYNQ display object while scanout runs. A valid DMA status
or locked bridge alone is not proof of a visible or correctly aligned screen.

Required board environment:

- Compatible PYNQ providing the legacy `pynq.lib._video._display` interface and
  mode index 2 = 1280 x 720, plus NumPy.
- Device-tree reserved/no-map RAM at `0x1E000000..0x1EFFFFFF`. Do not use that memory
  unless it is actually reserved by the running system. This migration does not
  supply or modify a boot image/device tree.
- Existing `acz7015-usb-host.service`, whose reset recovery is shared with SiI9022;
  its source support files are retained in `board_support/` for reproducibility.
  It is a board-specific prerequisite, not installed automatically. See that
  directory's README before deploying to another image.
- HDMI_1/J6, PS I2C1 exposed through EMIO, transmitter address 0x39; mode and
  register addresses must match the provided HWH.

## Experimental capture comparison

After separately rebuilding the matching `ch19_display` design:

```sh
sudo python3 modules/vision/software/ps/run_ch19_display.py --bitstream modules/vision/vivado/output/ch19_display/pl_stereo_hdmi_ch19.bit
sudo python3 modules/vision/software/ps/run_ch19_display.py --bitstream modules/vision/vivado/output/ch19_display/pl_stereo_hdmi_ch19.bit --live
```

The first command is static, the second enables capture. This is a single-buffer
comparison; live tearing is not solved. No depth-mode runtime or calibration is
released. Shared helpers still expose historical diagnostic methods; their
permissive frame-error handling is not an acceptance criterion for stereo input.
The HDMI-only baseline has no capture framebuffer for the PC live marker reader.
