"""Offline checks of imported artifacts and their selected rebuild inputs."""
import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

MODULE = Path(__file__).resolve().parents[1]
RELEASE = MODULE / "export/bitstream/acz7015/hdmi-baseline-v0.1.0"


class HardwareReleaseTests(unittest.TestCase):
    def test_artifacts_and_rebuild_inputs_match_manifest(self):
        info = json.loads((RELEASE / "build_info.json").read_text())
        self.assertFalse(info["provenance"]["bit_identical_rebuild_claimed"])
        for name, expected in info["files"].items():
            with self.subTest(artifact=name):
                self.assertEqual(hashlib.sha256((RELEASE / name).read_bytes()).hexdigest(), expected)
        for name, expected in info["rebuild_source_sha256"].items():
            with self.subTest(source=name):
                self.assertEqual(hashlib.sha256((MODULE / name).read_bytes()).hexdigest(), expected)

    def test_release_is_static_pre_monitor_hardware(self):
        root = ET.parse(RELEASE / "pl_hdmi_official_baseline.hwh").getroot()
        modules = {m.get("INSTANCE"): m for m in root.findall(".//MODULE")}
        self.assertIn("video_status", modules)
        self.assertNotIn("camera", modules)
        self.assertNotIn("native_probe", modules)
        params = {p.get("NAME"): p.get("VALUE") for p in
                  modules["display_vdma"].findall("./PARAMETERS/PARAMETER")}
        for name, value in {"C_NUM_FSTORES": "1", "C_INCLUDE_S2MM": "0",
                            "C_MM2S_GENLOCK_MODE": "3",
                            "C_MM2S_LINEBUFFER_DEPTH": "1024"}.items():
            self.assertEqual(params[name], value)
        ranges = {r.get("INSTANCE"): int(r.get("BASEVALUE"), 16)
                  for r in root.findall(".//MEMRANGE") if r.get("BASEVALUE")}
        for name, address in {"display_vdma": 0x43000000, "dynclk": 0x43C00000,
                              "vtc": 0x43C10000, "video_status": 0x41200000}.items():
            self.assertEqual(ranges[name], address)

    def test_packaged_display_ip_file_references_exist(self):
        ns = {"s": "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"}
        for component in (MODULE / "vivado/ip_repo").rglob("component.xml"):
            root = ET.parse(component).getroot()
            for name in root.findall(".//s:file/s:name", ns):
                with self.subTest(component=component.name, source=name.text):
                    self.assertTrue((component.parent / name.text).is_file())


if __name__ == "__main__":
    unittest.main()
