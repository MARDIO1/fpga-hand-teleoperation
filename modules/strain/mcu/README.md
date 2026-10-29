# STM32 IMU and strain acquisition node

STM32F103C8T6 firmware reads an MPU6050 and analog strain channels, runs the
quaternion EKF, and sends one CRC-protected UART frame to the Zynq PS at 100 Hz.

The primary firmware is the CubeMX/HAL project in `CubeMX/`. The older
Keil-only ADC bring-up remains in this directory for reference.

## Current CubeMX wiring

| STM32F103C8T6 | Function |
| --- | --- |
| PB6 | MPU6050 SCL |
| PB7 | MPU6050 SDA |
| PB5 | MPU6050 INT |
| PA2 | ADC1_IN2, slot 0, legacy middle-finger channel |
| PA0 | ADC1_IN0, slot 1 |
| PA3 | ADC1_IN3, slot 2 |
| PA4 | ADC1_IN4, slot 3 |
| PA5 | ADC1_IN5, slot 4 |
| PA9 | USART1 TX to USB-TTL/Zynq RX |
| PA10 | USART1 RX from USB-TTL/Zynq TX |
| GND | Common ground |

Do not exceed 3.3 V on an ADC input.

## Build and flash

Open `CubeMX/MDK-ARM/strain_f103.uvprojx` in Keil MDK, rebuild, and download
through ST-LINK. CubeMX owns peripheral initialization; application code is
kept in the generated user-code sections and BSP directories.

## UART output

USART1 uses 115200-8-N-1 and sends the fixed 46-byte `IMUQ` v1 frame defined
in [`contracts/strain_uart.md`](../../../contracts/strain_uart.md). Each frame
contains status, sequence and timestamp, quaternion `[w,x,y,z]`, five raw ADC
slots, raw MPU temperature, and CRC-16/CCITT-FALSE.

The CubeMX ADC1 configuration performs a five-rank scan. Slot 0 remains PA2 for
compatibility with the original middle-finger channel; the other slots follow
the pin order above. Send ASCII `C` or `c` to start manual gyro calibration;
keep the board stationary until the calibrating flag clears and calibrated flag
is set.

## Layout

- `CubeMX/` - current STM32CubeMX/HAL project
- `Drivers/BSP/imu_filter/` - quaternion EKF implementation
- `tests/` - host-side checks for the filter and protocol
- `Drivers/`, `Users/`, `Projects/` - retained older Keil ADC bring-up

PA1 was measured as externally pulled to ground on the current test board and is
not used for ADC.
