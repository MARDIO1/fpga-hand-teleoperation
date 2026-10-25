"""Synthetic checks for color, repeated colors, area and center extraction."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "software/pc"))
from unittest.mock import patch

import cv2
import numpy as np

from marker_detection import detect_markers, load_thresholds, validate_colors
from preview_glove_pc import HEADER, FRAME_BYTES, process_frame, read_exact, update_controls
from io import BytesIO


class MarkerTests(unittest.TestCase):
    def setUp(self):
        self.thresholds = load_thresholds()

    def test_six_blobs_with_repeated_colors_and_red_hue_wrap(self):
        hsv = np.zeros((240, 400, 3), np.uint8)
        markers = [(50, 60, 0, "red"), (170, 60, 179, "red"),
                   (290, 60, 60, "green"), (50, 170, 60, "green"),
                   (170, 170, 115, "blue"), (290, 170, 28, "yellow")]
        for x, y, hue, _ in markers:
            cv2.circle(hsv, (x, y), 12, (hue, 230, 220), -1)
        points, classes, filtered = detect_markers(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), self.thresholds["L"])
        self.assertEqual(len(points), 6)
        self.assertEqual(sum(point["color"] == "red" for point in points), 2)
        for x, y, _, color in markers:
            nearest = min(points, key=lambda point: (point["u"] - x)**2 + (point["v"] - y)**2)
            self.assertEqual(nearest["color"], color)
            self.assertAlmostEqual(nearest["u"], x, places=3)
            self.assertAlmostEqual(nearest["v"], y, places=3)
        self.assertGreater(np.count_nonzero(classes), 0)
        self.assertGreater(np.count_nonzero(filtered), 0)

    def test_area_and_border_checks_remain_but_elongated_shapes_are_accepted(self):
        image = np.full((240, 400, 3), 150, np.uint8)
        cv2.circle(image, (0, 40), 15, (0, 0, 255), -1)
        cv2.circle(image, (80, 50), 2, (0, 0, 255), -1)
        cv2.circle(image, (200, 100), 50, (0, 255, 0), -1)
        cv2.rectangle(image, (50, 160), (180, 168), (255, 0, 0), -1)
        points, _, _ = detect_markers(image, self.thresholds["L"])
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["color"], "blue")
        self.assertGreater(points[0]["bbox"][2] / points[0]["bbox"][3], 10)
        self.assertNotIn("circularity", points[0])

    def test_blue_stripe_is_not_specially_removed(self):
        image = np.zeros((200, 300, 3), np.uint8)
        cv2.line(image, (20, 60), (95, 60), (255, 0, 0), 6)
        cv2.circle(image, (100, 60), 12, (255, 0, 0), -1)
        cv2.rectangle(image, (150, 120), (220, 129), (255, 0, 0), -1)
        points, _, _ = detect_markers(image, self.thresholds["L"])
        self.assertEqual(len(points), 2)
        self.assertTrue(all(point["color"] == "blue" for point in points))
        self.assertTrue(all(point["bbox"][2] > 60 for point in points))

    def test_right_eye_recognizes_pale_yellow_and_purple_red_independently(self):
        hsv = np.zeros((160, 240, 3), np.uint8)
        cv2.circle(hsv, (50, 60), 12, (32, 50, 240), -1)
        cv2.circle(hsv, (150, 60), 12, (160, 180, 150), -1)
        image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        left, _, _ = detect_markers(image, self.thresholds["L"])
        right, _, _ = detect_markers(image, self.thresholds["R"])
        self.assertEqual(left, [])
        self.assertEqual({point["color"] for point in right}, {"red", "yellow"})

    def test_control_switch_preserves_independent_eye_and_color_settings(self):
        controls = {"eye L0 R1": 0, "color RYGB": 0, "min area": 80, "max area": 1500}
        with patch("preview_glove_pc.cv2.getTrackbarPos", side_effect=lambda key, _: controls[key]), \
             patch("preview_glove_pc.cv2.setTrackbarPos", side_effect=lambda key, _, value: controls.update({key: value})):
            previous = update_controls(self.thresholds, None)
            self.assertEqual(controls["H min"], 165)
            controls["min S"] = 125
            previous = update_controls(self.thresholds, previous)
            controls["eye L0 R1"] = 1
            previous = update_controls(self.thresholds, previous)
            self.assertEqual(controls["min S"], 100)
            self.assertEqual(controls["H min"], 155)
            controls["color RYGB"] = 1
            update_controls(self.thresholds, previous)
            self.assertEqual(controls["min S"], 35)
        self.assertEqual(self.thresholds["L"]["red"]["s_min"], 125)
        self.assertEqual(self.thresholds["R"]["red"]["s_min"], 100)

    def test_invalid_hsv_is_rejected(self):
        self.thresholds["R"]["yellow"]["h_min"] = 200
        with self.assertRaisesRegex(ValueError, "Invalid HSV"):
            validate_colors(self.thresholds["R"])

    def test_left_right_split_and_preview(self):
        frame = np.zeros((720, 1280), np.uint16)
        cv2.circle(frame[:, :640], (100, 200), 12, int(0xF800), -1)
        cv2.circle(frame[:, 640:], (150, 200), 12, int(0xF800), -1)
        preview, points, _ = process_frame(frame, self.thresholds)
        self.assertEqual(preview.shape, (1176, 1280, 3))
        self.assertEqual(points["L"][0]["u"], 150)
        self.assertEqual(points["R"][0]["u"], 100)

    def test_stream_header_and_short_read(self):
        header = HEADER.pack(b"GLV1", 7, 100, 200, FRAME_BYTES)
        self.assertEqual(HEADER.unpack(read_exact(BytesIO(header), HEADER.size))[1], 7)
        with self.assertRaises(EOFError):
            read_exact(BytesIO(b"short"), 20)


if __name__ == "__main__":
    unittest.main()
