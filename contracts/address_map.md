# Address map

The final address map is owned by `integration/`. Module test designs may use private addresses that are documented with their exported bitstreams.

Current standalone fusion overlay:

| Peripheral | Base | Range |
| --- | ---: | ---: |
| `hand_core` | `0x43C00000` | `0x1000` |

Standalone MPU6050 prototype overlay (a separate bitstream):

| Peripheral | Base | Range |
| --- | ---: | ---: |
| `imu` | `0x43C10000` | `0x1000` |

Its register layout is defined in [ImuFrame](imu_frame.md). This private test
address is not an allocation in the final integration design.
