"""Compare board-produced calibrated XYZ to the PC calibration reference."""
from pathlib import Path
import sys,json,argparse
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from calibrated_marker_stereo import CalibratedMarkerMatcher
from glove_fast_pc import ExactColorDetector
from marker_detection import load_thresholds
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'hls_markers'))
from marker_transport import decode_snapshot

def main():
 p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--calibration',default='../../data/samples/compact_xyz/candidate_calibration.npz');a=p.parse_args()
 frame,actual=decode_snapshot(Path(a.archive).read_bytes())
 cfg=load_thresholds('overlays/dual_camera_hdmi/glove_color_thresholds.json');detector=ExactColorDetector(geometry=True);points={}
 for e,pixels in [('L',frame[:,640:]),('R',frame[:,:640])]:
  points[e]=detector.detect(pixels,cfg[e],cfg['min_area'],cfg['max_area'])[0]
  key=lambda p:(p['color'],p['area_px'],p['sum_x'],p['sum_y'],tuple(p['bbox']))
  assert [key(p) for p in points[e]]==[key(p) for p in actual['selected'][e]],e
 expected=CalibratedMarkerMatcher(a.calibration).match(points['L'],points['R'])
 assert [(p['left_index'],p['right_index']) for p in expected['pairs']]==[(p['left'],p['right']) for p in actual['matches']]
 errors=[]
 for e,b in zip(expected['pairs'],actual['matches']):
  np.testing.assert_allclose(e['xyz_mm'],b['xyz_mm'],rtol=0,atol=.01)
  assert abs(e['reprojection_error_px']-b['reprojection_error_px'])<1e-5
  errors.append(float(np.max(np.abs(np.array(e['xyz_mm'])-b['xyz_mm']))))
 print(json.dumps(dict(status='PASS',pairs=len(errors),maximum_xyz_difference_mm=max(errors,default=0),frame=actual['snapshot_sequence'],capture_fps=actual.get('capture_fps'),recognition_fps=actual.get('recognition_fps'),pair_ms=actual['total_pair_ms'])))
if __name__=='__main__':main()
