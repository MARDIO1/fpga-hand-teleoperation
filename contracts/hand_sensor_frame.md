# HandSensorFrame v2

PS sends this little-endian 84-byte UDP datagram to the PC display on port 47000.
IMU attitude and strain mapping are completed on the board; raw inertial values
remain available for optional diagnostics.

| Offset | Type | Field |
| ---: | --- | --- |
| 0 | `uint32` | magic `0x444e4148` (`HAND`) |
| 4 | `uint16` | version `2` |
| 6 | `uint16` | type `1` (sensor/display input) |
| 8 | `uint32` | sequence |
| 12 | `uint32` | board-relative timestamp, microseconds |
| 16 | `uint8` | reset display reference |
| 17 | `uint8` | camera position valid |
| 18 | `uint8` | IMU quaternion valid |
| 19 | `uint8` | reserved |
| 20 | `float32[3]` | wrist XYZ, metres |
| 32 | `float32[4]` | wrist quaternion, WXYZ |
| 48 | `float32[3]` | diagnostic linear acceleration |
| 60 | `float32[3]` | diagnostic angular velocity |
| 72 | `uint16[5]` | board-calibrated bend: 0 = open, 4095 = fully bent |
| 82 | `uint16` | reserved |

The PC rejects duplicate and out-of-order sequences. A missing source holds its
last value and clears the corresponding validity flag; it does not reset the hand.
