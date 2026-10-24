# HandPoseFrame v0.1

Produced by fusion for PS debugging and future teleoperation.

| Field | Type | Meaning |
| --- | --- | --- |
| sequence | `uint32` | Source marker-frame sequence |
| timestamp_us | `uint32` | Source marker-frame timestamp |
| position[3] | `float32` | Palm position in metres |
| rotation[9] | `float32` | Row-major 3 by 3 palm rotation |
| bend[5] | `float32` | Reconstructed finger bend |
| spread[5] | `float32` | Reconstructed finger spread |
| valid_mask | `uint16` | Marker validity used for this result |
| valid | `uint8` | Output validity |
| state | `uint8` | Tracking, predict, damp, hold or reacquire |
