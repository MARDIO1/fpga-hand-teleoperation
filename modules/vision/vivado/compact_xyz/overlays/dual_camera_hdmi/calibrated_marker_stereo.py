"""Sparse rectification and experimental XYZ in the physical LEFT camera frame."""

import hashlib
from pathlib import Path

import cv2
import numpy as np

from marker_stereo import DEFAULT_MATCHING, match_markers


class CalibratedMarkerMatcher:
    def __init__(self,path):
        self.path=Path(path)
        with np.load(self.path,allow_pickle=False) as archive:
            self.model={key:archive[key] for key in archive.files}
        model=self.model
        for key,shape in dict(K1=(3,3),K2=(3,3),R=(3,3),R1=(3,3),R2=(3,3),P1=(3,4),P2=(3,4)).items():
            if key not in model or model[key].shape!=shape or not np.isfinite(model[key]).all():
                raise ValueError('Invalid calibration matrix: '+key)
        for key in ('D1','D2','T'):
            if key not in model or not np.isfinite(model[key]).all():
                raise ValueError('Missing/invalid calibration: '+key)
        if (model['T'].size!=3 or any(model[k].size not in (4,5,8,12,14) for k in ('D1','D2'))
                or tuple(model.get('image_size',()))!=(640,720)
                or not 0<float(model.get('square_mm',0))
                or any(model[k][0,0]<=0 or model[k][1,1]<=0 for k in ('K1','K2'))):
            raise ValueError('Calibration dimensions/units do not match the stereo capture')
        self.sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.settings=dict(DEFAULT_MATCHING,right_y_shift_px=0,max_vertical_error_px=2.5)
        self.right_rvec=cv2.Rodrigues(model['R'])[0]

    def match(self,left,right):
        # Validate original detections before moving into unbounded rectified coordinates.
        match_markers(left,right)
        converted=[]
        for n,points in ((1,left),(2,right)):
            if not points:
                converted.append([]);continue
            uv=np.array([[p['u'],p['v']] for p in points],np.float64)[:,None]
            corrected=cv2.undistortPoints(uv,self.model['K'+str(n)],self.model['D'+str(n)],
                          R=self.model['R'+str(n)],P=self.model['P'+str(n)])[:,0]
            if not np.isfinite(corrected).all():raise ValueError('Nonfinite corrected marker coordinates')
            converted.append([dict(p,u=float(q[0]),v=float(q[1])) for p,q in zip(points,corrected)])
        result=match_markers(*converted,settings=self.settings,coordinate_space='rectified')
        accepted=[];rejected=[]
        model=self.model
        for pair in result['pairs']:
            a,b=np.asarray(pair['left_uv'],np.float64),np.asarray(pair['right_uv'],np.float64)
            homogeneous=cv2.triangulatePoints(model['P1'],model['P2'],a[:,None],b[:,None])[:,0]
            if abs(homogeneous[3])<1e-10:
                rejected.append(dict(pair,reason='degenerate_triangulation'));continue
            xyz=model['R1'].T@(homogeneous[:3]/homogeneous[3])
            right_xyz=model['R']@xyz+model['T'].reshape(3)
            if not np.isfinite(xyz).all() or xyz[2]<=0 or right_xyz[2]<=0:
                rejected.append(dict(pair,reason='invalid_depth'));continue
            lp,rp=left[pair['left_index']],right[pair['right_index']]
            projected_l=cv2.projectPoints(xyz[None],np.zeros(3),np.zeros(3),model['K1'],model['D1'])[0][0,0]
            projected_r=cv2.projectPoints(xyz[None],self.right_rvec,model['T'],model['K2'],model['D2'])[0][0,0]
            error=max(float(np.linalg.norm(projected_l-[lp['u'],lp['v']])),
                      float(np.linalg.norm(projected_r-[rp['u'],rp['v']])))
            if error>2:
                rejected.append(dict(pair,reason='reprojection_error',reprojection_error_px=error));continue
            pair.update(left_rectified_uv=pair['left_uv'],right_rectified_uv=pair['right_uv'],
                        left_uv=[lp['u'],lp['v']],right_uv=[rp['u'],rp['v']],xyz_mm=xyz.tolist(),
                        reprojection_error_px=error,pair_id=len(accepted)+1)
            accepted.append(pair)
        result['pairs']=accepted
        used_l={p['left_index'] for p in accepted};used_r={p['right_index'] for p in accepted}
        result['unmatched_left']=[i for i in range(len(left)) if i not in used_l]
        result['unmatched_right']=[i for i in range(len(right)) if i not in used_r]
        result.pop('metric_valid',None)
        result.update(rejected_triangulations=rejected,geometry_status='sparse_calibrated_rectification',
                      metric_coordinates_available=True,absolute_accuracy_certified=False,
                      calibration_scope='user_accepted_PC_experiment',calibration_sha256=self.sha256,
                      coordinate_frame='physical_left_camera_optical_center',units='mm',
                      axes='X right, Y down, Z forward',exposure_timestamp_us=None)
        return result
