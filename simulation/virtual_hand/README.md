# Virtual hand simulation

The active backend is a 45-DoF MANO human hand in MuJoCo. It consumes camera
wrist XYZ, one dorsal-IMU quaternion and five normalized bends; it does not use IK.

## Setup

MANO is licensed separately and must not be committed. Prepare the ignored local runtime from the official archive:

```powershell
uv sync --group mano-build
uv run --group mano-build python prepare_mano_runtime.py "T:\Project\9.22 look_grap\PC_part_2\mano_v1_2.zip"
```

The setup script checks out the pinned DexHOI2Sim revision, converts legacy Chumpy arrays, and generates the local URDF and link meshes under `.runtime/`.

## Run

Validate all static poses, all 51 MuJoCo controls, five independent finger motions,
and a 240-frame canonical `.npz` action sequence:

```powershell
uv run python mano_controller.py --headless --frames 240
```

Open the interactive MuJoCo viewer with continuous programmed motion:

```powershell
uv run python mano_controller.py
```

Receive the first-board live stream (middle-finger strain plus dorsal IMU):

```powershell
uv run python live_hand_receiver.py --middle-span 600
```

The receiver listens on UDP port 47000 and reuses the 84-byte `HAND v2` sensor
packet. If `--middle-open` is omitted, the first packet is captured as the open
value. Use a negative `--middle-span` when the raw value decreases during flexion.
The first valid IMU quaternion is the display reference orientation. Missing UDP
packets hold the last pose; duplicate and out-of-order sequences are rejected.

Replay another sequence with `--sequence path/to/sequence.npz`. The arrays are
`timestamp_us`, `camera_valid`, `wrist_xyz`, `wrist_quaternion_wxyz`, `flex_raw`,
`linear_acceleration`, and `angular_velocity`; all sample arrays share the first dimension.

`hand_sequence.py` owns this format. Missing 20 Hz camera updates hold the last
position; IMU acceleration is recorded for diagnosis but is not integrated.
`mano_mapping.py` infers finger spread from bend, including thumb opposition, then
outputs six wrist controls plus 45 MANO joint controls.

Fit the five raw strain channels from recorded open, half-fist and fist samples:

```powershell
uv run python strain_calibration.py calibration_samples.npz --output strain_calibration.json
```

The previous Shadow Hand program remains as a reference and FPGA reconstruction test. It is not the active human-hand display backend.
