# Vision migration status

Status as of 2026-10-25; hardware observations below refer to the external
`vision_studio` workspace, not a hardware release from this repository.

## Included

- PC per-eye HSV segmentation and frame-local component centroids.
- Raw RGB565/image loading, interactive threshold editing and offline preview.
- Explicit live SSH snapshot access to the existing fixed-address capture buffer.
- Synthetic regression tests for color, area/border checks, eye order, controls
  and stream reads.

## Hardware source and static reference

The ch19-derived static HDMI baseline has displayed a 1280 x 720 grid without
visible misalignment in a user observation. Other initializations showed horizontal
wraparound. Repeat-start stability and the complete live stereo path remain to be
accepted. The original ch19 bitstream with an 800 x 480 Python initialization test
produced a black screen; that does not establish a defect in the complete official
bare-metal example.

Experimental capture, preprocessing/SAD RTL, their testbenches and standalone
build scripts are included. A historical static HDMI bit/HWH pair is exported as
`hdmi-baseline-v0.1.0`, with hashes, private address map and a matching test runner.
No experimental stereo/depth binary is exported as a verified release.

The prior capture/depth experiments contain frame-size error flags, single-buffer
read/write risks and source/build/deployment version differences. A static image
passing HDMI checks does not validate stereo frame identity or exposure alignment.
No MarkerFrame packaged IP or completed FPGA repair claim accompanies this migration.

## Remaining before XYZ integration

1. Stable complete frames with source frame IDs and defined capture timing.
2. Verified left/right temporal alignment and complete stereo calibration.
3. One-to-one stereo matching and persistent identities, including repeated colors.
4. Calibrated 3D reconstruction and independent spatial/dynamic error measurements.
5. An adapter to the shared nine-marker, metre-unit, float32 MarkerFrame contract.

The old approximate focal/baseline scale is not migrated as validated calibration.
Neither 20 Hz point output nor 5 mm XYZ accuracy has been demonstrated. The existing
160 x 180 integer-depth branch is not a substitute for marker-specific validation.
The shared contract is unchanged; no data is connected to fusion or integration.
