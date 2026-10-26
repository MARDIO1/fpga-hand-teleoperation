# Shared contracts

These documents define the boundaries between independently developed modules. Payload fields are little-endian. Cross-module PL streams use 32-bit AXI4-Stream words and assert `TLAST` on the final word of one frame.

CameraFrame, StrainFrame and HandPoseFrame use version `0.2`. The independent
[ImuFrame](imu_frame.md) contract is version `1`, with a fixed 16-word payload
containing original six-axis samples, temperature, Euler attitude and the same
64-bit PL acquisition timestamp. [HandSensorFrame](hand_sensor_frame.md) defines
the separate PS-to-PC `HAND v2` display datagram. The F103 wire format is defined
by [strain_uart.md](strain_uart.md).
