"""Separate-process, bounded publication of owned CPU snapshots."""
import multiprocessing as mp
from queue import Empty, Full

from marker_transport import publish_points, publish_snapshot


def _publish(output, jobs, errors, counts, completed, ready):
    try:
        ready.set()
        while True:
            job = jobs.get()
            if job is None:
                return
            result, frame, token = job
            if token is not None:
                import mmap
                import os
                import numpy as np
                base = token['base']
                if base not in (0x1e000000, 0x1e200000, 0x1e600000):
                    raise ValueError('Preview slot outside reserved whitelist')
                fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
                try:
                    with mmap.mmap(fd, 1280*720*2, flags=mmap.MAP_SHARED,
                                   prot=mmap.PROT_READ, offset=base) as memory:
                        frame = np.frombuffer(memory[:], dtype='<u2').reshape(720, 1280)
                finally:
                    os.close(fd)
                # Parent can reuse DDR only after this CPU-owned copy exists.
                completed.put(base)
            publish_points(output, result)
            counts[0] += 1
            if frame is not None:
                publish_snapshot(output, frame, result, 'bin')
                counts[1] += 1
    except BaseException as error:
        errors.put(repr(error))
        raise


class ProcessPublisher:
    def __init__(self, output):
        context = mp.get_context('spawn')
        self.output = output
        self.jobs = context.Queue(maxsize=1)
        self.errors = context.Queue()
        self.completed = context.Queue()
        self.ready = context.Event()
        self.reserved = set()
        self.counts = context.Array('L', 2)
        self.process = context.Process(target=_publish, args=(str(output), self.jobs, self.errors, self.counts, self.completed, self.ready), daemon=True)
        self.process.start()
        self.previews_dropped = self.points_dropped = 0
        self.last_result = None
        self.closed = False
        if not self.ready.wait(timeout=15):
            self.process.terminate()
            self.process.join(timeout=5)
            raise RuntimeError('Result publisher startup timed out')
        self.check()

    @property
    def points_written(self):
        return self.counts[0]

    @property
    def previews_written(self):
        return self.counts[1]

    def check(self):
        try:
            error = self.errors.get_nowait()
        except Empty:
            error = None
        if error is not None or self.process.exitcode not in (None, 0):
            raise RuntimeError('Result publisher failed: '+str(error or self.process.exitcode))

    @property
    def held_slots(self):
        self.check()
        while True:
            try:
                self.reserved.remove(self.completed.get_nowait())
            except Empty:
                return set(self.reserved)

    def submit(self, result, frame=None, token=None):
        self.check()
        if self.closed:
            raise RuntimeError('Publisher is closed')
        self.last_result = result
        if token is not None:
            if token != result.get('frame_token') or token['base'] not in (0x1e000000, 0x1e200000, 0x1e600000):
                raise ValueError('Preview token mismatch')
            if self.held_slots:
                self.previews_dropped += 1
                token = None
        try:
            self.jobs.put_nowait((result, frame, token))
            if token is not None:
                self.reserved.add(token['base'])
            return frame is not None or token is not None
        except Full:
            self.points_dropped += 1
            self.previews_dropped += int(frame is not None or token is not None)
            return False

    def close(self):
        if self.closed:
            return
        self.check()
        self.jobs.put(None, timeout=10)
        self.process.join(timeout=10)
        if self.process.is_alive():
            raise RuntimeError('Result publisher did not stop within 10 seconds')
        self.check()
        # Preserve the final point result even if the bounded queue was full.
        if self.last_result is not None:
            publish_points(self.output, self.last_result)
        self.jobs.close()
        self.jobs.join_thread()
        self.errors.close()
        self.completed.close()
        self.reserved.clear()
        self.closed = True
