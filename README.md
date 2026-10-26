# FPGA Hand Teleoperation

ACZ7015/Zynq-7015 hand-observation pipeline developed as three independently testable FPGA modules and one final board integration.

## Ownership

| Area | Responsibility | Standalone result |
| --- | --- | --- |
| `modules/vision` | Camera preprocessing and wrist XYZ output | Packaged vision IP and module test bitstream |
| `modules/strain` | Five-channel strain acquisition and preprocessing | Packaged strain IP and module test bitstream |
| `modules/fusion` | Camera/IMU/strain fusion and hand-state reconstruction | Packaged fusion IP and module test bitstream |
| `integration` | Frame synchronization, PS control and final ACZ7015 design | The final combined bitstream |

Each module owns its sources, simulation, data, Vivado test project and exported artifacts. A module bitstream proves that module on hardware; it is not linked into the final image. `integration/vivado` consumes packaged IP from the three module areas and is the only place that produces the combined board bitstream.

## Repository rules

- Keep cross-module packet formats in `contracts/`.
- Keep reproducible sources and build scripts in Git; generated Vivado/HLS runs stay ignored.
- Small deterministic samples may be committed. Raw videos and large datasets stay outside Git and are described by a manifest with checksums.
- A change to a shared contract must update its version and all affected tests.
- The production path remains floating-point until measured performance or resource use requires a change.

## Current baseline

The repository starts with the validated floating-point fusion core, its independent ACZ7015 overlay, the PS UDP bridge and the MuJoCo virtual-hand simulator. Vision and strain owners can migrate only the parts they want into their clean module areas.
