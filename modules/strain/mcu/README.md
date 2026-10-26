# STM32 strain acquisition node (ADC + UART)

STM32F103C8T6 firmware for analog voltage acquisition and serial readout, used as the
MCU-side acquisition path for the strain module.

- MCU: STM32F103C8T6, 72 MHz (HSE + PLL x9)
- ADC: ADC1_IN2 on PA2, 12-bit, 239.5-cycle sampling time, polling mode (HAL)
- UART: USART1, PA9 (TX) / PA10 (RX), 115200-8-N-1, `printf` retargeted to USART1
- IDE: Keil MDK-ARM (ArmCC V5.06, C99, MicroLIB)

## Wiring

| STM32F103C8T6 | Connect to |
| --- | --- |
| PA2 (ADC1_IN2) | Analog input, 0 .. 3.3 V |
| PA9 (USART1_TX) | USB-TTL RX |
| PA10 (USART1_RX) | USB-TTL TX |
| GND | USB-TTL GND (common ground) |

Do not exceed 3.3 V on the ADC input.

## Build and flash

1. Open `Projects/MDK-ARM/START0.uvprojx` in Keil MDK.
2. Rebuild the project.
3. Download to the board.

## Output

Every 500 ms the firmware prints one line at 115200 baud:

```
ADC=4095  Voltage=3.300 V
```

The raw value is the 12-bit ADC result; voltage is `raw * 3300 / 4095` in mV.

## Layout

- `Drivers/BSP/adc.dma/` - ADC driver (`adc_init`, `HAL_ADC_MspInit`)
- `Drivers/SYSTEM/` - clock, delay and USART1 helpers
- `Users/main.c` - initialization and the sampling/print loop
- `Projects/MDK-ARM/` - Keil project

## Notes

On the current test board PA1 (ADC1_IN1) was measured as externally pulled to ground,
so this firmware samples PA2 (ADC1_IN2) instead.
