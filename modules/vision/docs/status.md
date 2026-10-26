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
