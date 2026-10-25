# Standalone vision hardware

Target: ACZ7015, `xc7z015clg485-2`, Vivado 2025.2. Run commands from the repository
root with Vivado tools on PATH. No old `vision_studio` directory is required.

```sh
vivado -mode batch -source modules/vision/vivado/create_hdmi_baseline.tcl
vivado -mode batch -source modules/vision/vivado/create_hdmi_baseline.tcl -tclargs build
vivado -mode batch -source modules/vision/vivado/create_stereo.tcl -tclargs ch19_display
vivado -mode batch -source modules/vision/vivado/create_stereo.tcl -tclargs build ch19_display
```

Without `build`, scripts create and validate the design and generate IP/HDL; they
do not run implementation. Generated projects and outputs stay in ignored
`project/` and `output/`. Builds never overwrite versioned export directories.

| Design | Purpose | Project/output subdirectory |
| --- | --- | --- |
| create_hdmi_baseline.tcl | Pre-monitor ch19-derived DDR-to-HDMI static baseline | hdmi_baseline |
| create_stereo.tcl, ch19_display | Capture plus direct ch19 display comparison; no depth | ch19_display |
| create_stereo.tcl, no variant | Original stereo/OSD comparison | stereo |
| create_stereo.tcl, pl_depth | Experimental AXI DMA SAD branch | pl_depth |
| create_stereo.tcl, pl_stream | Experimental streaming preprocessing/SAD/display | pl_stream |

Experimental variants are sources, not validated releases. Only the pre-monitor
static HDMI baseline is exported in this migration. Camera timing constraints
remain incomplete; positive reported slack does not validate unconstrained DVP
sampling. The patched ch62 controller preserves A/B byte ordering but does not
compare eye row IDs or guarantee simultaneous exposure.

The checked-in `depth_palette.vh` is a historical visualization table generated
using an approximate scale; it is not a calibration model or XYZ result. No old
metric scale is required to rebuild this frozen table. Its numeric colors must
not be treated as verified distances.

## Simulation

```powershell
powershell -ExecutionPolicy Bypass -File modules/vision/sim/run_sim.ps1
```

If tools are not on PATH, pass `-VivadoBin <Vivado-bin-directory>`.
The script checks eight cases: line ordering, native timing monitor, preprocessing,
two-frame stream, depth overlay and SAD at 4/8/16 lanes. FIFO behavior in the stream
tests uses the small behavioral model embedded in `tb_stream_preproc.sv`; these
tests do not replace XPM/CDC timing or real-board validation.

## Source and IP ownership

`rtl/vendor/acz7015_ch62/` contains only the camera initializer, line formatter and
FIFO wrapper used by this design. `ip_repo/` contains the board display converters
and Digilent dynamic-clock IP with their original notices. See
`../docs/third_party.md` for attribution and license limitations. AMD IP is generated
by Vivado from XCI/configuration; generated implementations and SDKs are not copied.
