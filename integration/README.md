# Board integration

This area owns the only combined ACZ7015 design. It will connect the vision, strain and fusion packaged IP, perform timestamp alignment and expose PS configuration/status plus UDP debugging.

`modules/imu` supplies an independently tested MPU6050 prototype and ImuFrame
contract. It is not yet connected here. Its ARM estimator and PL packet interface
must remain together until a PL estimator is implemented; its standalone PL
timestamp must be aligned to the common integration timebase before fusion.

Module test bitstreams are never nested or linked here. The final Vivado build consumes module IP and emits its own `.bit`, `.hwh` and `.xsa` under `export/bitstream/`.

## First-board bring-up

The current one-IMU/one-strain version deliberately uses the standalone MPU6050
overlay. Loading it replaces the active PL image. From the repository root on the
board, first record the repeatable three-pose strain calibration:

```bash
python3 modules/strain/software/ps/calibrate_strain.py --channels 2
```

Then keep the hand still for the first two seconds and start the SSH-run streamer:

```bash
sudo python3 integration/software/ps/board_stream.py
```

The PS reads `/dev/ttyUSB0`, solves the MPU6050 attitude, maps the calibrated
middle-finger bend, and sends `HAND v2` to `192.168.137.1:47000` at 100 Hz. Camera
position is invalid in this first-board version, so the PC display holds its
default wrist position.
