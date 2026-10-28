# STM32F103C8T6 IMU + strain acquisition

This is the CubeMX/HAL firmware used for the first hardware bring-up.

## Wiring

| Signal | STM32F103C8T6 pin | Notes |
| --- | --- | --- |
| MPU6050 VCC | 3.3 V | Do not feed an unknown bare MPU6050 board with 5 V |
| MPU6050 GND | GND | Common ground with USB-TTL |
| MPU6050 SCL | PB6 / I2C1_SCL | External pull-ups are normally present on GY-521 boards |
| MPU6050 SDA | PB7 / I2C1_SDA |  |
| MPU6050 INT | PB5 / EXTI5 | Rising-edge data-ready interrupt |
| MPU6050 AD0 | GND | Selects address `0x68` |
| Strain OUT | PA2 / ADC1_IN2 | Input must remain between 0 V and 3.3 V |
| USB-TTL RX | PA9 / USART1_TX | Cross TX to RX |
| USB-TTL TX | PA10 / USART1_RX | Cross RX to TX |
| USB-TTL GND | GND | Required |

## Runtime

- MPU6050: ±4 g, ±2000 dps, DLPF setting 2, 500 Hz sample request.
- MPU requests 500 Hz data-ready. With the current 100 kHz I2C and EKF load,
  the measured processing rate is about 216 Hz; integration uses the measured
  elapsed time instead of assuming 500 Hz.
- Telemetry: 115200 8-N-1, 100 Hz, UART TX DMA.
- Calibration: send ASCII `C` or `c` while the unit is stationary. The next
  2500 processed samples (currently about 12 seconds) estimate gyro bias.
  Power-up never starts a calibration automatically.
- I2C1 is currently generated at CubeMX's valid 100 kHz default. Set Fast Mode
  400 kHz in CubeMX before sustained 500 Hz hardware validation; the application
  code requires no change.

## Binary telemetry packet (46 bytes, little-endian)

| Offset | Size | Field |
| ---: | ---: | --- |
| 0 | 4 | Magic `IMUQ` |
| 4 | 1 | Version, currently 1 |
| 5 | 1 | Status bits |
| 6 | 2 | Packet length, 46 |
| 8 | 4 | Sequence number |
| 12 | 4 | Timestamp in microseconds (1 ms resolution) |
| 16 | 16 | Quaternion `float32 [w, x, y, z]` |
| 32 | 10 | Five ADC `uint16` slots; PA2 is slot 0, unused slots are `0xFFFF` |
| 42 | 2 | MPU6050 raw temperature `int16` |
| 44 | 2 | CRC-16/CCITT-FALSE over bytes 0..43 |

Status bits are: bit 0 MPU detected, bit 1 valid sample, bit 2 calibrating,
bit 3 calibrated, bit 4 a telemetry packet was dropped because DMA was busy,
and bit 5 MPU initialization failed after reset. Initialization is retried up
to five times at 500 ms intervals.

Build without STM32CubeIDE:

```powershell
./build.ps1
```
