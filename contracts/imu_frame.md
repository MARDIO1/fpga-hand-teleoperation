# ImuFrame v0.2

Produced by the dorsal IMU preprocessing stage and consumed by fusion.

| Field | Type | Meaning |
| --- | --- | --- |
| sequence | `uint32` | IMU sample sequence number |
| timestamp_us | `uint32` | Sample time in microseconds |
| valid | `uint8` | Fused orientation is available |
| quaternion_wxyz[4] | `float32` | Palm-to-world orientation |
| linear_acceleration[3] | `float32` | Gravity-free acceleration in IMU body axes, m/s^2 |
| angular_velocity[3] | `float32` | Body angular velocity, rad/s |

The fast-delivery PS path records acceleration and angular velocity for diagnosis
but does not integrate them into position. Missing camera updates hold the last
position. Quaternion orientation remains live at the IMU rate.
