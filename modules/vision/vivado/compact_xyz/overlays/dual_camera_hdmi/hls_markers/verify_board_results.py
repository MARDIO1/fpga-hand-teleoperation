"""Compare an on-board HLS candidate table to the independent PC reference."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from glove_rle_reference import detect_rle_markers

def canonical(points):
    return sorted((p['color'],p['area_px'],p['sum_x'],p['sum_y'],tuple(p['bbox'])) for p in points)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('raw');p.add_argument('result');p.add_argument('--thresholds',default=str(Path(__file__).resolve().parent.parent/'glove_color_thresholds.json'))
    args=p.parse_args()
    frame=np.fromfile(args.raw,dtype='<u2').reshape(720,1280)
    result=json.loads(Path(args.result).read_text());cfg=json.loads(Path(args.thresholds).read_text())
    for eye,pixels in [('L',frame[:,640:]),('R',frame[:,:640])]:
        expected,_,_=detect_rle_markers(pixels,cfg[eye],cfg['min_area'],cfg['max_area'])
        actual=result['candidates'][eye]
        assert canonical(actual)==canonical(expected),(eye,canonical(actual),canonical(expected))
        print('%s PASS %d hardware regions match reference exactly'%(eye,len(actual)))
if __name__=='__main__':main()
