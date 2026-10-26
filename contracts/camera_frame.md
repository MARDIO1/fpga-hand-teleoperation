# CameraFrame v0.2

Produced by the vision module and consumed by fusion.

| Field | Type | Meaning |
| --- | --- | --- |
| sequence | `uint32` | Camera-frame sequence number |
| timestamp_us | `uint32` | Observation time in microseconds |
| valid | `uint8` | Wrist position is available |
| wrist_xyz[3] | `float32` | Wrist/palm position in world metres |

The camera no longer supplies palm orientation or individual finger markers.
