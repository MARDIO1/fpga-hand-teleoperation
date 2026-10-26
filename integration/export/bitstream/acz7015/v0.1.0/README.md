# ACZ7015 first-board candidate v0.1.0

This candidate combines MPU6050 acquisition and the camera/IMU/strain fusion
core in one bitstream. Vivado implementation, routing, DRC and timing signoff
passed. The physical ACZ7015 smoke test passed on 2026-10-26.

The current PS program can continue reading the MPU at `0x43C10000`. The fusion
core is available at `0x43C00000`; moving runtime fusion calls from PS into this
core is the next software step.

The combined smoke test completed one `hand_core` transaction, sampled the MPU
without I2C errors, decoded the 100 Hz strain UART without rejects, and delivered
1300 consecutive UDP packets to the PC with no drops or rejects. USB `error -71`
remained at zero after the single PL reconfiguration.
