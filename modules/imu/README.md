# MPU6050 IMU prototype

Standalone ACZ7015 module migrated from the board-tested `mpu6050_studio` workspace.
It acquires original acceleration, angular rate and temperature over I2C, timestamps
the acquisition in PL, estimates attitude using floating-point Mahony on the ARM,
then writes the complete original-sample-plus-attitude frame back to the IP.

The [ImuFrame contract](../../contracts/imu_frame.md) defines the fixed 64-byte,
32-bit AXI4-Stream output: original six-axis int16 samples, temperature, float32
yaw/pitch/roll, 64-bit microsecond timestamp, sequence and status. Original values
and attitude always belong to the same captured sample. This IP does not compute
attitude without the ARM program.

## Ownership

| Directory | Content |
| --- | --- |
| `rtl/` | Open-drain I2C, initialization/readback, acquisition and AXI/AXIS packet interface |
| `software/ps/` | Calibration, Mahony, capture/replay, hardware probe and diagnostic utilities |
| `software/pc/` | Live SSH JSONL viewer and local recording |
| `sim/`, `tests/` | Bus/packet simulation and deterministic software tests |
| `data/samples/` | Synthetic sample policy; raw captures remain ignored |
| `vivado/` | Standalone test build and IP packaging scripts |
| `export/ip/v0.1.0/` | Packaged IP release from these sources |
| `export/bitstream/acz7015/v0.1.0/` | Standalone test bit/HWH and source/artifact checksums |

## Wiring

| MPU6050 | ACZ7015 GPIO0/P7 |
| --- | --- |
| SCL | FPGA ball H5, GPIO0[8] |
| SDA | FPGA ball H6, GPIO0[9] |
| VCC / GND | 3.3 V / GND |
| AD0 | GND, 7-bit address 0x68 |

H5/H6 are FPGA ball names; use the board schematic for header positions. Both
signals need pull-ups to 3.3 V, typically 2.2k–4.7k (check existing module pull-ups).
The 400 kHz upper-limit parameter also enforces minimum low and START-hold times;
the current 100 MHz controller operates at about 308 kHz. Configuration is 500 Hz,
DLPF=2, +/-4 g (8192 LSB/g), +/-500 deg/s (65.5 LSB/deg/s).

The tested module retained SLEEP=1 on the first wake write after reset. The driver
waits, repeats the wake write and verifies PWR_MGMT_1=0x01 before proceeding.

## Validate and build

From the repository root, with Python 3 and Vivado 2025.2:

```powershell
python -m unittest discover -s modules/imu/tests -v
./modules/imu/sim/run.ps1
vivado -mode batch -source modules/imu/vivado/package_ip.tcl
vivado -mode batch -source modules/imu/vivado/create_project.tcl -tclargs build
```

`run.ps1 -VivadoBin PATH` selects a different Vivado installation. Generated
projects, simulation output and reports stay ignored. Builds target
`xc7z015clg485-2` and write bit/HWH to `vivado/output/`; packaging writes
`vivado/output/ip/` with VLNV `local.fpga:sensor:mpu6050_imu:1.0`. Exported releases
are snapshots, not automatically overwritten by rebuilds.

Optional reference validation uses `ahrs==0.4.0` and NumPy on a PC:

```sh
python modules/imu/tests/verify_reference.py
```

## Board operation

Needs the existing ACZ7015 Linux/PYNQ installation, Python 3.6+ and root access.
Loading this standalone overlay replaces the current PL configuration, including
any running stereo/HDMI overlay. Stop the other owner before loading it.

From a checkout on the board:

```sh
sudo python3 modules/imu/software/ps/probe_board.py
sudo python3 modules/imu/software/ps/run_mpu6050.py \
  --bitstream modules/imu/export/bitstream/acz7015/v0.1.0/mpu6050.bit \
  --output /tmp/imu_pose.jsonl
```

Alternatively copy the bit/HWH pair and `software/ps/*.py` into one board folder,
then use `--bitstream mpu6050.bit`. The tested deployment folder was
`/home/xilinx/overlays/mpu6050_studio`; `start_live.sh` starts a one-hour capture
against an already loaded overlay, and `stop_live.sh` stops that capture.

Hold the module stationary for 1000 consecutive samples (about two seconds).
Calibration uses online Welford statistics to avoid a final-frame processing
spike. The raw sample remains available in PL while attitude calibration waits.
After calibration, move the module to observe Euler angles and raw samples.

## PC operation

Install `software/pc/requirements.txt`; Tkinter is also required. Register and
verify the board SSH host key using your normal SSH client first. Unknown/changed
keys are rejected. The password is prompted without echo or supplied through
`MPU_SSH_PASSWORD`; no password is embedded in this module.

```sh
python -m pip install -r modules/imu/software/pc/requirements.txt
python modules/imu/software/pc/view_live.py --host BOARD_ADDRESS \
  --remote /tmp/imu_pose.jsonl
```

The current viewer reads a board JSONL file over SSH, displays at 10 Hz and saves
received complete frames to ignored `data/raw/pc_pose.jsonl`. It is a usable
prototype with known buffering/continuity limitations, not the future direct
continuous network feed. See [status and measurements](docs/status.md).

The module is not connected to fusion or the combined overlay. Do not link its
standalone bitstream into another design. Integration must consume packaged IP,
provide ARM attitude writeback and align the timestamp to a common timebase.
