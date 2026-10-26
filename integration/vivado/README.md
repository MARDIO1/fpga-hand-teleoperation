# First-board Vivado integration

This project combines the packaged MPU6050 acquisition IP and the current HLS
fusion IP into one ACZ7015 bitstream. It preserves the standalone addresses:

- `hand_core`: `0x43C00000`
- `mpu6050_imu`: `0x43C10000`

Run `build.cmd` to recreate, synthesize and implement the project. Generated
Vivado state, reports and output artifacts remain ignored. Building does not
program the board; loading `output/first_board.bit` is a separate manual step.

The reviewed candidate is copied to `../export/bitstream/acz7015/v0.1.0/` only
after implementation passes. Its build metadata also records the separate
on-board smoke-test result.
