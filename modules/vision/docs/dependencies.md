# Dependencies

| Dependency | Purpose | Required for |
| --- | --- | --- |
| Python >= 3.10 | PC tools and standard-library unittest | All migrated code |
| NumPy | RGB565 decoding and arrays | Detection and tests |
| OpenCV Python with GUI support | HSV, components, images and trackbars | Detection; GUI for interactive preview |
| Paramiko | SSH snapshots | Live preview only; imported lazily |
| Existing stereo overlay and Linux Python 3 | Fixed-address read-only `/dev/mem` snapshots | Live preview only, not supplied here |

Install ranges are recorded in `../software/pc/requirements.txt`. They are not a
lockfile or a claim that every version in each range was tested. Offline processing
does not import PYNQ, use SSH, require root or depend on the old project directory.

The PC prototype does not depend on Vivado or vendor RTL. Hardware sources are now
included separately: Vivado 2025.2 with the Zynq-7000 device support generates AMD
IP from Tcl/XCI inputs. PowerShell and Vivado XSim run the RTL regressions. No HLS
build is needed for these RTL variants. Board software additionally requires the
legacy PYNQ video interface and prepared ACZ7015 Linux environment described in
`../software/ps/README.md`. See `third_party.md` for vendor attribution and unresolved
public redistribution permission.
