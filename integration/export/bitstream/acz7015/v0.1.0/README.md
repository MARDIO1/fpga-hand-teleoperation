# ACZ7015 first-board candidate v0.1.0

This candidate combines MPU6050 acquisition and the camera/IMU/strain fusion
core in one bitstream. Vivado implementation, routing, DRC and timing signoff
passed. It has not yet been loaded on the physical board.

The current PS program can continue reading the MPU at `0x43C10000`. The fusion
core is available at `0x43C00000`; moving runtime fusion calls from PS into this
core is the next software step.
