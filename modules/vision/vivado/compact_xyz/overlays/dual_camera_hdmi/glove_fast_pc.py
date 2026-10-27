"""Fast PC execution of the integer-HSV model; no hardware timing claim."""

import cv2
import numpy as np

from glove_rle_reference import classify565
from marker_detection import COLORS


GEOMETRY_SPEC = dict(min_width_px=8, min_height_px=8, max_width_px=70,
                     max_height_px=70, max_aspect_ratio=2, center='area_centroid')


def make_color_lut(thresholds):
    # Every RGB565 value is evaluated once; runtime labels are bit-exact.
    return classify565(np.arange(65536, dtype=np.uint16), thresholds)[0]


def detect_classes(classes, min_area=80, max_area=1500, geometry=False):
    if (classes.dtype != np.uint8 or classes.ndim != 2 or not classes.size
            or np.any(classes > len(COLORS)) or not 0 < min_area <= max_area):
        raise ValueError("Expected class IDs 0..4 and positive ordered area bounds")
    height, width = classes.shape
    candidates = []
    for color_id, name in enumerate(COLORS, 1):
        _, _, stats, centers = cv2.connectedComponentsWithStats(
            (classes == color_id).astype(np.uint8), connectivity=8)
        # Filter before entering Python: background speckles never become dicts.
        keep = ((stats[:, 4] >= min_area) & (stats[:, 4] <= max_area)
                & (stats[:, 0] > 0) & (stats[:, 1] > 0)
                & (stats[:, 0] + stats[:, 2] < width)
                & (stats[:, 1] + stats[:, 3] < height))
        keep[0] = False
        if geometry:
            spec = GEOMETRY_SPEC
            keep &= ((stats[:, 2] >= spec['min_width_px']) & (stats[:, 3] >= spec['min_height_px'])
                     & (stats[:, 2] <= spec['max_width_px']) & (stats[:, 3] <= spec['max_height_px'])
                     & (stats[:, 2] <= spec['max_aspect_ratio'] * stats[:, 3])
                     & (stats[:, 3] <= spec['max_aspect_ratio'] * stats[:, 2]))
        accepted = sorted(np.flatnonzero(keep), key=lambda i: tuple(centers[i]))
        for number, i in enumerate(accepted, 1):
            x, y, w, h, area = (int(value) for value in stats[i])
            u, v = (float(value) for value in centers[i])
            candidates.append(dict(label=f"{name}{number}", color=name, u=u, v=v,
                                   area_px=area, sum_x=round(u * area), sum_y=round(v * area),
                                   bbox=[x, y, w, h]))
    return candidates


class ExactColorDetector:
    """Rebuild the 64 KiB table only when the eye's four thresholds change."""

    def __init__(self, geometry=False):
        self.tables = {}
        self.geometry = geometry

    def detect(self, pixels, thresholds, min_area=80, max_area=1500, roi=None):
        if pixels.dtype != np.uint16 or pixels.ndim != 2:
            raise ValueError("Expected a 2D uint16 RGB565 eye")
        signature = tuple(tuple(sorted(thresholds[name].items())) for name in COLORS)
        if signature not in self.tables:
            # Keep only current left/right configurations, not every slider value.
            if len(self.tables) >= 2:
                self.tables.clear()
            self.tables[signature] = make_color_lut(thresholds)
        height, width = pixels.shape
        x, y, w, h = (0, 0, width, height) if roi is None else roi
        if (any(type(value) is not int for value in (x, y, w, h)) or min(x, y) < 0
                or min(w, h) <= 0 or x + w > width or y + h > height):
            raise ValueError("Glove ROI must be inside the eye image")
        crop = self.tables[signature][pixels[y:y+h, x:x+w]]
        points = detect_classes(crop, min_area, max_area, self.geometry)
        for point in points:
            point['u'] += x
            point['v'] += y
            point['sum_x'] += x * point['area_px']
            point['sum_y'] += y * point['area_px']
            point['bbox'][0] += x
            point['bbox'][1] += y
        classes = np.zeros(pixels.shape, np.uint8)
        classes[y:y+h, x:x+w] = crop
        return points, classes, dict(backend='exact_rgb565_lut_native_ccl')
