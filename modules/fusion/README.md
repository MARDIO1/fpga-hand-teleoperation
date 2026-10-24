# Fusion module

Floating-point reconstruction baseline. Inputs are already-decoded marker XYZ values plus five strain values; the module does not contain camera processing or ADC acquisition.

## Layout

- `hls/`: synthesizable algorithm and public C++ types
- `tests/`: native and RTL co-simulation testbenches
- `vivado/`: independent PS-to-AXI4-Lite test overlay
- `software/`: PYNQ userspace MMIO/UDP test bridge
- `export/ip/`: packaged HLS IP archive
- `export/bitstream/`: independently tested ACZ7015 overlay

Run `run_native.cmd` from this directory for the native tests. Vitis HLS uses `hls_config.cfg`. The standalone Vivado overlay is rebuilt with `vivado/build_overlay.cmd` after HLS has produced `build/hls/impl/ip`.
