# HDMI static baseline v0.1.0

Standalone **display-only** test image for ACZ7015 / `xc7z015clg485-2`, generated
with Vivado 2025.2. Derived from the board's ch19 display topology and configured
by Linux software for 1280 x 720 at nominal 60 Hz. This is not the original
800 x 480 bare-metal example, a stereo/depth release or the final integration image.

Topology: PS DDR -> VDMA MM2S -> RGB565 conversion -> AXI video output/VTC ->
RGB565 board bridge -> SiI9022A. Includes read-only bridge status GPIO; excludes
the subsequently added native timing monitor and all camera/depth logic.

## Files and use

Keep `.bit` and same-stem `.hwh` together. Verify them using `build_info.json`.
Run `software/ps/run_hdmi_baseline.py --bitstream <this-directory>/pl_hdmi_official_baseline.bit`
as root on the prepared board; full prerequisites and repository-root command
are in [the runner README](../../../../software/ps/README.md).

The expected image has red/yellow left/right borders, white/cyan top/bottom
borders, a white center at x=640, green left half, blue right half and 80-pixel grid.
No framebuffer rotation or porch compensation is used.

## Validation boundary

On 2026-10-25 the user observed this static grid without misalignment following
restoration from the original-example black-screen experiment. The host also
read a running DMA and locked output bridge. Earlier starts showed wraparound;
repeated startup and sustained live-video reliability are not established.
This package is an observed static reference, not a completed HDMI repair claim.

## Rebuild and provenance

`vivado/create_hdmi_baseline.tcl` creates the pre-monitor design from the selected
sources. New builds go to ignored `vivado/output/hdmi_baseline/`; review their
HWH parameters and on-board behavior before replacing a release.

These binaries are imported unchanged from the saved confirmed reference, not
regenerated during migration. Exact historical synthesis inputs were not fully
archived with the original binary; `build_info.json` records both imported-file
checksums and the selected current rebuild source snapshot. A bit-identical rebuild
is not claimed. No `.xsa` is included because a matching confirmed snapshot was
not available; a newer monitor-build XSA must not be substituted.

The address map is private to this module test. Its dynamic-clock address overlaps
the fusion standalone overlay and must not be used as a combined-system map.
See `address_map.txt` and the redistribution limitations in `docs/third_party.md`.
