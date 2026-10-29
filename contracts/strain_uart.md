# F103 IMU and strain UART v1

Fixed-size transport from the STM32F103C8T6 to the Zynq PS.

- UART: `115200 8N1`
- USB CDC: the same IMUQ frames and calibration command on the virtual serial port
- byte order: little-endian
- rate: `100 Hz`
- frame size: `46 bytes`
- structure: `<4sBBHII4f5HhH`

| Offset | Type | Field |
| ---: | --- | --- |
| 0 | `char[4]` | ASCII `IMUQ` |
| 4 | `uint8` | version, currently `1` |
| 5 | `uint8` | status flags |
| 6 | `uint16` | frame size, `46` |
| 8 | `uint32` | sequence |
| 12 | `uint32` | F103 boot-relative `timestamp_us` |
| 16 | `float32[4]` | quaternion in `[w, x, y, z]` order |
| 32 | `uint16[5]` | raw strain ADC channels |
| 42 | `int16` | raw MPU6050 temperature |
| 44 | `uint16` | CRC-16/CCITT-FALSE over bytes 0 through 43 |

Status flags:

| Bit | Meaning |
| ---: | --- |
| 0 | MPU6050 present |
| 1 | current IMU sample valid |
| 2 | manual gyro calibration in progress |
| 3 | gyro calibration complete |
| 4 | UART transmit drop observed |
| 5 | MPU6050 initialization error |
| 6 | USB transmit drop observed |

CRC parameters are polynomial `0x1021`, initial value `0xffff`, no reflection,
and final XOR `0x0000`. Sequence detects dropped frames. The PS records its own
monotonic arrival time for diagnostics; the MCU timestamp is boot-relative and
does not share the Zynq clock.

The current five-channel build scans the ADC slots in this order:

| Slot | STM32F103 pin | ADC channel |
| ---: | --- | --- |
| 0 | PA2 | ADC1_IN2, legacy middle-finger channel |
| 1 | PA0 | ADC1_IN0 |
| 2 | PA3 | ADC1_IN3 |
| 3 | PA4 | ADC1_IN4 |
| 4 | PA5 | ADC1_IN5 |

An unavailable conversion contains `0xffff`, so the receiver must not interpret
it as a valid measurement.

Calibration is manual. The PS sends one ASCII `C` or `c` byte to start gyro
calibration. Keep the sensor stationary while status bit 2 is set. Calibration
has completed when bit 2 clears and bit 3 becomes set.
