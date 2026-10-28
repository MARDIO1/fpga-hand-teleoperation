"""Preload the V2 driver, load the combined overlay, then capture five frames."""

from pathlib import Path
import sys


VISION = Path("/home/xilinx/overlays/pl_stereo_hdmi/compact_optimized_20261027")
OVERLAY = Path(__file__).resolve().with_name("full_board.bit")
sys.path[:0] = [str(VISION / "software" / "marker_ingress_v2"),
                str(VISION / "software" / "hls_markers"),
                str(VISION / "software" / "hls_geometry"),
                str(VISION / "software")]


def main():
    import run_direct_board
    from calibrated_hardware import CalibratedHardwareMatcher  # preload ctypes
    from pynq import Clocks, Overlay

    Overlay(str(OVERLAY))
    Clocks.set_pl_clk(0, div0=5, div1=2)
    print("immediate_fclk0_mhz={:.3f}".format(Clocks.fclk0_mhz), flush=True)
    sys.argv = ["run_direct_board.py", "--frames", "5", "--fps", "0",
                "--snapshot-fps", "1",
                "--output", "/dev/shm/marker_results_diag"]
    run_direct_board.main()


if __name__ == "__main__":
    main()
