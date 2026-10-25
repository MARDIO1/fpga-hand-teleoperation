import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"software/ps"))
from attitude import Attitude, Sample, euler
from run_mpu6050 import read_sample, packet_words, publish_packet
import struct
import json
import subprocess
import tempfile


def sample(i, accel=(0, 0, 8192), gyro=(0, 0, 0), timestamp=None):
    return Sample(i & 0xffffffff, i*2000 if timestamp is None else timestamp, accel, gyro)


class AttitudeTests(unittest.TestCase):
    def calibrated(self, accel=(0, 0, 8192), gyro=(0, 0, 0)):
        f = Attitude(calibration_samples=20)
        for i in range(20):
            pose = f.update(sample(i, accel, gyro))
        self.assertIsNotNone(pose)
        return f

    def test_static_tilt_initialization_and_bias_removal(self):
        for roll, pitch in [(0, 0), (35, -25), (-75, 40), (170, 10)]:
            r, p = map(math.radians, (roll, pitch))
            accel = tuple(round(v*8192) for v in
                          (-math.sin(p), math.sin(r)*math.cos(p), math.cos(r)*math.cos(p)))
            f = self.calibrated(accel, (80, -60, 100))
            for i in range(20, 1020):
                pose = f.update(sample(i, accel, (80, -60, 100)))
            self.assertAlmostEqual(pose["roll_deg"], roll, delta=0.02)
            self.assertAlmostEqual(pose["pitch_deg"], pitch, delta=0.02)
            self.assertAlmostEqual(pose["yaw_deg"], 0, delta=0.02)

    def test_yaw_integration_and_timestamp_jitter(self):
        f = self.calibrated()
        timestamp = 19*2000
        total = 0
        for i in range(20, 520):
            delta = 1500 if i % 2 else 2500
            timestamp += delta
            total += delta
            pose = f.update(sample(i, gyro=(0, 0, 5895), timestamp=timestamp)) # 90 deg/s
        self.assertAlmostEqual(pose["yaw_deg"], 90*total/1e6, delta=0.002)
        self.assertAlmostEqual(sum(v*v for v in pose["quaternion_wxyz"]), 1, places=12)

    def test_full_rotation_uses_body_rates(self):
        f = self.calibrated()
        for i in range(20, 520):
            angle = math.radians(90*(i-19)*0.002)
            a = (0, round(math.sin(angle)*8192), round(math.cos(angle)*8192))
            pose = f.update(sample(i, a, (5895, 0, 0)))
        self.assertAlmostEqual(pose["roll_deg"], 90, delta=0.4)
        self.assertAlmostEqual(pose["yaw_deg"], 0, delta=0.1)

    def test_stationary_filter_corrects_tilt_error(self):
        f = self.calibrated()
        f.q = (math.cos(0.2), math.sin(0.2), 0, 0)
        for i in range(20, 2020):
            pose = f.update(sample(i))
        self.assertLess(abs(pose["roll_deg"]), 0.5)

    def test_motion_restarts_calibration(self):
        f = Attitude(20)
        for i in range(19):
            self.assertIsNone(f.update(sample(i)))
        self.assertIsNone(f.update(sample(19, gyro=(1000, 0, 0))))
        self.assertEqual(f.calibration_count, 0)
        self.assertIsNone(f.bias)

    def test_online_calibration_matches_mean_without_retaining_history(self):
        f = Attitude(1000)
        for i in range(1000):
            pose = f.update(sample(i, gyro=(100+i % 3, -30, 20)))
        self.assertIsNotNone(pose)
        self.assertAlmostEqual(f.bias[0], math.radians(100.999/65.5), places=12)
        self.assertEqual(f.calibration_count, 0)
        self.assertFalse(hasattr(f, "calibration"))

    def test_dynamic_acceleration_gated(self):
        f = self.calibrated()
        pose = f.update(sample(20, (0, 0, 20000)))
        self.assertFalse(pose["accel_correction"])
        self.assertEqual(euler(f.q), (0, 0, 0))

    def test_gap_duplicate_backwards_and_invalid_input_rejected(self):
        for s in [sample(19), sample(20, timestamp=100), sample(40),
                  sample(20, gyro=(65535, 0, 0))]:
            f = self.calibrated()
            with self.assertRaises(ValueError):
                f.update(s)

    def test_sequence_and_32bit_timestamp_wrap(self):
        f = self.calibrated()
        f.last_sequence = 0xffffffff
        f.last_timestamp = 2**32-1000
        pose = f.update(Sample(0, 2**32+1000, (0, 0, 8192), (0, 0, 0)))
        self.assertEqual(pose["timestamp_us"], 2**32+1000)
        self.assertEqual(pose["dropped_samples"], 0)

    def test_skipped_sample_accounted(self):
        f = self.calibrated()
        pose = f.update(sample(21))
        self.assertEqual(pose["dropped_samples"], 1)

    def test_packet_keeps_original_raw_and_acquisition_time(self):
        f = self.calibrated()
        s = sample(20, (0, 0, 8192), (-123, 456, -789))
        pose = f.update(s)
        pose["attitude_epoch"] = 3
        words = packet_words(pose)
        self.assertEqual(len(words), 16)
        self.assertEqual(words[:5], [0x494d5531, 0x10007, 20, 40000, 0])
        self.assertEqual(words[7], (456 << 16) | (65536-123))
        self.assertEqual(words[8], 65536-789)
        self.assertEqual(words[14], 3)
        angle = struct.unpack("<f", struct.pack("<I", words[9]))[0]
        self.assertAlmostEqual(angle, pose["yaw_deg"], places=6)
        class Fake:
            writes = []
            def read(self, address): return 0
            def write(self, address, value): self.writes.append((address, value))
        mmio = Fake()
        self.assertTrue(publish_packet(mmio, pose))
        self.assertEqual(mmio.writes, [(0x40+i*4, w) for i, w in enumerate(words)]+[(0x80, 1)])

    def test_busy_packet_does_not_get_overwritten(self):
        class Busy:
            def read(self, address): return 1
            def write(self, address, value): raise AssertionError("Busy packet was overwritten")
        self.assertFalse(publish_packet(Busy(), {}))


class MMIOTests(unittest.TestCase):
    def test_decode_signs_and_64bit_timestamp(self):
        class Fake:
            def read(self, offset):
                return {0: 0x4d505531, 4: 3, 8: 10, 12: 7, 16: 2,
                        0x14: 0x1234, 0x18: 0xfffffedc, 0x1c: 8192,
                        0x20: 0xffffff80, 0x24: 64, 0x28: 32767, 0x2c: 258,
                        0x30: 0}[offset]
        s = read_sample(Fake())
        self.assertEqual(s.accel, (4660, -292, 8192))
        self.assertEqual(s.gyro, (-128, 64, 32767))
        self.assertEqual(s.timestamp_us, 2*2**32+7)

    def test_torn_read_is_retried(self):
        class Fake:
            count = 0
            def read(self, offset):
                if offset == 0: return 0x4d505531
                if offset == 4: return 3
                if offset == 8:
                    self.count += 1
                    return self.count
                return 0
        self.assertIsNone(read_sample(Fake()))

    def test_fault_hides_stale_sample(self):
        class Fake:
            def read(self, offset): return 0x4d505531 if offset == 0 else 0
        self.assertIsNone(read_sample(Fake()))


class ReplayTests(unittest.TestCase):
    def test_cli_replay_outputs_raw_pose_and_timestamp_together(self):
        scratch = Path(__file__).resolve().parents[1]/"sim/output"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(scratch)) as directory:
            raw = Path(directory)/"raw.jsonl"
            output = Path(directory)/"pose.jsonl"
            raw.write_text("".join(json.dumps(sample(i)._asdict())+"\n" for i in range(30)), encoding="utf-8")
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/"software/ps/run_mpu6050.py"),
                                     "--replay", str(raw), "--output", str(output),
                                     "--calibration-samples", "20"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(len(rows), 11)
            self.assertEqual(rows[-1]["sequence"], 29)
            self.assertEqual(rows[-1]["timestamp_us"], 58000)
            self.assertEqual(rows[-1]["raw_accel"], [0, 0, 8192])
            self.assertEqual(rows[-1]["raw_gyro"], [0, 0, 0])
            self.assertEqual([rows[-1][k] for k in ("yaw_deg", "pitch_deg", "roll_deg")], [0, 0, 0])
            stats = json.loads(result.stderr.splitlines()[-1])
            self.assertEqual(stats["poses"], 11)
            self.assertEqual(stats["dropped_samples"], 0)


if __name__ == "__main__":
    unittest.main()
