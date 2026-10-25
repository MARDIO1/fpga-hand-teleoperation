"""Color-only component candidates; labels and centroids are frame-local."""

import json
from pathlib import Path

import cv2
import numpy as np


COLORS = {"red": (60, 60, 255), "yellow": (0, 255, 255),
          "green": (60, 230, 60), "blue": (255, 100, 30)}
DEFAULT_THRESHOLDS = Path(__file__).parent / "config" / "glove_color_thresholds.json"


def validate_colors(thresholds):
    if not isinstance(thresholds, dict) or set(thresholds) != set(COLORS):
        raise ValueError("Each eye needs red, yellow, green and blue thresholds")
    for name, bounds in thresholds.items():
        limits = dict(h_min=179, h_max=179, s_min=255, v_min=255)
        if not isinstance(bounds, dict) or set(bounds) != set(limits):
            raise ValueError(f"{name} needs h_min, h_max, s_min, v_min")
        if any(type(bounds[key]) is not int or not 0 <= bounds[key] <= limit
               for key, limit in limits.items()):
            raise ValueError(f"Invalid HSV bounds for {name}")


def load_thresholds(path=DEFAULT_THRESHOLDS):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != {"L", "R", "min_area", "max_area"}:
        raise ValueError("Threshold file needs L, R, min_area, max_area")
    for eye in ("L", "R"):
        validate_colors(config[eye])
    if (type(config["min_area"]) is not int or type(config["max_area"]) is not int
            or not 0 < config["min_area"] <= config["max_area"]):
        raise ValueError("Invalid component area limits")
    return config


def detect_markers(image, thresholds, min_area=80, max_area=1500):
    if image is None or image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Expected a uint8 BGR image")
    validate_colors(thresholds)
    if not 0 < min_area <= max_area:
        raise ValueError("Invalid component area limits")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    candidates = []
    classes = np.zeros(image.shape[:2], np.uint8)
    filtered = np.zeros_like(image)
    height, width = image.shape[:2]
    for class_id, (name, color) in enumerate(COLORS.items(), 1):
        bounds = thresholds[name]
        low, high = bounds["h_min"], bounds["h_max"]
        intervals = ((low, high),) if low <= high else ((low, 179), (0, high))
        mask = np.zeros(image.shape[:2], np.uint8)
        for first, last in intervals:
            mask |= cv2.inRange(hsv, (first, bounds["s_min"], bounds["v_min"]), (last, 255, 255))
        classes[mask != 0] = class_id
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        accepted = []
        keep = np.zeros(count, bool)
        for index in range(1, count):
            x, y, w, h, area = (int(value) for value in stats[index])
            if not min_area <= area <= max_area:
                continue
            # A clipped color component cannot provide a complete centroid.
            if x == 0 or y == 0 or x + w >= width or y + h >= height:
                continue
            keep[index] = True
            accepted.append((centroids[index], area, (x, y, w, h)))
        filtered[keep[labels]] = color
        for number, (center, area, box) in enumerate(sorted(accepted, key=lambda value: tuple(value[0])), 1):
            candidates.append(dict(label=f"{name}{number}", color=name, u=float(center[0]),
                                   v=float(center[1]), area_px=area, bbox=list(box)))
    return candidates, classes, filtered


def draw_candidates(image, candidates, eye):
    result = image.copy()
    for point in candidates:
        color = COLORS[point["color"]]
        x, y, w, h = point["bbox"]
        center = (round(point["u"]), round(point["v"]))
        cv2.rectangle(result, (x, y), (x + w, y + h), color, 1)
        cv2.drawMarker(result, center, color, cv2.MARKER_CROSS, 12, 1)
        text = f"{eye}:{point['label']} ({point['u']:.1f},{point['v']:.1f})"
        position = (max(0, min(x, image.shape[1] - 250)), max(15, y - 5))
        cv2.putText(result, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.43, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(result, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.43, color, 1, cv2.LINE_AA)
    return result


def colorize_classes(classes):
    palette = np.zeros((len(COLORS) + 1, 3), np.uint8)
    for index, color in enumerate(COLORS.values(), 1):
        palette[index] = color
    return palette[classes]
