"""Display candidate tables produced by the board's HLS core; no PC detection."""
import argparse
import json
from pathlib import Path
import sys
import time
import cv2
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
sys.path.insert(0,str(HERE.parents[2]/'scripts'))
from board_ssh import paramiko,HOST,USER,PASSWORD
from marker_detection import draw_candidates
from preview_downsample import rgb565_bgr
from marker_transport import decode_snapshot

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default=HOST)
    parser.add_argument('--remote',default='/dev/shm/marker_results/latest.bin',help='requires board --snapshot-fps > 0; old NPZ supported')
    parser.add_argument('--output',default='output/glove_preview/pl_live')
    parser.add_argument('--frames',type=int,default=0)
    parser.add_argument('--headless',action='store_true')
    args=parser.parse_args()
    if args.headless and args.frames<=0: parser.error('headless requires finite --frames')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    c=paramiko.SSHClient();c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(args.host,username=USER,password=PASSWORD,timeout=15)
    count=0;last=None
    try:
        with c.open_sftp() as sftp:
            while args.frames==0 or count<args.frames:
                with sftp.open(args.remote,'rb') as stream:
                    stream.prefetch();data=stream.read()
                frame,result=decode_snapshot(data)
                sequence=result['snapshot_sequence']
                if sequence==last:
                    if not args.headless and cv2.waitKey(10)&255 in (27,ord('q')): break
                    time.sleep(0.05);continue
                last=sequence
                image=rgb565_bgr(frame)
                points={eye:[dict(p) for p in result.get('selected',result['candidates'])[eye]] for eye in ('L','R')}
                for match in result.get('matches',[]):
                    points['L'][match['left']]['label']='P'+str(match['id'])
                    points['R'][match['right']]['label']='P'+str(match['id'])
                left=draw_candidates(image[:,640:],points['L'],'L')
                right=draw_candidates(image[:,:640],points['R'],'R')
                preview=np.vstack((np.zeros((55,1280,3),np.uint8),np.hstack((left,right))))
                cv2.putText(preview,'PL HLS color + RLE-CCL | PS centroids | frame %d | pair %.1f ms'%(sequence,result['total_pair_ms']),(10,23),cv2.FONT_HERSHEY_SIMPLEX,0.58,(255,255,255),1)
                cv2.putText(preview,'CAP %.1f FPS | DET %.1f FPS | PAIRS %d | XYZ %s | Q/Esc quit'%(result.get('capture_fps',0),result.get('recognition_fps',0),len(result.get('matches',[])),'EXPERIMENTAL MM' if result.get('metric_coordinates_available') else 'UNCAL'),(10,46),cv2.FONT_HERSHEY_SIMPLEX,0.5,(200,200,200),1)
                if result.get('metric_coordinates_available'):
                    lines=['XYZ EXPERIMENTAL [MM]  LEFT CAMERA: X RIGHT / Y DOWN / Z FORWARD']
                    for match in result.get('matches',[]):
                        if match.get('xyz_valid'):
                            x,y,z=match['xyz_mm']
                            lines.append('P%02d X %+.1f Y %+.1f Z %.1f  REPROJ %.3f PX'%(match['id'],x,y,z,match.get('reprojection_error_px',0)))
                    footer=np.zeros((24*len(lines)+8,1280,3),np.uint8)
                    for i,line in enumerate(lines):cv2.putText(footer,line,(10,22+24*i),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),1)
                    preview=np.vstack((preview,footer))
                cv2.imwrite(str(output/'latest_preview.png'),preview)
                cv2.imwrite(str(output/'latest_raw.png'),image)
                (output/'latest.json').write_text(json.dumps(result,indent=2))
                print('frame=%d L=%d R=%d pair_ms=%.1f'%(sequence,len(result['candidates']['L']),len(result['candidates']['R']),result['total_pair_ms']),flush=True)
                count+=1
                if not args.headless:
                    cv2.imshow('PL markers - board recognition',preview)
                    if cv2.waitKey(1)&255 in (27,ord('q')): break
    finally:
        c.close();cv2.destroyAllWindows()
if __name__=='__main__': main()
