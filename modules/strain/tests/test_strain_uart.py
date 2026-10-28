"""Tests for the board-side IMUQ decoder and calibration mapping."""

import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / "software" / "ps"
sys.path.insert(0, str(MODULE))

from strain_uart import Calibration, Decoder, FRAME, PreviewCalibration, crc16_ccitt


def packet(sequence=7, status=0x0b, quaternion=(1.0, 0.1, 0.2, 0.3),
           raw=(1, 2, 3, 4, 5), temperature=1234):
    body = struct.pack("<4sBBHII4f5Hh", b"IMUQ", 1, status, FRAME.size,
                       sequence, 123000, *quaternion, *raw, temperature)
    return body + struct.pack("<H", crc16_ccitt(body))


class DecoderTest(unittest.TestCase):
    def test_fragmented_frame_and_resync(self):
        decoder = Decoder()
        payload = packet()
        self.assertEqual(decoder.feed(b"bad" + payload[:9]), [])
        frames = decoder.feed(payload[9:])
        self.assertEqual(frames[0].sequence, 7)
        self.assertEqual(frames[0].status, 0x0b)
        self.assertAlmostEqual(frames[0].quaternion_wxyz[1], 0.1, places=6)
        self.assertEqual(frames[0].raw, (1, 2, 3, 4, 5))
        self.assertEqual(frames[0].temperature_raw, 1234)
        self.assertTrue(frames[0].mpu_present)
        self.assertTrue(frames[0].sample_valid)
        self.assertFalse(frames[0].calibrating)
        self.assertTrue(frames[0].calibrated)

    def test_crc_rejected(self):
        decoder = Decoder()
        payload = bytearray(packet())
        payload[28] ^= 1
        self.assertEqual(decoder.feed(payload), [])
        self.assertEqual(decoder.rejected, 1)


class CalibrationTest(unittest.TestCase):
    def test_decreasing_three_pose_mapping(self):
        poses = {"open": [0, 0, 3000, 0, 0],
                 "half": [0, 0, 2200, 0, 0],
                 "fist": [0, 0, 1000, 0, 0]}
        calibration = Calibration([2], poses)
        self.assertEqual(calibration.map((0, 0, 3000, 0, 0))[2], 0)
        self.assertEqual(calibration.map((0, 0, 2200, 0, 0))[2], 2048)
        self.assertEqual(calibration.map((0, 0, 1000, 0, 0))[2], 4095)

    def test_load(self):
        data = {"schema": "strain.calibration.v1", "channels": [2],
                "poses": {"open": [0, 0, 1000, 0, 0],
                          "half": [0, 0, 2000, 0, 0],
                          "fist": [0, 0, 3000, 0, 0]}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibration.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(Calibration.load(path).map((0, 0, 2000, 0, 0))[2], 2048)

    def test_preview_uses_absolute_change_from_startup(self):
        preview = PreviewCalibration(channel=2, span=600)
        self.assertEqual(preview.map((0, 0, 3000, 0, 0))[2], 0)
        self.assertEqual(preview.map((0, 0, 2700, 0, 0))[2], 2048)
        self.assertEqual(preview.map((0, 0, 3700, 0, 0))[2], 4095)


if __name__ == "__main__":
    unittest.main()
