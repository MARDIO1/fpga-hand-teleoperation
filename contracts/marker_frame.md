# MarkerFrame v0.1

Produced by the vision module and consumed by frame synchronization/fusion.

| Field | Type | Meaning |
| --- | --- | --- |
| magic/version | `uint32` | Contract identifier and version |
| sequence | `uint32` | Camera-frame sequence number |
| timestamp_us | `uint32` | Observation time in microseconds |
| valid_mask | `uint32` | One validity bit per marker ID |
| xyz[9][3] | `float32` | Nine marker positions in metres |

Marker IDs and coordinate-frame orientation will be frozen before the vision IP is connected to integration.
