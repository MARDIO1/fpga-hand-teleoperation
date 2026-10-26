# Frozen HLS IP for compact XYZ v0.1.0

Vitis HLS 2025.2 packages: glove_markers (HSV/RLE/CCL) and marker_geometry
(double sparse geometry), matching the selected board release. Source and rebuild
scripts: `../../../vivado/compact_xyz/overlays/dual_camera_hdmi/hls_markers/` and
`hls_geometry/`. These are standalone internal interfaces, not MarkerFrame IP.
Run the standalone `prepare_release.py` to verify and unpack them for Vivado.
