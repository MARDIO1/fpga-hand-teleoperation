import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

MODULE = Path(__file__).resolve().parents[1]
RELEASE = MODULE/"export/bitstream/acz7015/v0.1.0"
IP = MODULE/"export/ip/v0.1.0"


class ReleaseTests(unittest.TestCase):
    def test_binary_and_rebuild_sources_match_manifest(self):
        info = json.loads((RELEASE/"build_info.json").read_text(encoding="utf-8"))
        for name, expected in info["files"].items():
            with self.subTest(artifact=name):
                self.assertEqual(hashlib.sha256((RELEASE/name).read_bytes()).hexdigest(), expected)
        for name, expected in info["rebuild_source_sha256"].items():
            with self.subTest(source=name):
                self.assertEqual(hashlib.sha256((MODULE/name).read_bytes()).hexdigest(), expected)

    def test_packaged_ip_references_and_rtl(self):
        ns = {"s": "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"}
        core = ET.parse(IP/"component.xml").getroot()
        interfaces = {n.text for n in core.findall("./s:busInterfaces/s:busInterface/s:name", ns)}
        self.assertTrue({"s_axi", "m_axis"} <= interfaces)
        for item in core.findall(".//s:file/s:name", ns):
            self.assertTrue((IP/item.text).is_file(), item.text)
        for source in (MODULE/"rtl").glob("*.v"):
            self.assertEqual(source.read_bytes(), (IP/"src"/source.name).read_bytes())

    def test_validation_does_not_claim_completed_integration(self):
        info = json.loads((RELEASE/"build_info.json").read_text(encoding="utf-8"))
        self.assertFalse(info["provenance"]["bit_identical_rebuild_claimed"])
        self.assertFalse(info["validation"]["combined_overlay_validated"])
        self.assertFalse(info["validation"]["continuous_low_latency_transport_validated"])


if __name__ == "__main__":
    unittest.main()
