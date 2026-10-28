"""Compatibility test between the board sender and PC HAND v2 decoder."""

from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "integration" / "software" / "ps"))
sys.path.insert(0, str(ROOT / "simulation" / "virtual_hand"))

from board_stream import HAND, packet, pose_from_frame, smooth_bend
from vision_latest import LatestVision, VisionMarker
from wrist_ring import RingCalibration, RingMarker, WristRingTracker
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
                         (0.0, 0.0, 1.0), (0.1, -0.2, 0.3), True, True)
        decoded = decode_packet(payload)
        self.assertEqual(HAND.size, 84)
        self.assertEqual(decoded.sequence, 9)
        self.assertTrue(decoded.reset)
        self.assertTrue(decoded.imu_valid)
        self.assertTrue(decoded.sensor.camera_valid)
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

    def test_vision_latest_converts_mm_and_expires(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(json.dumps({
                "snapshot_sequence": 8, "source_frame_id": 42,
                "capture_boundary_timestamp_us": 123456,
                "metric_coordinates_available": True, "frame_errors": 0,
                "selected": {"L": [{"color": "red"}, {"color": "blue"}]},
                "matches": [
                    {"left": 0, "xyz_valid": True, "xyz_mm": [100, 200, 500]},
                    {"left": 1, "xyz_valid": True, "xyz_mm": [300, 400, 700]},
                ],
            }), encoding="utf-8")
            reader = LatestVision(path, max_age=0.2)
            sample = reader.poll(10.0)
            self.assertEqual(sample.sequence, 42)
            self.assertEqual(len(sample.markers), 2)
            self.assertEqual(sample.markers[0], VisionMarker("red", (0.1, 0.2, 0.5)))
            self.assertEqual(sample.markers[1].color, "blue")
            for actual, expected in zip(sample.markers[1].xyz_m, (0.3, 0.4, 0.7)):
                self.assertAlmostEqual(actual, expected)
            self.assertIsNone(reader.poll(10.21))

    def test_vision_color_filter(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            path.write_text(json.dumps({
                "snapshot_sequence": 1, "capture_boundary_timestamp_us": 2,
                "metric_coordinates_available": True, "frame_errors": 0,
                "selected": {"L": [{"color": "red"}, {"color": "blue"}]},
                "matches": [
                    {"left": 0, "xyz_valid": True, "xyz_mm": [10, 20, 30]},
                    {"left": 1, "xyz_valid": True, "xyz_mm": [90, 90, 90]},
                ],
            }), encoding="utf-8")
            sample = LatestVision(path, colors=("red",)).poll(1.0)
            self.assertEqual(sample.markers,
                             (VisionMarker("red", (0.01, 0.02, 0.03)),))

    def test_ring_recovers_center_from_occluded_repeated_colors(self):
        calibration = RingCalibration(
            ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
            (RingMarker("blue_left", "blue", (-0.03, 0, 0)),
             RingMarker("red", "red", (0, 0.02, 0)),
             RingMarker("blue_right", "blue", (0.03, 0, 0))))
        tracker = WristRingTracker(calibration)
        estimate = tracker.update((
            VisionMarker("blue", (0.13, 0.2, 0.5)),
            VisionMarker("blue", (0.07, 0.2, 0.5)),
        ), (1, 0, 0, 0))
        for actual, expected in zip(estimate.xyz_camera_m, (0.1, 0.2, 0.5)):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(estimate.used_markers, 2)

    def test_ring_holds_for_unidentified_single_blue(self):
        calibration = RingCalibration(
            ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
            (RingMarker("blue_left", "blue", (-0.03, 0, 0)),
             RingMarker("blue_right", "blue", (0.03, 0, 0)),
             RingMarker("red", "red", (0, 0.02, 0))))
        tracker = WristRingTracker(calibration)
        self.assertIsNone(tracker.update(
            (VisionMarker("blue", (0.1, 0.2, 0.5)),), (1, 0, 0, 0)))

    def test_ring_rejects_moving_thumb_with_same_yellow_color(self):
        calibration = RingCalibration(
            ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
            (RingMarker("wrist_yellow", "yellow", (0, 0, 0)),
             RingMarker("blue_left", "blue", (-0.03, 0, 0)),
             RingMarker("blue_right", "blue", (0.03, 0, 0))))
        tracker = WristRingTracker(calibration)
        estimate = tracker.update((
            VisionMarker("yellow", (0.1, 0.2, 0.5)),
            VisionMarker("yellow", (0.3, 0.4, 0.7)),  # moving thumb
            VisionMarker("blue", (0.07, 0.2, 0.5)),
            VisionMarker("blue", (0.13, 0.2, 0.5)),
        ), (1, 0, 0, 0))
        self.assertEqual(estimate.used_markers, 3)
        for actual, expected in zip(estimate.xyz_camera_m, (0.1, 0.2, 0.5)):
            self.assertAlmostEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
