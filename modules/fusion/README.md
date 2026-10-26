# Fusion module

Floating-point reconstruction baseline. Inputs are camera wrist XYZ, one dorsal-IMU
quaternion/acceleration/gyro sample, and five strain values. The core infers finger
spread from bend and uses bounded inertial prediction only during short camera loss.

## Layout

- `hls/`: synthesizable algorithm and public C++ types
- `tests/`: native and RTL co-simulation testbenches
- `vivado/`: independent PS-to-AXI4-Lite test overlay
- `software/`: PYNQ userspace MMIO/UDP test bridge
- `export/ip/`: packaged HLS IP archive
- `export/bitstream/`: independently tested ACZ7015 overlay

Run `run_native.cmd` for the native tests and `build_hls.cmd` to synthesize and
package the current IP. The build script stages inputs under `%TEMP%` because
Vitis HLS rejects the repository's space-containing parent path. The standalone
Vivado overlay is rebuilt with `vivado/build_overlay.cmd` after HLS has produced
`build/hls/impl/ip`.
