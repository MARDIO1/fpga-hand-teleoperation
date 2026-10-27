"""Checks for lossless action recording and packet replay."""

from pathlib import Path
import tempfile
import unittest

import numpy as np

from action_io import ActionRecording, rewrite_payload
from protocol import MAGIC, PACKET, SENSOR, VERSION, decode_packet


def sample_payload() -> bytes:
    return PACKET.pack(MAGIC, VERSION, SENSOR, 7, 11, 0, 0, 1, 0,
                       *([0.0] * 13), *([0] * 5), 0)


class ActionIoTest(unittest.TestCase):
    def test_round_trip_and_rewrite(self) -> None:
        payload = np.frombuffer(sample_payload(), dtype=np.uint8).copy()
        recording = ActionRecording(np.array((0.0, 0.01)), np.stack((payload, payload)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "action.npz"
            recording.save(path)
            loaded = ActionRecording.load(path)
        np.testing.assert_array_equal(loaded.payloads, recording.payloads)
        sequence, sample = decode_packet(rewrite_payload(payload, 99, 1234, True))
        self.assertEqual(sequence, 99)
        self.assertEqual(sample.timestamp_us, 1234)
        self.assertTrue(sample.reset)


if __name__ == "__main__":
    unittest.main()
