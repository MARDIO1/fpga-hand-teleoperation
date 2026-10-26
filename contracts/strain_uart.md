# F103 strain UART v1

Minimal fixed-size transport from the F103 to the Zynq PS.

- UART: `115200 8N1`
- byte order: little-endian
- rate: `100 Hz`
- frame size: `28 bytes`

| Offset | Type | Field |
| ---: | --- | --- |
| 0 | `char[4]` | ASCII `STRN` |
| 4 | `uint8` | version, currently `1` |
| 5 | `uint8` | flags, currently `0` |
| 6 | `uint16` | frame size, `28` |
| 8 | `uint32` | sequence |
| 12 | `uint32` | F103 boot-relative `timestamp_us` |
| 16 | `uint16[5]` | thumb, index, middle, ring, little raw ADC values |
| 26 | `uint16` | CRC-16/CCITT-FALSE over bytes 0 through 25 |

CRC parameters are polynomial `0x1021`, initial value `0xffff`, no reflection,
and final XOR `0x0000`. Sequence detects dropped frames. The PS records its own
monotonic arrival time for camera/IMU alignment; the F103 timestamp is retained
for sample spacing and diagnostics but is not assumed to share the Zynq clock.
