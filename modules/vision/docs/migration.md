# Migration provenance

Selected from the local `vision_studio` working tree on 2026-10-25. The source
working tree contains uncommitted development, so its HEAD alone does not identify
these files. This is a selected-source migration, not an import of old Git history.

| Original location below vision_studio | Destination below modules/vision |
| --- | --- |
| overlays/dual_camera_hdmi/marker_detection.py | software/pc/marker_detection.py |
| overlays/dual_camera_hdmi/preview_glove_pc.py | software/pc/preview_glove_pc.py |
| overlays/dual_camera_hdmi/glove_color_thresholds.json | software/pc/config/glove_color_thresholds.json |
| load_rgb565 and rgb565_bgr in overlays/dual_camera_hdmi/preview_downsample.py | software/pc/rgb565.py |
| overlays/dual_camera_hdmi/test_marker_detection.py | tests/test_marker_detection.py |

Migration changes: relative module paths; RGB565 utilities separated from the
depth-comparison program; explicit live host; prompted/environment credentials;
SSH host-key verification; normal package dependencies; ignored raw-output path.
The color detection algorithm and bundled thresholds are retained. New tests
cover the migrated entry point and file utility boundary.

`status.md` summarizes relevant hardware observations and limitations instead of
copying chronological debug logs. Calibration data, real captures, private keys,
password values, machine-specific tool paths and whole vendor bundles are excluded.
Shared contracts, fusion, strain and integration are unchanged.

## Hardware batches

`hardware_source_manifest.json` records selected original file locations and SHA-256
checksums before migration edits. Capture files are in `rtl/capture/`, experimental
SAD/preprocessing/display files in `rtl/depth/`, shared display diagnostics in
`rtl/display/`, testbenches in `sim/`, and minimal ch62 dependencies in
`rtl/vendor/acz7015_ch62/`. Source XCI and display-IP repositories live in `vivado/`.

The baseline rebuild Tcl is selected from the pre-monitor file in the source
repository HEAD, then adjusted to the new module paths. The current stereo build
is selected from the working tree. Generated files are confined to ignored
`vivado/project/` and `vivado/output/`; checked-in release files are not build outputs.
The original runtime helper and minimal board reset prerequisites are retained under
`software/ps/`, with explicit matching-bitstream arguments for the test runners.

The only binary import is the saved pre-monitor, user-confirmed static HDMI bit/HWH
pair. Its source association is documented as historical, not a bit-identical
rebuild claim. Current timing-monitor binaries, unaccepted stereo binaries and
the original 800 x 480 black-screen experiment remain outside the export.
The checked-in depth color table remains an approximate historical visualization;
no validated calibration is supplied.
