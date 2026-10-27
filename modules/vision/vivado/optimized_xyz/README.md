# Optimized XYZ v0.2.0 ¡ª 2026-10-27

Selected ACZ7015 standalone vision release. The board-tested complete point-output
rate is **29.564 FPS**; asynchronous same-frame preview capped at 2 Hz gives
**28.620 FPS**, measured over 600 frames per mode from consecutive completion
timestamps after three warm-up frames. These are observed scene-dependent rates.

PL uses leased DDR capture, a FIFO reader, II=1 color scanning and the original
float64 geometry core. PS uses native C++ stereo matching and a bounded publisher
process. Three reserved frame slots prevent preview copies from being overwritten.
Coordinates remain experimental millimetres in the physical left optical frame;
IDs are frame-local. The shared MarkerFrame/fusion contract is not implemented.

## Verify and run

From the repository root, Python 3.10+ with NumPy:

```sh
python modules/vision/vivado/optimized_xyz/prepare_release.py
python -m unittest discover -s modules/vision/vivado/optimized_xyz/tests -v
python -m unittest discover -s modules/vision/vivado/optimized_xyz/software/hls_markers -p 'test_*.py' -v
```

The verifier checks every frozen published file, then unpacks matching IP for
rebuilds. Copy `software/` and the matching
`export/bitstream/acz7015/optimized-xyz-v0.2.0/pl_stereo_compact_optimized.bit`
and `.hwh` to the board, retaining the software directory layout. The target
PYNQ image needs NumPy and the existing 16 MiB no-map reserved DDR region starting
at 0x1e000000. Compile the matcher on the board:

```sh
cd software/hls_markers
g++ -std=c++11 -O2 marker_match.cpp test_marker_match.cpp -o test_marker_match
./test_marker_match
g++ -std=c++11 -O2 -shared -fPIC marker_match.cpp -o libmarker_match.so
cd ../..
```

Stop the previous capture owner and quiesce its DMA before loading the matching
bit/HWH with the board's overlay loader. This release intentionally has no automatic
deployment entry. On the tested image the actual PS reference clock is 33.333 MHz;
use `Clocks.set_pl_clk(0, div0=5, div1=2)` for the verified 100 MHz PL clock rather
than relying on the legacy runtime's 50 MHz reference assumption. Run only one
capture owner, from the bundle root:

```sh
sudo python3 software/marker_ingress_v2/run_direct_board.py --frames 0 --fps 0 --snapshot-fps 0
# For asynchronous preview, use --snapshot-fps 2 instead.
```

Results are `/dev/shm/marker_results_v2/latest.json` and `latest.bin`. The existing
compact release PC snapshot decoder can read this format; configure its remote
path to this V2 directory. `--fps 0` disables the software ceiling.

## Rebuild and provenance

Vivado/Vitis HLS 2025.2, xc7z015clg485-2, 100 MHz. After preparation:

```sh
vivado -mode batch -source modules/vision/vivado/optimized_xyz/build_optimized.tcl
```

Set `VISION_OPTIMIZED_PROJECT` to an unused short project path on Windows if needed.
Builds write to ignored output directories. Packaged HLS IP is frozen under
`export/ip/optimized-xyz-v0.2.0`; changed color C++ and its testbench are under
`hls/optimized_xyz`. Geometry source and deterministic fixtures are retained in
the previous compact release. No HLS mathematics or external packet contract was
changed. INGRESS_HISTORY.md preserves historical control development notes;
the current software and measured report supersede its predeployment guidance.

See [measured board report](../../export/bitstream/acz7015/optimized-xyz-v0.2.0/OPTIMIZATION_REPORT.md),
final per-frame timing records, ownership/smoke summaries, resource and timing
reports in that release directory. Raw captures, temporary reports and generated
Vivado projects are excluded. Local migration checks do not rerun FPGA synthesis
or board tests. Camera timing coverage, exposure synchronization, absolute 3D
accuracy, long-term operation and dense-scene worst-case throughput remain unverified.
