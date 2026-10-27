import tempfile
from pathlib import Path
import unittest

import cv2
import numpy as np

from calibrated_marker_stereo import CalibratedMarkerMatcher


class CalibratedMatcherTests(unittest.TestCase):
    def test_physical_left_frame_and_sparse_inverse_distortion(self):
        root=Path(__file__).resolve().parents[2]/'output/test_tmp';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            self.assertEqual(Path(folder).resolve().parent,root.resolve())
            k=np.array([[800.,0,320],[0,810,360],[0,0,1.]])
            d=np.array([-.1,.03,.001,-.001,.005])
            rvec=np.array([.002,.02,-.003]);rot=cv2.Rodrigues(rvec)[0];t=np.array([-33.4,.2,.4])
            r1,r2,p1,p2,_,_,_=cv2.stereoRectify(k,d,k,d,(640,720),rot,t)
            path=Path(folder)/'candidate.npz'
            np.savez(path,K1=k,K2=k,D1=d,D2=d,R=rot,T=t,R1=r1,R2=r2,P1=p1,P2=p2,
                     image_size=[640,720],square_mm=13.6,metric_valid=False)
            matcher=CalibratedMarkerMatcher(path)
            xyz=np.array([[50.,20.,500.],[40.,80.,650.]])
            lu=cv2.projectPoints(xyz,np.zeros(3),np.zeros(3),k,d)[0][:,0]
            ru=cv2.projectPoints(xyz,rvec,t,k,d)[0][:,0]
            def points(uv):return [dict(u=float(q[0]),v=float(q[1]),area_px=300,color='blue') for q in uv]
            result=matcher.match(points(lu),points(ru))
            self.assertEqual(len(result['pairs']),2)
            np.testing.assert_allclose([p['xyz_mm'] for p in result['pairs']],xyz,atol=.001)
            self.assertFalse(result['absolute_accuracy_certified'])
            self.assertEqual(result['coordinate_frame'],'physical_left_camera_optical_center')
            self.assertEqual(matcher.match([],[])['pairs'],[])

    def test_invalid_calibration_rejected(self):
        root=Path(__file__).resolve().parents[2]/'output/test_tmp';root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as folder:
            self.assertEqual(Path(folder).resolve().parent,root.resolve())
            path=Path(folder)/'invalid.npz';np.savez(path,K1=np.zeros((3,3)))
            with self.assertRaises(ValueError):CalibratedMarkerMatcher(path)


if __name__=='__main__':unittest.main()
