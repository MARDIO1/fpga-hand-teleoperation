# Strain module

Owner workspace for five-channel strain acquisition and preprocessing.

- `rtl/`, `hls/`: implementation sources
- `sim/`, `tests/`: module simulation and regression
- `data/samples/`: small deterministic inputs
- `vivado/`: standalone ACZ7015 test design and rebuild scripts
- `export/ip/`: packaged IP releases
- `export/bitstream/`: standalone module test bitstreams
- `mcu/`: STM32F103 ADC/UART acquisition firmware
- `software/ps/strain_uart.py`: board-side STRN decoder and calibration mapper
- `software/ps/read_strain.py`: short UART rate and raw-value smoke test
- `software/ps/calibrate_strain.py`: repeatable open/half/fist calibration tool

On the board, recalibrate the connected middle-finger channel with:

```bash
python3 modules/strain/software/ps/calibrate_strain.py --channels 2
```

The command records 200 samples per pose and replaces the local
`modules/strain/data/strain_calibration.json`. Calibration data is specific to
the fitted glove and is intentionally not committed.

If `/dev/ttyUSB0` exists but the CH341 driver is stuck, restart only its interface:

```bash
sudo sh -c 'echo 1-1.1:1.0 > /sys/bus/usb/drivers/ch341/unbind; sleep 1; echo 1-1.1:1.0 > /sys/bus/usb/drivers/ch341/bind'
```

This cannot recover a Hub-level `error -71`; in that case even device reset
commands cannot reach the CH340.
