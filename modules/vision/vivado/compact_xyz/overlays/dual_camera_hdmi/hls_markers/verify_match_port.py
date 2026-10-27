"""Check the native port against the user's marker_stereo.py reference."""
import argparse
from pathlib import Path
import sys
import random
import math
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from marker_stereo import match_markers
from marker_display_control import SparseMatcher
from glove_fast_pc import ExactColorDetector
from marker_detection import load_thresholds
from preview_downsample import load_rgb565

def check(engine,candidates):
    selected,actual=engine.process(candidates)
    expected=match_markers(selected['L'],selected['R'])['pairs']
    assert [(p['left'],p['right'],p['id']) for p in actual]==[(p['left_index'],p['right_index'],p['pair_id']) for p in expected]
    for a,b in zip(actual,expected):
        for key in ('cost','disparity_px','vertical_residual_px'):assert math.isclose(a[key],b[key],rel_tol=1e-12,abs_tol=1e-12),(a,b)
        assert a['xyz_mm'] is None

def main():
    p=argparse.ArgumentParser();p.add_argument('--library',required=True);args=p.parse_args()
    engine=SparseMatcher(Path(args.library).resolve());rng=random.Random(129)
    for frame in range(250):
        points={eye:[] for eye in ('L','R')}
        for i in range(rng.randrange(1,25)):
            u=rng.uniform(220,600);v=rng.uniform(30,680);color=rng.choice(('red','yellow','green','blue'));area=rng.randint(80,1500)
            for eye,x,y in [('L',u,v),('R',u-rng.uniform(20,190),v-4.12+rng.uniform(-8,8))]:
                points[eye].append(dict(color=color,u=x,v=y,area_px=area,bbox=[int(x)-10,int(y)-10,20,20]))
        if frame%5==0:points['R']+=points['R'][:1]
        check(engine,points)
    cfg=load_thresholds(Path(__file__).resolve().parent.parent/'glove_color_thresholds.json');detector=ExactColorDetector(geometry=True)
    samples=sorted(Path('output/glove_preview/live').glob('sample_*.rgb565'))
    for path in samples:
        frame=load_rgb565(path);points={}
        for eye,pixels in [('L',frame[:,640:]),('R',frame[:,:640])]:
            points[eye]=detector.detect(pixels,cfg[eye],cfg['min_area'],cfg['max_area'])[0]
        check(engine,points)
    print('PORT PASS 250 seeded cases + %d real stereo frames: pairs, costs, disparity, vertical residual and XYZ-invalid status'%len(samples))
if __name__=='__main__':main()
