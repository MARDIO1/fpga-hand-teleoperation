# Optimized XYZ v0.2.0

Board-tested 2026-10-27 on ACZ7015, xc7z015clg485-2, 100 MHz,
Vivado/Vitis HLS 2025.2. Keep bit/HWH paired. Latest software lives in
`modules/vision/vivado/optimized_xyz/software`, not the old laboratory ZIP.

Measured point-only throughput: 29.564 FPS. With asynchronous preview capped at
2 Hz: 28.620 FPS. Each mode ran 600 frames; see OPTIMIZATION_REPORT.md and
validation/{points,preview}. Resource use: LUT 58.41%, FF 32.55%, BRAM36 38.95%,
DSP 40.00%. Constrained setup/hold slack: +0.898/+0.047 ns; sensor timing
coverage remains incomplete. Experimental millimetres and frame-local IDs.

Setup/rebuild: [optimized release](../../../../vivado/optimized_xyz/README.md).
`build_info.json` hashes the frozen sources, software, packaged IP, hardware and
validation evidence. Earlier build_validation.json records the original local
build paths, while build_info.json uses repository-relative paths.
