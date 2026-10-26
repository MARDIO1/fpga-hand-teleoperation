# Board integration

This area owns the only combined ACZ7015 design. It will connect the vision, strain and fusion packaged IP, perform timestamp alignment and expose PS configuration/status plus UDP debugging.

`modules/imu` supplies an independently tested MPU6050 prototype and ImuFrame
contract. It is not yet connected here. Its ARM estimator and PL packet interface
must remain together until a PL estimator is implemented; its standalone PL
timestamp must be aligned to the common integration timebase before fusion.

Module test bitstreams are never nested or linked here. The final Vivado build consumes module IP and emits its own `.bit`, `.hwh` and `.xsa` under `export/bitstream/`.
