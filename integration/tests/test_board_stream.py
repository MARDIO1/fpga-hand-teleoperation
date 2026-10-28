"""Compatibility test between the board sender and PC HAND v2 decoder."""

from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integration" / "software" / "ps"))
sys.path.insert(0, str(ROOT / "simulation" / "virtual_hand"))

from board_stream import HAND, packet, pose_from_frame, smooth_bend
from live_hand_udp import decode_packet
from smoke_board import HAND_INPUT, HAND_OUTPUT, run_hand_core


class BoardStreamTest(unittest.TestCase):
    def test_pose_uses_calibrated_imuq_quaternion(self):
        class Frame:
            mpu_present = True
            sample_valid = True
            calibrated = True
            timestamp_us = 123456
            quaternion_wxyz = (0.5, 0.5, 0.5, 0.5)

        pose = pose_from_frame(Frame())
        self.assertEqual(pose["timestamp_us"], 123456)
        self.assertEqual(pose["quaternion_wxyz"], (0.5, 0.5, 0.5, 0.5))
        self.assertEqual(pose["acceleration_g"], (0.0, 0.0, 0.0))

    def test_pose_rejects_uncalibrated_imuq_frame(self):
        class Frame:
            mpu_present = True
            sample_valid = True
            calibrated = False

        self.assertIsNone(pose_from_frame(Frame()))

    def test_packet_matches_pc_decoder(self):
        payload = packet(9, 123456, (1.0, 0.0, 0.0, 0.0),
                         (0, 0, 2048, 0, 0), (0.1, 0.2, 0.3),
                         (0.0, 0.0, 1.0), (0.1, -0.2, 0.3), True)
        decoded = decode_packet(payload)
        self.assertEqual(HAND.size, 84)
        self.assertEqual(decoded.sequence, 9)
        self.assertTrue(decoded.reset)
        self.assertTrue(decoded.imu_valid)
        self.assertEqual(int(decoded.sensor.flex_raw[2]), 2048)
        self.assertEqual(tuple(decoded.sensor.linear_acceleration), (0.0, 0.0, 1.0))
        self.assertAlmostEqual(decoded.sensor.angular_velocity[1], -0.2, places=6)

    def test_bend_filter_holds_jitter_and_tracks_motion(self):
        previous = smooth_bend(None, (0, 0, 2000, 0, 0), 0.25, 16)
        held = smooth_bend(previous, (0, 0, 2010, 0, 0), 0.25, 16)
        moved = smooth_bend(held, (0, 0, 2100, 0, 0), 0.25, 16)
        self.assertEqual(held[2], 2000)
        self.assertEqual(moved[2], 2025)

    def test_hand_core_smoke_transaction_matches_hls_layout(self):
        class FakeMmio:
            def __init__(self):
                self.writes = {}
                output = HAND_OUTPUT.pack(*(0.0,) * 22, 2, 0)
                self.output = struct.unpack("<23I", output)

            def write(self, offset, value):
                self.writes[offset] = value

            def read(self, offset):
                if offset == 0:
                    return 2
                return self.output[(offset - 0x100) // 4]

        mmio = FakeMmio()
        result = run_hand_core(mmio)
        self.assertEqual(HAND_INPUT.size, 72)
        self.assertEqual(HAND_OUTPUT.size, 92)
        self.assertEqual(result, {"valid": 2, "state": 0})
        self.assertEqual(mmio.writes[0x18], 1)
        self.assertEqual(mmio.writes[0], 1)


if __name__ == "__main__":
    unittest.main()
