import unittest

from marker_stereo import match_markers


def marker(u,v,color='blue',area=300):
    return dict(u=u,v=v,color=color,area_px=area)


class StereoMarkerTests(unittest.TestCase):
    def test_sign_of_right_shift_and_disparity(self):
        result=match_markers([marker(200,104.12)],[marker(100,100)])
        self.assertEqual(len(result['pairs']),1)
        self.assertAlmostEqual(result['pairs'][0]['vertical_residual_px'],0)
        self.assertEqual(result['pairs'][0]['disparity_px'],100)
        self.assertFalse(result['metric_valid'])
        self.assertIsNone(result['pairs'][0]['xyz_mm'])

    def test_repeated_colors_get_distinct_pairs(self):
        result=match_markers([marker(200,100),marker(250,180)],
                             [marker(100,96),marker(150,176)])
        self.assertEqual([(p['left_index'],p['right_index']) for p in result['pairs']],[(0,0),(1,1)])

    def test_wrong_color_vertical_disparity_and_area_are_rejected(self):
        left=[marker(200,100)]
        for right in ([marker(100,96,'red')],[marker(100,140)],
                      [marker(220,96)],[marker(100,96,area=20)]):
            self.assertEqual(match_markers(left,right)['pairs'],[])

    def test_ambiguous_same_color_is_not_forced(self):
        result=match_markers([marker(200,100)], [marker(100,96),marker(110,96)])
        self.assertEqual(result['pairs'],[])

    def test_mutual_matching_prevents_duplicate_right(self):
        result=match_markers([marker(200,100),marker(210,104)], [marker(100,96)])
        self.assertEqual([(p['left_index'],p['right_index']) for p in result['pairs']],[(0,0)])

    def test_empty_and_invalid(self):
        self.assertEqual(match_markers([],[])['pairs'],[])
        with self.assertRaises(ValueError):
            match_markers([marker(float('nan'),10)],[])
        with self.assertRaises(ValueError):
            match_markers([],[],dict(uniqueness_margin=0))


if __name__=='__main__':
    unittest.main()
