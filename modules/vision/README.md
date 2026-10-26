# Vision module

Owner workspace for stereo capture, preprocessing and marker reconstruction. Migrate selected sources here; do not copy the old repository history or generated Vivado state.

- `rtl/`, `hls/`: implementation sources
- `sim/`, `tests/`: module simulation and regression
- `data/samples/`: small deterministic inputs
- `vivado/`: standalone ACZ7015 test design and rebuild scripts
- `export/ip/`: packaged IP releases
- `export/bitstream/`: standalone module test bitstreams

## Selected board version

The final adopted version is [compact XYZ v0.1.0](vivado/compact_xyz/README.md),
compiled and board-tested on 2026-10-26: PL color recognition and geometry, PS
pairing, PC preview. Matching bit/HWH, HLS IP, calibration and validation evidence
are published under export/. XYZ is experimental millimetres; the shared
MarkerFrame/fusion adapter is not implemented.

## Historical migrated baseline (2026-10-25)

Selected sources were migrated from the local `vision_studio` workspace on
2026-10-25: the PC color-marker prototype, experimental capture/preprocessing/SAD
RTL, standalone build scripts and one historical static HDMI test release.
Old Git history, generated build directories and raw captures are not imported.

The prototype outputs per-eye **2D candidates**, not calibrated XYZ or the shared
[`MarkerFrame v0.1`](../../contracts/marker_frame.md). Candidate labels are local
to one frame. No fusion or integration interface is connected by this migration.

| Stage in the existing hardware experiments | Geometry |
| --- | --- |
| OV5640 acquisition | 640 x 720 RGB565 per eye |
| Combined raw frame | 1280 x 720; physical right eye first, left eye second |
| Experimental depth processing | 160 x 180 per eye; RTL included, not XYZ validated |
| HDMI test output | 1280 x 720; static reference exported |

See [PC usage](software/pc/README.md), [current limitations](docs/status.md),
[dependency list](docs/dependencies.md) and [migration provenance](docs/migration.md).
Hardware build and simulation commands are in [vivado/README.md](vivado/README.md).
The exported [HDMI baseline](export/bitstream/acz7015/hdmi-baseline-v0.1.0/README.md)
is an observed static reference, not a completed real-time stereo repair.

From the repository root, using Python 3.10 or newer:

```sh
python -m pip install -r modules/vision/software/pc/requirements.txt
python -m unittest discover -s modules/vision/tests -v
```

Raw preview output defaults to `modules/vision/data/raw/glove_preview/`, which is
ignored by the repository. No real captures or calibration parameters ship with
this prototype.
