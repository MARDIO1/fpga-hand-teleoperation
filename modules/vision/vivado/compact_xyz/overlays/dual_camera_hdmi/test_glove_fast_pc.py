import unittest

import numpy as np

from glove_fast_pc import ExactColorDetector, detect_classes, make_color_lut
from glove_rle_reference import classify565, detect_rle_markers
from marker_detection import load_thresholds


class FastDetectorTests(unittest.TestCase):
    def test_all_rgb565_codes(self):
        config = load_thresholds()
        codes = np.arange(65536, dtype=np.uint16)
        for eye in ('L', 'R'):
            np.testing.assert_array_equal(make_color_lut(config[eye])[codes],
                                          classify565(codes, config[eye])[0])

    def test_same_as_rle_and_roi_coordinates(self):
        config = load_thresholds()
        pixels = np.zeros((50, 90), np.uint16)
        pixels[10:24, 15:29] = 0xf800
        pixels[10:24, 29:43] = 0x001f  # Adjacent different colors stay separate.
        pixels[30:40, 70:80] = 0x07e0
        pixels[0:10, 0:10] = 0xf800  # Clipped component is rejected.
        fast = ExactColorDetector()
        for roi in (None, (10, 5, 40, 30)):
            expected, classes, _ = detect_rle_markers(pixels, config['L'], 20, 500, roi)
            actual, actual_classes, _ = fast.detect(pixels, config['L'], 20, 500, roi)
            self.assertEqual(expected, actual)
            np.testing.assert_array_equal(classes, actual_classes)

    def test_geometry_rejects_thin_noise(self):
        classes = np.zeros((80, 100), np.uint8)
        classes[10:30, 10:30] = 1
        classes[40:43, 10:60] = 4
        self.assertEqual(len(detect_classes(classes)), 2)
        self.assertEqual(len(detect_classes(classes, geometry=True)), 1)

    def test_two_to_one_boundary_is_inclusive(self):
        classes=np.zeros((80,120),np.uint8)
        classes[10:34,10:58]=1  # 48/24 exactly 2:1.
        classes[45:69,10:59]=3  # 49/24 exceeds 2:1.
        actual=detect_classes(classes,geometry=True)
        self.assertEqual(len(actual),1)
        self.assertEqual(actual[0]['bbox'][2:],[48,24])

    def test_preview_backend_preserves_candidates(self):
        from preview_glove_pc import process_frame
        config = load_thresholds()
        frame = np.zeros((720, 1280), np.uint16)
        frame[100:120, 100:120] = 0xf800
        frame[200:220, 800:820] = 0x001f
        _, expected, _ = process_frame(frame, config)
        _, actual, _ = process_frame(frame, config, detector=ExactColorDetector())
        self.assertEqual(expected, actual)

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            detect_classes(np.full((2, 3), 5, np.uint8))
        with self.assertRaises(ValueError):
            ExactColorDetector().detect(np.zeros((5, 5), np.uint16),
                                        load_thresholds()['L'], roi=(0, 0, 6, 5))


if __name__ == '__main__':
    unittest.main()
