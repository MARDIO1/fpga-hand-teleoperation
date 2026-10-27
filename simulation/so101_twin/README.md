# SO-101 digital twin

This is an independent optional demonstration. It does not import or modify the
MANO viewer or its UDP receiver. Both demos permanently share the Python project
and environment in `..\virtual_hand`; only their application code is separate.

The arm model is `robotstudio_so101` from MuJoCo Menagerie. Mink tracks camera
XYZ and the IMU-derived gripper direction while enforcing joint, velocity,
self-collision and table-collision limits. The middle flex channel controls the
gripper with a 5% dead zone.

```powershell
uv sync --project ..\virtual_hand
uv run --project ..\virtual_hand python so101_twin.py
uv run --project ..\virtual_hand python so101_twin.py --sequence ..\virtual_hand\.runtime\demo_sequence.npz
uv run --project ..\virtual_hand python so101_twin.py --udp --port 47000
uv run --project ..\virtual_hand python so101_twin.py --udp --headless --seconds 5
uv run --project ..\virtual_hand python -m unittest -v test_so101_twin.py
```

The MANO receiver and this program both default to UDP port 47000. Run only one
live receiver at a time, or give the SO-101 demo another port with `--port`.

## Calibration, recording and replay

Mirror the live stream to both viewers and the tools port:

```powershell
uv run --project ..\virtual_hand python udp_relay.py --targets 47001 47002 47003
```

The guided calibrator prompts for neutral, positive roll, positive pitch and
positive yaw poses. Hold each requested pose before pressing Enter:

```powershell
uv run --project ..\virtual_hand python calibrate_orientation.py
```

Record lossless HAND v2 packets, then replay them through the GUI player. Stop
the live relay before playback so live and recorded sequence numbers do not mix.

```powershell
uv run --project ..\virtual_hand python record_action.py recordings\demo.npz --seconds 10
uv run --project ..\virtual_hand python play_action.py recordings\demo.npz
```

The player supports pause, seeking, looping and 0.25x to 2x speed, and sends the
same replay frames to MANO on 47001 and SO-101 on 47002.

Validate IMU drift with the hand resting on a stable surface. The default test is
420 seconds and passes when absolute yaw stays within one degree:

```powershell
uv run --project ..\virtual_hand python validate_imu.py --mode static
```

For the short one-turn closure test, return the hand to exactly the starting pose
before the configured capture time expires. The pass limit is two degrees:

```powershell
uv run --project ..\virtual_hand python validate_imu.py --mode circle --seconds 10
```

Both commands save every quaternion, acceleration and angular-rate sample to
`.runtime/imu_validation.csv`. They use relay target port 47003 by default.

The first valid camera and IMU sample becomes the relative origin. Position is
mapped 1:1 by default; use `--position-scale` to change it. Relative IMU yaw
explicitly moves the target around the robot base on a horizontal arc (1:1 gain,
no angular dead zone, 180 degree target limit), while pitch and roll shape the gripper
orientation. A green marker shows the requested target. `reach_limited=True`
means joint or collision constraints prevented close tracking; the arm remains
at the nearest continuously reached boundary instead of jumping to another IK
branch.

