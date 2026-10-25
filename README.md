# FPGA Hand Teleoperation

ACZ7015/Zynq-7015 hand-observation pipeline developed as four independently testable modules and one final board integration.

## Ownership

| Area | Responsibility | Standalone result |
| --- | --- | --- |
| `modules/vision` | Stereo cameras, preprocessing and marker XYZ output | Packaged vision IP and module test bitstream |
| `modules/strain` | Five-channel strain acquisition and preprocessing | Packaged strain IP and module test bitstream |
| `modules/imu` | MPU6050 six-axis acquisition, PL timestamps and ARM attitude estimation | Packaged acquisition/packet IP, module test bitstream and PC viewer |
| `modules/fusion` | Marker/strain mapping, filtering and hand-state reconstruction | Packaged fusion IP and module test bitstream |
| `integration` | Frame synchronization, PS control and final ACZ7015 design | The final combined bitstream |

Each module owns its sources, simulation, data, Vivado test project and exported artifacts. A module bitstream proves that module on hardware; it is not linked into the final image. `integration/vivado` consumes packaged IP from the module areas and is the only place that produces the combined board bitstream.

## Repository rules

- Keep cross-module packet formats in `contracts/`.
- Keep reproducible sources and build scripts in Git; generated Vivado/HLS runs stay ignored.
- Small deterministic samples may be committed. Raw videos and large datasets stay outside Git and are described by a manifest with checksums.
- A change to a shared contract must update its version and all affected tests.
- The production path remains floating-point until measured performance or resource use requires a change.

## Current baseline

The repository starts with the validated floating-point fusion core, its independent ACZ7015 overlay, the PS UDP bridge and the MuJoCo virtual-hand simulator. Vision and strain owners can migrate only the parts they want into their clean module areas.

The [MPU6050 prototype](modules/imu/README.md) adds a standalone six-axis/raw-plus-attitude stream. It remains separate from vision, strain and fusion; its measured throughput and known calibration/display interruptions are recorded in the module status document.
