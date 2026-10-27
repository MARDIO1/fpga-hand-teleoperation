"""Bounded latest-result publication; the worker never accesses leased DDR."""
from threading import Condition, Thread

from marker_transport import publish_points, publish_snapshot


class AsyncPublisher:
    def __init__(self, output):
        self.output = output
        self.condition = Condition()
        self.points = self.preview = None
        self.stopping = False
        self.error = None
        self.points_written = self.previews_written = self.previews_dropped = 0
        self.thread = Thread(target=self._run, name='marker-publisher', daemon=True)
        self.thread.start()

    def check(self):
        if self.error is not None:
            raise RuntimeError('Result publisher failed') from self.error

    def submit(self, result, frame=None):
        # Caller transfers ownership of result and the cached frame copy.
        with self.condition:
            self.check()
            if self.stopping:
                raise RuntimeError('Publisher is closed')
            self.points = result
            if frame is not None:
                self.previews_dropped += int(self.preview is not None)
                self.preview = (frame, result)
            self.condition.notify()

    def _run(self):
        try:
            while True:
                with self.condition:
                    self.condition.wait_for(lambda: self.stopping or self.points is not None or self.preview is not None)
                    points, preview = self.points, self.preview
                    self.points = self.preview = None
                    if points is None and preview is None and self.stopping:
                        return
                if points is not None:
                    publish_points(self.output, points)
                    self.points_written += 1
                if preview is not None:
                    publish_snapshot(self.output, preview[0], preview[1], 'bin')
                    self.previews_written += 1
        except BaseException as error:
            with self.condition:
                self.error = error

    def close(self):
        with self.condition:
            self.stopping = True
            self.condition.notify()
        self.thread.join(timeout=10)
        if self.thread.is_alive():
            raise RuntimeError('Result publisher did not stop within 10 seconds')
        self.check()
