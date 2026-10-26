#!/usr/bin/env python3
"""Compare the board's stereo matcher at three per-eye resolutions on a PC."""

import argparse
from pathlib import Path
import time

import cv2
import numpy as np

from depth_core import DepthProcessor, HEIGHT, WIDTH


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


def label(image, title, detail):
    top = np.full((74, image.shape[1], 3), 25, dtype=np.uint8)
    cv2.putText(top, title, (14, 29), cv2.FONT_HERSHEY_SIMPLEX,
                0.76, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(top, detail, (14, 57), cv2.FONT_HERSHEY_SIMPLEX,
                0.54, (190, 190, 190), 1, cv2.LINE_AA)
    return np.vstack((top, image))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="1280x720 RGB565 or PNG stereo frame")
    parser.add_argument("--output", type=Path, default=Path("output/depth_resolution_compare.png"))
    parser.add_argument("--calibration", type=Path, default=Path(__file__).resolve().parent.parent / "dual_camera_udp/metric_scale.npz")
    args = parser.parse_args()
    cv2.setNumThreads(1)
    captured = load_rgb565(args.input)
    shown = np.empty((HEIGHT, WIDTH), dtype=np.uint16)
    panels = [label(rgb565_bgr(captured[:, WIDTH // 2:]),
                    "Original left camera", "640 x 720 source")]
    for sample in (4, 2, 1):
        processor = DepthProcessor(np.load(str(args.calibration)), sample=sample)
        start = time.perf_counter()
        valid, median = processor.process(captured, shown)
        elapsed = time.perf_counter() - start
        pixels = (WIDTH // 2 // sample) * (HEIGHT // sample)
        detail = f"valid {valid / pixels:.1%} | median {median:.0f} mm | PC {elapsed * 1000:.0f} ms"
        panels.append(label(rgb565_bgr(shown[:, ::2]),
                            f"Depth {WIDTH // 2 // sample} x {HEIGHT // sample} (1/{sample})",
                            detail))
        print(f"sample={sample} size={WIDTH // 2 // sample}x{HEIGHT // sample} "
              f"valid={valid}/{pixels} median_mm={median:.0f} pc_ms={elapsed * 1000:.0f}")
    comparison = np.vstack((np.hstack(panels[:2]), np.hstack(panels[2:])))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(args.output), comparison):
        raise RuntimeError("could not save comparison")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
