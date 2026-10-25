import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"software/pc"))
from view_live import parse_pose


class LiveViewerTests(unittest.TestCase):
    def frame(self):
        return {"schema": "mpu6050.attitude.v1", "valid": True,
                "timestamp_us": 123, "yaw_deg": 1, "pitch_deg": 2, "roll_deg": 3,
                "raw_accel": [0, 0, 8192], "raw_gyro": [1, -2, 3]}

    def test_complete_pose_preserves_raw_and_timestamp(self):
        frame = self.frame()
        self.assertEqual(parse_pose(json.dumps(frame)), frame)

    def test_reject_invalid_nonfinite_and_wrong_axis_count(self):
        for key, value in [("valid", False), ("yaw_deg", math.nan),
                           ("raw_accel", [1, 2]), ("timestamp_us", -1)]:
            frame = self.frame()
            frame[key] = value
            with self.assertRaises(ValueError):
                parse_pose(json.dumps(frame))


if __name__ == "__main__":
    unittest.main()
