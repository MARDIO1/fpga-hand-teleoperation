# Shared contracts

These documents define the boundaries between independently developed modules. Payload fields are little-endian. Cross-module PL streams use 32-bit AXI4-Stream words and assert `TLAST` on the final word of one frame.

MarkerFrame, StrainFrame and HandPoseFrame remain at `0.1`. The independent
[ImuFrame](imu_frame.md) contract is version `1`, with a fixed 16-word payload
containing original six-axis samples, temperature, Euler attitude and the same
64-bit PL acquisition timestamp. Existing fusion inputs are unchanged.
