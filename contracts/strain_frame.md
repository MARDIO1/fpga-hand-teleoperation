# StrainFrame v0.2

Produced by the strain module and consumed by frame synchronization/fusion.

| Field | Type | Meaning |
| --- | --- | --- |
| magic/version | `uint32` | Contract identifier and version |
| sequence | `uint32` | Strain-sample sequence number |
| timestamp_us | `uint32` | Sample time in microseconds |
| raw[5] | `uint16` | Thumb through little-finger raw bend values |

The PS retains the newest complete strain frame and assigns its monotonic arrival
time to the common camera/IMU timeline. The source timestamp remains available
for spacing and packet-loss diagnostics.

The F103 wire representation is defined in `strain_uart.md`.
