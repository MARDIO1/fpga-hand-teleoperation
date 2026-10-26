"""Stereo matching shared by the board display and PC resolution preview."""

import cv2
import numpy as np


WIDTH, HEIGHT = 1280, 720
HALF = WIDTH // 2
VERTICAL_SHIFT_PX = 4.12  # median of 18 saved stereo checkerboard pairs


class DepthProcessor:
    def __init__(self, scale, sample=4):
        if sample not in (1, 2, 4):
            raise ValueError("sample must be 1, 2, or 4")
        self.sample = sample
        self.num_disparities = 192 // sample
        self.focal = float(scale["focal_px"]) / sample
        self.baseline = float(scale["baseline_mm"])
        self.offset = float(scale["offset_px"]) / sample
        self.matcher = cv2.StereoSGBM_create(
            minDisparity=0, numDisparities=self.num_disparities, blockSize=5,
            P1=8 * 25, P2=32 * 25, disp12MaxDiff=1,
            uniquenessRatio=8, speckleWindowSize=50, speckleRange=2,
            mode=cv2.STEREO_SGBM_MODE_SGBM,
        )
        palette = getattr(cv2, "COLORMAP_TURBO", cv2.COLORMAP_JET)
        ramp = cv2.applyColorMap(np.arange(256, dtype=np.uint8)[:, None],
                                palette).reshape(256, 3)
        b, g, r = (ramp[:, 0].astype(np.uint16),
                   ramp[:, 1].astype(np.uint16),
                   ramp[:, 2].astype(np.uint16))
        self.rgb565 = np.zeros(256, dtype=np.uint16)
        self.rgb565[1:] = ((r[1:] & 0xF8) << 8) | ((g[1:] & 0xFC) << 3) | (b[1:] >> 3)

    def process(self, captured, shown):
        # The vendor's first 640 columns come from the physical right lens.
        # RGB565 green is a low-cost luminance proxy for stereo matching.
        right = (((captured[::self.sample, :HALF:self.sample] >> 5) & 63) * 4).astype(np.uint8)
        left = (((captured[::self.sample, HALF::self.sample] >> 5) & 63) * 4).astype(np.uint8)
        right = cv2.warpAffine(right,
                               np.float32([[1, 0, 0], [0, 1, VERTICAL_SHIFT_PX / self.sample]]),
                               (HALF // self.sample, HEIGHT // self.sample))
        disparity = self.matcher.compute(left, right).astype(np.float32) / 16.0
        valid = (disparity > self.offset + 0.5) & (disparity < self.num_disparities)
        depth_mm = np.zeros(disparity.shape, dtype=np.float32)
        np.divide(self.focal * self.baseline, disparity - self.offset,
                  out=depth_mm, where=valid)
        valid &= (depth_mm >= 300) & (depth_mm <= 3000)
        index = np.zeros(disparity.shape, dtype=np.uint8)
        index[valid] = np.clip(1 + (3000 - depth_mm[valid]) * 254 / 2700,
                               1, 255).astype(np.uint8)
        full_index = cv2.resize(index, (WIDTH, HEIGHT),
                                interpolation=cv2.INTER_NEAREST)
        np.take(self.rgb565, full_index, out=shown)
        median_mm = float(np.median(depth_mm[valid])) if np.any(valid) else 0.0
        return int(np.count_nonzero(valid)), median_mm
