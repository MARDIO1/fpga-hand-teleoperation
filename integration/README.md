# Board integration

## Current first-demo data path

The stereo matching vertical gate is currently an experimental 5 pixels (the
published v0.2.0 value was 2.5). The lab lighting thresholds are saved in
`modules/vision/data/thresholds_lab_experimental.json`. Static tests improved
yellow matching, but misses and false candidates remain; these settings need
further validation for motion, occlusion, and 3D accuracy.

### F103 USB CDC and individual finger calibration

The F103 USB CDC device is expected at `/dev/ttyACM0`; verify its actual name
after connecting it. It uses the same 46-byte IMUQ frames as UART. Stop any
other serial reader before calibration. Individually calibrate thumb, index,
middle and little finger, keeping the other fingers extended:

```bash
python3 modules/strain/software/ps/calibrate_strain.py --device /dev/ttyACM0
python3 integration/software/ps/board_stream.py --device /dev/ttyACM0 --strain-mode calibrated
```

The program shows all ADC slots and proposes the slot with the clearest change;
retry or choose a slot manually if necessary. It saves `finger_calibration.json`
on the board. The stream maps the calibrated slots into HAND v2 order (thumb,
index, middle, ring, little); ring copies normalized little-finger bend. Invalid
ADC conversion values hold the last bend. The default destination remains
`192.168.137.1:47000`; use `--host` and `--port` to change it. On the PC run
the existing MANO receiver. These changes do not require a PL rebuild. The
remaining sections include historical first-board information.

The first demo uses the standalone optimized stereo release in PL and its PS
software; the F103 provides the IMU quaternion and strain through USB UART.
No board-side MPU6050 IP or `hand_core` call is required for this path. The
older combined-overlay sections below describe earlier experiments, not the
selected first-demo deployment. A simultaneous board run is not yet verified.

The stereo publisher's `latest.json` contains frame-local matches in the
physical left camera optical frame, with XYZ in millimetres. `vision_latest.py`
converts XYZ to metres. The present wrist tracker requires a real calibration
file relating the wrist marker layout, IMU and camera coordinates; no such
file has been verified. Wrist and thumb yellow markers have the same colour.
F103 and camera timestamps are separate clocks; the demo uses the newest
samples without claiming exposure-level synchronization.

`board_stream.py` sends the existing HAND v2 datagram. Its acceleration and
angular-velocity fields are zero placeholders: IMUQ v1 does not contain those
measurements. A missing or stale camera position retains the last position and
clears its validity flag. The current protocol descriptions are
`contracts/strain_uart.md` and `contracts/hand_sensor_frame.md`; no wire format
changes are needed.

This area owns the combined ACZ7015 designs. `create_project.tcl` retains the
validated first-board IMU + hand-core image. `create_full_project.tcl` adds the
optimized stereo capture/marker/XYZ pipeline to the same top-level image; it does
not join prebuilt module bitstreams.

`modules/imu` supplies the independently tested MPU6050 IP. The current combined
bitstream exposes it at `0x43C10000` and `hand_core` at `0x43C00000`. Attitude
estimation and the hand-core call still run through PS software.

Module test bitstreams are never nested or linked here. The final Vivado build
consumes module IP and emits its own `.bit`, `.hwh` and `.xsa` under
`integration/vivado/full_output/`.

Prepare the frozen stereo IP, then create or build the full project:

```powershell
python modules\vision\vivado\optimized_xyz\prepare_release.py
vivado -mode batch -source integration\vivado\create_full_project.tcl
vivado -mode batch -source integration\vivado\create_full_project.tcl -tclargs build
```

Generated work stays in ignored `.vivado/full_board`,
`integration/vivado/full_output`, and `integration/vivado/full_reports`
directories. The short work path avoids Windows' 260-character limit inside the
floating-point geometry IP. The full address map preserves the
standalone module addresses: `hand_core` at `0x43C00000`, MPU6050 at
`0x43C10000`, and the stereo blocks at their optimized-v0.2.0 addresses. The
full image also exposes the raw camera 1/2 VSYNC counters through a dual AXI
GPIO at `0x41210000`; this small persistent diagnostic distinguishes a stopped
sensor from a downstream stereo or VDMA stall.

## First-board bring-up

The current one-IMU/one-strain version uses the combined first-board overlay.
After copying the repository to the board, run the bounded interface smoke test:

```bash
sudo python3 integration/software/ps/smoke_board.py
```

Use `--reuse-overlay` for later checks so restarting software does not reconfigure
PL. The three sensor classes are calibrated separately.

1. Strain: record the repeatable open / half-bent / closed poses:

```bash
python3 modules/strain/software/ps/calibrate_strain.py --channels 0
```

2. IMU: calibration runs on the F103 only when explicitly requested. Keep the
glove still and run the streamer once with `--calibrate-imu`; later starts reuse
that state while the F103 remains powered and do not initiate calibration automatically.

3. Vision: temporarily place one yellow ball at the defined wrist centre. Start
in the standard pose, then slowly turn the wrist so both cuff faces pass through
the stereo view. Each usable frame transforms its visible cuff balls back to the
local wrist frame using the simultaneous IMU attitude and yellow centre. Samples
are clustered into the complete ring template (red 1, green 1, blue 5), so all
seven balls do not need to be visible in one frame. Remove the yellow ball after
writing `wrist_ring_calibration.json`. This capture needs live stereo data; do not
substitute guessed marker offsets.

Then start the SSH-run streamer:

```bash
sudo python3 integration/software/ps/board_stream.py
```

To request manual F103 gyro calibration, keep the sensor stationary and run:

```bash
sudo python3 integration/software/ps/board_stream.py --calibrate-imu
```

If no calibration file exists, the default `auto` mode enters an explicit preview:
the first sample is the zero point and the absolute change drives bend over a
600-count span. Use `--strain-mode calibrated` to require a completed calibration,
or `--strain-mode preview --preview-span 600` to force the uncalibrated display.

The PS reads the 46-byte `IMUQ` stream from `/dev/ttyUSB0`, checks its CRC and
status, maps the calibrated bend channels, and forwards the F103 quaternion in
`HAND v2` to `192.168.137.1:47000` at 100 Hz. It does not run a second attitude
filter. Streaming starts after the MCU reports present, valid, and calibrated.
The current firmware transmits five ADC slots in the order PA2, PA0, PA3, PA4,
PA5. Slot 0 remains the legacy middle-finger channel; the other slots are raw
inputs until the fitted glove is assigned to finger indices and calibrated.

For the full image, run the optimized stereo publisher first. It atomically writes
`/dev/shm/marker_results_v2/latest.json`. The hand streamer consumes its newest
valid sample without blocking the 100 Hz IMU/strain loop. A calibrated seven-point
wrist-ring model is mandatory; raw marker centroids are not wrist positions:

```bash
sudo python3 integration/software/ps/board_stream.py \
  --vision-json /dev/shm/marker_results_v2/latest.json \
  --wrist-calibration modules/vision/data/wrist_ring_calibration.json
```

The model stores every ball's colour and sensor-frame offset from the wrist
centre. IMU orientation reduces each frame to a small colour-compatible assignment
problem; repeated blue balls are selected by geometric residual and temporal
continuity. Two or more visible balls are sufficient, a uniquely identified
single ball may continue tracking, and an unresolved lone blue ball is rejected.
A sample older than `--vision-max-age` is invalid and the last position is held.
Camera frames remain asynchronous (about 20--30 Hz); HAND packets use the newest
absolute optical-frame wrist position and the current IMU timestamp. MANO and
robot displays may establish their own initial origin. This software path requires
the full bitstream: loading the standalone stereo bitstream would remove MPU6050
and `hand_core` from PL.

## Current hardware status

- F103 + CH340 alone: 100.00 Hz for 500 frames, no CRC or sequence errors.
- MPU6050 overlay alone: I2C errors 0, dropped samples 0, about 500 pose updates/s.
- Controlled retest: UART passed at 100.00 Hz before the MPU overlay. One overlay
  load left UART healthy and did not increase the 171-message `error -71`
  baseline; a later redundant reload increased the count and left
  `/dev/ttyUSB0` present but unable to return a valid strain frame.
- The onboard RTL8188FTV is soldered to CH334H port 4 and is not a removable
  dongle. H5/H6 are GPIO0 I2C pins; the USB host uses PS MIO/ULPI, so no direct
  FPGA-pin conflict has been found.
- After a full power cycle, one overlay load followed by a `--reuse-overlay`
  restart completed the hardware path: the PC received 486 HAND v2 packets with
  0 dropped and 0 rejected, the USB `error -71` count remained 0, and a final
  standalone UART check received 200 frames at 100.00 Hz with 0 rejected.
- Software `HAND v2` end to end: 240/240 packets received, 0 dropped, 0 rejected,
  and the received pose was rendered by MANO.
- Combined `first_board.bit`: `hand_core` AXI transaction passed; MPU returned
  1206 samples in 3 seconds with 0 I2C errors; UART returned 299 frames with 0
  rejects; the PC received 1300 consecutive UDP packets with 0 drops or rejects.
  USB `error -71` remained at 0 after the single PL load.

The first-board hardware path is accepted with the controlled startup above. The
earlier failure was below the UART decoder, at the Hub/full-speed USB transaction
layer, and appeared during some PL reconfigurations rather than steady-state
computation. Its electrical cause is not yet proven. Do not try to remove the
onboard Wi-Fi device and do not automatically reset the whole Hub; load the
overlay once after a power cycle and use `--reuse-overlay` for streamer restarts.

![First-board hardware pose](../simulation/virtual_hand/results/first_board_hardware.png)
