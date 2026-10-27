"""Check standalone use without the old workspace or live SSH dependencies."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

PC = Path(__file__).resolve().parents[1] / "software/pc"
sys.path.insert(0, str(PC))
from rgb565 import load_rgb565, rgb565_bgr


class EntryPointTests(unittest.TestCase):
    def test_rgb565_color_order_and_truncated_input(self):
        colors = np.array([[0xF800, 0x07E0, 0x001F]], dtype="<u2")
        self.assertEqual(rgb565_bgr(colors).tolist(),
                         [[[0, 0, 248], [0, 252, 0], [248, 0, 0]]])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.rgb565"
            path.write_bytes(b"\x00\x00")
            with self.assertRaisesRegex(ValueError, "1280x720"):
                load_rgb565(path)

    def test_offline_cli_from_other_directory_without_paramiko(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "frame.rgb565", root / "output"
            frame = np.zeros((720, 1280), dtype="<u2")
            frame[100:120, 100:120] = 0xF800
            frame[200:220, 800:820] = 0xF800
            frame.tofile(source)
            # Block the optional SSH dependency to verify offline isolation.
            code = (
                "import sys,runpy; sys.modules['paramiko']=None; "
                "sys.path.insert(0,sys.argv.pop(1)); "
                "script=sys.argv.pop(1); sys.argv[0]=script; "
                "runpy.run_path(script,run_name='__main__')"
            )
            result = subprocess.run(
                [sys.executable, "-c", code, str(PC), str(PC / "preview_glove_pc.py"),
                 "--input", str(source), "--headless", "--output", str(output)],
                cwd=root, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            metadata = json.loads((output / "latest.json").read_text())
            self.assertEqual(metadata["identity_status"], "frame_local_candidates_only")
            self.assertIsNone(metadata["calibration"])
            self.assertIsNone(metadata["source_frame_id"])
            self.assertIsNone(metadata["exposure_timestamp"])
            self.assertEqual(metadata["candidates"]["R"][0]["u"], 109.5)
            self.assertEqual(metadata["candidates"]["L"][0]["u"], 169.5)
            self.assertEqual((output / "latest.rgb565").read_bytes(), source.read_bytes())
            self.assertTrue((output / "latest_preview.png").is_file())

    def test_missing_live_host_is_rejected_before_connection(self):
        result = subprocess.run(
            [sys.executable, str(PC / "preview_glove_pc.py"), "--headless", "--frames", "1"],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Live snapshots require --host", result.stderr)


if __name__ == "__main__":
    unittest.main()
