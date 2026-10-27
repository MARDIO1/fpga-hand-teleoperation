# Vision status, 2026-10-27

Selected release: **optimized-xyz-v0.2.0**, board-tested 2026-10-27.
Complete measured output is 29.564 FPS point-only and 28.620 FPS with asynchronous
preview capped at 2 Hz. Each mode covers 600 frames, measured using consecutive
completion timestamps. No publication queue drops or hardware errors were observed.
These scenes had few matched pairs and do not establish worst-case throughput.

See [setup and rebuild](../vivado/optimized_xyz/README.md) and
[measured evidence](../export/bitstream/acz7015/optimized-xyz-v0.2.0/OPTIMIZATION_REPORT.md).
The FIFO reader, II=1 color core and bounded publisher are included with matching
bit/HWH and frozen IP. Same-frame preview ownership was checked on the board.
The source migration itself does not reload the board or rerun synthesis.

Camera timing constraints, exposure synchronization, physical XYZ accuracy and
long-term stability remain unverified. Coordinates are experimental millimetres
and IDs are frame-local; the shared metre/float32 MarkerFrame contract and fusion
adapter remain unchanged and unimplemented by this release.

## Historical compact release status (2026-10-26)

# Vision status, 2026-10-26

The selected standalone result is **compact-xyz-v0.1.0**, compiled and board-tested
on 2026-10-26. It performs PL color-component detection and calibrated geometry,
with PS C++ pairing and PC visualization. HDMI has been removed from this version.
See [setup and rebuild](../vivado/compact_xyz/README.md) and
[board evidence](../export/bitstream/acz7015/compact-xyz-v0.1.0/compact_validation.md).

The matching bit/HWH and seven key board-side file hashes were checked over SSH
against the local latest release. The migration does not restart or reload hardware.
The recorded full-cycle rate is 8.61 Hz, with 2 Hz preview; it is not 20/30 Hz XYZ.
Reported numerical differences measure agreement with the PC implementation,
not absolute physical accuracy. Calibration is experimental, units are millimetres,
coordinates are relative to the physical left optical centre, IDs are frame-local.
DDR tearing and simultaneous exposure remain unverified.

The shared nine-marker metre/float32 MarkerFrame interface remains unchanged.
No adapter, persistent identity, final integration, 5 mm accuracy or restart
stability claim is made. The older static HDMI release and experimental SAD
sources remain historical references; ingress V2 is excluded from this release.
