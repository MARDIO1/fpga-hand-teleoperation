import sys
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'software/hls_markers'))
from process_publisher import ProcessPublisher
from marker_transport import decode_snapshot


class ProcessPublisherTests(unittest.TestCase):
    def test_preview_slot_is_held_until_copy_ack_and_full_queue_never_reserves(self):
        worker = ProcessPublisher.__new__(ProcessPublisher)
        worker.errors, worker.jobs, worker.completed = Queue(), Queue(maxsize=1), Queue()
        worker.process = SimpleNamespace(exitcode=None)
        worker.reserved = set()
        worker.closed = False
        worker.previews_dropped = worker.points_dropped = 0
        token = {'base': 0x1e000000, 'frame_id': 7}
        self.assertTrue(worker.submit({'frame_token': token}, token=token))
        self.assertEqual(worker.held_slots, {token['base']})
        slots = (0x1e000000, 0x1e200000, 0x1e600000)
        self.assertEqual(next(base for base in slots if base != 0x1e200000 and base not in worker.held_slots), 0x1e600000)
        worker.completed.put(token['base'])
        self.assertEqual(worker.held_slots, set())
        self.assertFalse(worker.submit({'frame_token': token}, token=token))
        self.assertEqual(worker.held_slots, set())

    def test_drain_preserves_owned_snapshot_and_final_points(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as output:
            worker = ProcessPublisher(output)
            frame = np.full((720, 1280), 123, dtype='<u2')
            worker.submit({'sequence': 0}, frame)
            for index in range(1, 100):
                worker.submit({'sequence': index})
            worker.close()
            worker.close()
            image, result = decode_snapshot((Path(output)/'latest.bin').read_bytes())
            self.assertEqual(result['sequence'], 0)
            self.assertTrue(np.all(image == 123))
            self.assertEqual(__import__('json').loads((Path(output)/'latest.json').read_text())['sequence'], 99)
            self.assertGreater(worker.points_dropped, 0)

    def test_child_write_error_propagates(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as output:
            worker = ProcessPublisher(Path(output)/'missing')
            worker.submit({'sequence': 0})
            worker.process.join(5)
            with self.assertRaisesRegex(RuntimeError, 'publisher failed'):
                worker.close()


if __name__ == '__main__':
    unittest.main()
