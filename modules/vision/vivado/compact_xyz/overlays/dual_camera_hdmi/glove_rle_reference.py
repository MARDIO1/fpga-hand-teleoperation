"""Integer RGB565 classification and run-based 8-connected component reference.

This is a frame-level golden model, not a cycle/BRAM-accurate RTL simulator.
"""

import cv2
import numpy as np

from marker_detection import COLORS, validate_colors
from preview_downsample import rgb565_bgr


def integer_hsv565(pixels):
    if pixels.dtype != np.uint16:
        raise ValueError("Expected uint16 RGB565 pixels")
    # Match the existing PC decoder: zero-fill low bits, not bit replication.
    red = ((pixels.astype(np.int32) >> 11) & 31) << 3
    green = ((pixels.astype(np.int32) >> 5) & 63) << 2
    blue = (pixels.astype(np.int32) & 31) << 3
    maximum = np.maximum(np.maximum(red, green), blue)
    delta = maximum - np.minimum(np.minimum(red, green), blue)
    divisor = np.maximum(delta, 1)
    numerator = np.where(maximum == red, 30 * (green - blue),
                         np.where(maximum == green, 30 * (blue - red) + 60 * delta,
                                  30 * (red - green) + 120 * delta))
    # Normalize the red branch before division so RTL need not emulate signed
    # floor division (Verilog signed / instead truncates toward zero).
    numerator = np.where(numerator < 0, numerator + 180 * delta, numerator)
    hue = ((numerator + divisor // 2) // divisor) % 180
    hue = np.where(delta == 0, 0, hue)
    saturation = (255 * delta + maximum // 2) // np.maximum(maximum, 1)
    return np.stack((hue, saturation, maximum), axis=-1).astype(np.uint8)


def classify_hsv(hsv, thresholds):
    validate_colors(thresholds)
    classes = np.zeros(hsv.shape[:-1], np.uint8)
    overlaps = np.zeros_like(classes)
    h, s, v = (hsv[..., index] for index in range(3))
    # First match wins: red, yellow, green, blue. Record any ambiguous pixels.
    for color_id, name in enumerate(COLORS, 1):
        bounds = thresholds[name]
        low, high = bounds["h_min"], bounds["h_max"]
        hue = ((h >= low) & (h <= high)) if low <= high else ((h >= low) | (h <= high))
        matches = hue & (s >= bounds["s_min"]) & (v >= bounds["v_min"])
        overlaps += matches.astype(np.uint8)
        classes[matches & (classes == 0)] = color_id
    return classes, int(np.count_nonzero(overlaps > 1))


def classify565(pixels, thresholds):
    return classify_hsv(integer_hsv565(pixels), thresholds)


def opencv_classes(pixels, thresholds):
    return classify_hsv(cv2.cvtColor(rgb565_bgr(pixels), cv2.COLOR_BGR2HSV), thresholds)


def rle_components(classes):
    if classes.dtype != np.uint8 or classes.ndim != 2 or not classes.size or np.any(classes > len(COLORS)):
        raise ValueError("Expected a non-empty uint8 2D map with class IDs 0..4")
    parents, regions = {}, {}
    previous = []
    total_runs = max_row_runs = peak_active_roots = 0
    next_label = 0

    def root(label):
        while parents[label] != label:
            parents[label] = parents[parents[label]]
            label = parents[label]
        return label

    def merge(first, second):
        first, second = root(first), root(second)
        if first == second:
            return first
        if first > second:
            first, second = second, first
        parents[second] = first
        target, old = regions[first], regions.pop(second)
        for key in ("area", "sum_x", "sum_y"):
            target[key] += old[key]
        for key in ("xmin", "ymin"):
            target[key] = min(target[key], old[key])
        for key in ("xmax", "ymax"):
            target[key] = max(target[key], old[key])
        return first

    for y, row in enumerate(classes):
        edges = np.flatnonzero(np.r_[True, row[1:] != row[:-1], True])
        current, cursor = [], 0
        for start, stop in zip(edges[:-1], edges[1:]):
            color = int(row[start])
            if color == 0:
                continue
            start, end = int(start), int(stop - 1)
            while cursor < len(previous) and previous[cursor][1] < start - 1:
                cursor += 1
            connections = set()
            index = cursor
            while index < len(previous) and previous[index][0] <= end + 1:
                _, previous_end, previous_color, label = previous[index]
                if previous_end >= start - 1 and previous_color == color:
                    connections.add(root(label))
                index += 1
            if connections:
                label = min(connections)
                for other in sorted(connections):
                    label = merge(label, other)
            else:
                label = next_label
                next_label += 1
                parents[label] = label
                regions[label] = dict(color_id=color, area=0, sum_x=0, sum_y=0,
                                      xmin=start, xmax=end, ymin=y, ymax=y)
            region = regions[root(label)]
            length = end - start + 1
            region["area"] += length
            region["sum_x"] += (start + end) * length // 2
            region["sum_y"] += y * length
            region["xmin"] = min(region["xmin"], start)
            region["xmax"] = max(region["xmax"], end)
            region["ymax"] = y
            current.append((start, end, color, label))
        total_runs += len(current)
        max_row_runs = max(max_row_runs, len(current))
        peak_active_roots = max(peak_active_roots, len({root(run[3]) for run in previous + current}))
        previous = current
    # shortcut: retain all labels until frame end; add retirement/capacity handling
    # before using this algorithm as a bounded-memory hardware specification.
    stats = dict(total_runs=total_runs, max_row_runs=max_row_runs,
                 allocated_labels=next_label, peak_active_roots=peak_active_roots,
                 components=len(regions))
    return sorted(regions.values(), key=region_key), stats


def region_key(region):
    return tuple(region[key] for key in ("color_id", "ymin", "xmin", "ymax", "xmax", "area", "sum_x", "sum_y"))


def detect_rle_markers(pixels, thresholds, min_area=80, max_area=1500, roi=None):
    """Use the verified model in the live preview; no shape-based rejection."""
    if pixels.ndim != 2 or not 0 < min_area <= max_area:
        raise ValueError("Expected a 2D RGB565 eye and positive ordered area limits")
    classes, overlaps = classify565(pixels, thresholds)
    height, width = pixels.shape
    if roi is None:
        roi = (0, 0, width, height)
    x, y, w, h = roi
    if (any(type(value) is not int for value in roi) or min(x, y) < 0
            or min(w, h) <= 0 or x + w > width or y + h > height):
        raise ValueError("Glove ROI must be inside the eye image")
    allowed = np.zeros(classes.shape, bool)
    allowed[y:y+h, x:x+w] = True
    classes[~allowed] = 0
    regions, statistics = rle_components(classes)
    names = tuple(COLORS)
    candidates = []
    counters = dict.fromkeys(names, 0)
    for region in sorted(regions, key=lambda item: (item["color_id"], item["sum_x"] / item["area"], item["sum_y"] / item["area"])):
        if not min_area <= region["area"] <= max_area:
            continue
        if (region["xmin"] <= x or region["ymin"] <= y
                or region["xmax"] >= x + w - 1 or region["ymax"] >= y + h - 1):
            continue
        name = names[region["color_id"] - 1]
        counters[name] += 1
        candidates.append(dict(label=f"{name}{counters[name]}", color=name,
                               u=region["sum_x"] / region["area"], v=region["sum_y"] / region["area"],
                               area_px=region["area"], sum_x=region["sum_x"], sum_y=region["sum_y"],
                               bbox=[region["xmin"], region["ymin"], region["xmax"]-region["xmin"]+1,
                                     region["ymax"]-region["ymin"]+1]))
    statistics["overlap_pixels_full_eye"] = overlaps
    return candidates, classes, statistics


def opencv_components(classes):
    """Independent pixel-label oracle; no area/shape filtering before comparison."""
    result = []
    y, x = np.indices(classes.shape)
    for color_id in range(1, len(COLORS) + 1):
        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            (classes == color_id).astype(np.uint8), connectivity=8)
        sx = np.bincount(labels.ravel(), weights=x.ravel(), minlength=count)
        sy = np.bincount(labels.ravel(), weights=y.ravel(), minlength=count)
        for label in range(1, count):
            left, top, width, height, area = (int(value) for value in stats[label])
            result.append(dict(color_id=color_id, area=area, sum_x=int(sx[label]), sum_y=int(sy[label]),
                               xmin=left, xmax=left + width - 1, ymin=top, ymax=top + height - 1))
    return sorted(result, key=region_key)
