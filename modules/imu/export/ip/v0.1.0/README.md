# MPU6050 IP v0.1.0

VLNV: `local.fpga:sensor:mpu6050_imu:1.0`. Rebuilt with Vivado 2025.2 from this module. Add this directory as an IP repository; apply `vivado/mpu6050.xdc` in the owning board design. AXI-Lite configuration and ARM attitude writeback are required for the full AXIS packet. This package does not itself implement the ARM estimator. See the module README and shared ImuFrame contract.
