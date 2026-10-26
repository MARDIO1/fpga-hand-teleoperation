"""Compatibility test between the board sender and PC HAND v2 decoder."""

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integration" / "software" / "ps"))
sys.path.insert(0, str(ROOT / "simulation" / "virtual_hand"))

from board_stream import HAND, packet
from live_hand_udp import decode_packet


class BoardStreamTest(unittest.TestCase):
    def test_packet_matches_pc_decoder(self):
        payload = packet(9, 123456, (1.0, 0.0, 0.0, 0.0),
                         (0, 0, 2048, 0, 0), (0.1, 0.2, 0.3), True)
        decoded = decode_packet(payload)
        self.assertEqual(HAND.size, 84)
        self.assertEqual(decoded.sequence, 9)
        self.assertTrue(decoded.reset)
        self.assertTrue(decoded.imu_valid)
        self.assertEqual(int(decoded.sensor.flex_raw[2]), 2048)


if __name__ == "__main__":
    unittest.main()
