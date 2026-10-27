# Current standalone release: compact XYZ v0.1.0

This is the selected 2026-10-26 board-tested version, replacing the older HDMI
baseline as the vision module's current standalone result. The original source
layout is retained here so the HLS and board tools keep their relative imports.
No generated Vivado project, raw capture, HDMI branch or ingress-V2 experiment is
included. Shared vendor camera sources remain in `../../rtl/vendor/acz7015_ch62`.

PL: RGB565 HSV/RLE/CCL and double-precision sparse rectification/triangulation.
PS: candidate filtering, C++ unique stereo matching, DMA and result publication.
PC: visualization. Coordinates are experimental millimetres in the physical left
camera optical frame (X right, Y down, Z forward); IDs are frame-local.
This is not yet the shared metre/float32 MarkerFrame contract or integrated fusion.

## Prepare and run

From the repository root:

```sh
python -m pip install -r modules/vision/vivado/compact_xyz/requirements.txt
python modules/vision/vivado/compact_xyz/prepare_release.py
```

The command checks all frozen release hashes and stages a flat board bundle in
`overlays/dual_camera_hdmi/output/compact_xyz/` beneath this directory. Copy that
bundle to a board directory. On the ACZ7015 PYNQ image, build the native matcher:

```sh
g++ -std=c++11 -O2 marker_match.cpp test_marker_match.cpp -o test_marker_match
./test_marker_match
g++ -std=c++11 -O2 -shared -fPIC marker_match.cpp -o libmarker_match.so
```

Loading an overlay requires first stopping the existing camera/marker processes
and halting/resetting their DMA/VDMA. The optional `hls_geometry/deploy_compact.py`
performs that existing board-specific sequence and disables the old HDMI service;
do not use it merely to inspect files. Inspect its host/board assumptions first.
For a quiesced board, from the copied bundle:

```sh
sudo python3 start_compact.py
sudo python3 -u run_markers_board.py --calibrated --frames 0 --fps 30 --snapshot-fps 2
```

`--fps 30` is a limit, not achieved throughput. The recorded full-cycle rate is
8.61 Hz; acquisition is approximately 29.7 FPS. PC preview, from this directory:

```sh
python overlays/dual_camera_hdmi/hls_markers/preview_markers_board.py
```

Install paramiko on the PC; the connection helper defaults to the existing board
image's xilinx account at 192.168.137.99. Update connection settings for your image.
The preview reads `/dev/shm/marker_results/latest.bin`; points are in `latest.json`.

## Rebuild and validate

Tools: Vivado and Vitis HLS 2025.2; part xc7z015clg485-2, 100 MHz.
`prepare_release.py` unpacks the exact published HLS IP into ignored `output/`.
From this directory, use those packages to rebuild the standalone bitstream:

```sh
vivado -mode batch -source overlays/dual_camera_hdmi/hls_geometry/build_compact.tcl
```

On Windows, set `VISION_COMPACT_PROJECT` to an unused short path if Vivado exceeds
its path-length limit. Generated output stays ignored. `finish_compact.tcl`
rejects resource usage above 60% or failing setup/hold timing before exporting.

To regenerate geometry IP from source, run `hls_geometry/prepare_fixtures.py`, then
Vitis HLS `hls_geometry/run_hls.tcl` and `cosim.tcl`. The checked-in deterministic
fixtures and calibration live in `../../data/samples/compact_xyz`. For marker IP,
run `hls_markers/prepare_fixtures.py`, then `run_hls.tcl` with GLOVE_HLS_STAGE set
to csim, synth and cosim, followed by `export_ip.tcl`. Use Vitis HLS's Tcl runner
(e.g. `vitis-run --mode hls --tcl <script>`), all from this directory.

Local Python regressions:

```sh
python -m unittest discover -s overlays/dual_camera_hdmi -p "test_*.py" -v
python -m unittest discover -s overlays/dual_camera_hdmi/hls_markers -p "test_*.py" -v
```

Published evidence and hashes are in
`../../export/bitstream/acz7015/compact-xyz-v0.1.0/`. Existing board reports cover
384 C-simulation points, 12 RTL cosimulation points, historical replay and live
board comparisons. Reference agreement is not physical distance accuracy.
The source migration does not rerun a complete Vivado/HLS build or hardware test.
DDR snapshots may tear, exposure synchronization and absolute accuracy remain
unverified, and no automatic boot configuration is included.
