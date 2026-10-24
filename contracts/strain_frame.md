# StrainFrame v0.1

Produced by the strain module and consumed by frame synchronization/fusion.

| Field | Type | Meaning |
| --- | --- | --- |
| magic/version | `uint32` | Contract identifier and version |
| sequence | `uint32` | Strain-sample sequence number |
| timestamp_us | `uint32` | Sample time in microseconds |
| raw[5] | `uint16` | Thumb through little-finger raw bend values |

The integration block retains the newest complete strain frame whose timestamp is not later than the marker frame being solved.
