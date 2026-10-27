"""Fixed-size stereo RGB565 file input and BGR conversion."""
import cv2
import numpy as np

WIDTH, HEIGHT = 1280, 720


def load_rgb565(path):
    if path.suffix.lower() == ".rgb565":
        frame = np.fromfile(str(path), dtype="<u2")
        if frame.size != WIDTH * HEIGHT:
            raise ValueError("expected a 1280x720 RGB565 frame")
        return frame.reshape(HEIGHT, WIDTH)
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None or bgr.shape[:2] != (HEIGHT, WIDTH):
        raise ValueError("expected a 1280x720 stereo image")
    b, g, r = cv2.split(bgr)
    return (((r.astype(np.uint16) & 0xF8) << 8)
            | ((g.astype(np.uint16) & 0xFC) << 3)
            | (b.astype(np.uint16) >> 3))


def rgb565_bgr(frame):
    b = ((frame & 31) << 3).astype(np.uint8)
    g = (((frame >> 5) & 63) << 2).astype(np.uint8)
    r = (((frame >> 11) & 31) << 3).astype(np.uint8)
    return cv2.merge((b, g, r))


