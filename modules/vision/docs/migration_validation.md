# Migration verification, 2026-10-25

All checks below ran against the new module directory. They do not require the
old workspace at runtime. This migration did not connect to, reload or change the
running board.

## Passed

- 14 Python unittest cases: color segmentation, controls, eye order, stream reads,
  standalone offline CLI without Paramiko, invalid inputs, imported bit/HWH and
  source snapshot hashes, HWH module/address checks and display IP file references.
- Eight Vivado XSim cases: line controller, HDMI timing monitor, preprocessing,
  two-frame stream chain, depth overlay, and SAD at 4, 8 and 16 lanes.
- Vivado 2025.2 project creation, BD validation and target generation for the
  pre-monitor HDMI baseline and `ch19_display` stereo comparison.
- Syntax compilation of the four migrated PS Python files, documentation link
  checks and `git diff --check`.

PC Python checks used OpenCV 4.11.0 and NumPy 2.2.2. Dependency ranges are not a
claim that all permitted versions were exercised. On this host the sandbox's
default temporary directory was not writable, so the test process used the ignored
`modules/vision/data/raw/test_tmp/` directory for TMP/TEMP. No such setting is
required by the tests on hosts with a writable standard temporary directory.

## Not claimed

- Full post-migration synthesis, routing, bit generation or a bit-identical rebuild.
- New packaged MarkerFrame IP, complete stereo calibration, XYZ accuracy or fusion
  integration.
- On-board verification of the migrated PS paths, repeated startup stability, live
  stereo anti-tearing or exposure synchronization.
- Hardware acceptance of the experimental depth variants. Their RTL simulations
  passed; only the two named standalone designs underwent BD generation here.

The exported static reference retains its historical validation scope. Future
rebuilds should go to ignored outputs and be separately accepted before updating
the versioned release and its hashes. No Git commit or push was made by migration.
