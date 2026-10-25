# Source provenance

Migrated at the workspace owner's request from the locally authored
`mpu6050_studio` prototype. No camera vendor source, virtual environments, board
credentials, raw captures or unfinished direct-stream implementation is included.

- `Haseeb718/mpu6050-fpga-i2c` was reviewed for the FPGA I2C approach. Its source was
  not copied; this module implements its own burst acquisition and error handling.
- `Mayitzin/ahrs` (MIT) is an optional external validation reference. No AHRS source
  or installed package is vendored; the ARM runtime uses standard Python math.
- `WangXuan95/FPGA-FixedPoint` (GPL-3.0) was considered for future PL arithmetic but
  was not imported or used. Current attitude processing remains floating-point.
- Register definitions follow the TDK/InvenSense MPU-6000/MPU-6050 register map.
- PC live access uses separately installed Paramiko, consistently with the vision
  PC tool. No library copy or stored password is committed.
- Packaged-IP metadata/XGUI and bit/HWH are generated with AMD Vivado 2025.2.
  Existing generated copyright notices are retained; no new blanket license is
  asserted over AMD tools or primitives.

References:

- https://github.com/Haseeb718/mpu6050-fpga-i2c
- https://github.com/Mayitzin/ahrs
- https://ahrs.readthedocs.io/en/latest/filters/mahony.html
- https://github.com/WangXuan95/FPGA-FixedPoint
- https://invensense.tdk.com/wp-content/uploads/2015/02/MPU-6000-Register-Map1.pdf
