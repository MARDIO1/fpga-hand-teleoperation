# PC color-marker prototype

This tool segments red, yellow, green and blue independently for each eye using
HSV thresholds, component pixel area and image-border checks. It deliberately
does not impose roundness, aspect ratio or morphology filters. Blue stripes can
therefore remain candidates or merge with a blue marker.

## Offline use

From the repository root:

```sh
python -m pip install -r modules/vision/software/pc/requirements.txt
python modules/vision/software/pc/preview_glove_pc.py --input path/to/frame.png
python modules/vision/software/pc/preview_glove_pc.py --input path/to/frame.rgb565 --headless
```

Input must be an unannotated 1280 x 720 stereo image or little-endian RGB565 file
(1,843,200 bytes). The first 640 columns are physical right-eye data; the last
640 are physical left-eye data. The preview displays left eye first. Candidate
`u`, `v` coordinates are local to each 640 x 720 eye, with origin at the upper
left, u increasing rightward and v downward, in pixels.

The window supports S to save a sample, T to save thresholds and Q/Esc to exit.
Select the eye and color before changing HSV controls. H ranges from 0 to 179;
S/V range from 0 to 255. A hue minimum greater than its maximum wraps through 0.
Threshold saves go into the output directory and do not overwrite the bundled
config. Reuse them with `--thresholds path/to/thresholds.json`.

## Live read-only preview

This migration supplies no overlay or board startup program. Live preview requires
an already running, compatible stereo capture pipeline with its single frame at
physical address `0x1E000000`. Do not run it against a different overlay, buffer
layout or the HDMI-only static test. It does not discover buffers or load hardware.

First verify and register the board's SSH host key using your normal SSH client.
Unknown or changed host keys are rejected. Then run:

```sh
python modules/vision/software/pc/preview_glove_pc.py --host BOARD_ADDRESS --user xilinx
python modules/vision/software/pc/preview_glove_pc.py --host BOARD_ADDRESS --ssh-key path/to/key --sudo-nopasswd --headless --frames 12
```

Passwords are prompted without echo. For noninteractive runs, supply
`VISION_SSH_PASSWORD` and `VISION_SUDO_PASSWORD` through your environment; do not
commit their values. `--sudo-nopasswd` uses existing passwordless sudo and does
not change board permissions. The remote reader needs access to `/dev/mem`.

Default request rate is 2 snapshots/s; `--fps` accepts values greater than 0 and
at most 10. This is not camera FPS or a verified point-output rate. Headless live
runs require a finite `--frames` count. `--output` changes the save directory.

## Output meaning

Saved files contain the original `.rgb565`, decoded `_raw.png`, annotated
`_preview.png` and candidate `.json`. JSON includes per-eye candidates, thresholds,
PC detection time and available read timing. `latest.*` is overwritten periodically;
finite headless live runs also save numbered frames.

`snapshot_sequence` is a reader counter, not a camera frame ID. Board read start/end
times are monotonic memory-read intervals, not exposure timestamps. A snapshot may
tear while capture overwrites DDR. Offline files also retain unverified consistency.
`calibration`, `source_frame_id` and `exposure_timestamp` remain null. Candidate
labels are not persistent marker IDs, and no XYZ, stereo correspondence or
cross-frame tracking is produced. This JSON is not the shared MarkerFrame contract.

The bundled thresholds reflect one experimental camera/lighting setup. Retune them
before evaluating new cameras or illumination. Synthetic test success is not a
real-glove detection accuracy or hardware performance measurement.
