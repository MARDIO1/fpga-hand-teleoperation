"""C++ sparse matching and HLS HDMI display control. Candidate filtering stays external."""
import ctypes as C
from pathlib import Path
import threading
import time
import numpy as np

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from marker_stereo import DEFAULT_MATCHING
import json

class Point(C.Structure):
    _fields_=[('color',C.c_uint32)]+[(k,C.c_double) for k in ('u','v','area')]
class Pair(C.Structure):
    _fields_=[(k,C.c_uint32) for k in ('left','right','id')]+[(k,C.c_double) for k in ('cost','disparity','vertical')]
class Config(C.Structure):
    _fields_=[(k,C.c_double) for k in ('right_y_shift_px','max_vertical_error_px','min_disparity_px','max_disparity_px','max_area_ratio','uniqueness_margin')]
COLORS=('red','yellow','green','blue')
RGB={'red':0xf800,'yellow':0xffe0,'green':0x07e0,'blue':0x001f}

def select_candidates(points,spec):
    # Replace this boundary when the user's improved selector is ready.
    return [p for p in points if spec['min_width_px']<=p['bbox'][2]<=spec['max_width_px']
        and spec['min_height_px']<=p['bbox'][3]<=spec['max_height_px']
        and p['bbox'][2]<=spec['max_aspect_ratio']*p['bbox'][3]
        and p['bbox'][3]<=spec['max_aspect_ratio']*p['bbox'][2]]

class SparseMatcher:
    def __init__(self,library=None):
        self.lib=C.CDLL(str(library or Path(__file__).with_name('libmarker_match.so')))
        self.lib.marker_match.argtypes=[C.POINTER(Point),C.c_uint,C.POINTER(Point),C.c_uint,C.POINTER(Pair),C.POINTER(Config)]
        self.lib.marker_match.restype=C.c_int
        self.config=Config(**DEFAULT_MATCHING)
        self.geometry=json.loads(Path(__file__).with_name('geometry_spec.json').read_text())
    def process(self,candidates):
        selected={eye:select_candidates(candidates[eye],self.geometry) for eye in ('L','R')}
        if any(len(v)>128 for v in selected.values()):raise RuntimeError('Too many candidates for sparse matching')
        arrays={eye:(Point*128)(*[Point(COLORS.index(p['color'])+1,p['u'],p['v'],p['area_px']) for p in selected[eye]]) for eye in ('L','R')}
        output=(Pair*128)()
        count=self.lib.marker_match(arrays['L'],len(selected['L']),arrays['R'],len(selected['R']),output,C.byref(self.config))
        if count<0:raise RuntimeError('C++ matching rejected input')
        matches=[dict(left=int(p.left),right=int(p.right),id=int(p.id),cost=p.cost,
            disparity_px=p.disparity,vertical_residual_px=p.vertical,xyz_valid=False,xyz_mm=None) for p in output[:count]]
        return selected,matches

class DisplayController:
    def __init__(self,initial_results=False):
        from pynq import MMIO
        self.mmio=MMIO(0x43c30000,0x10000)
        self.button=MMIO(0x41230000,0x1000)
        self.page=initial_results;self.sequence=0;self.commit=0;self.data=None;self.error=None
        self.lock=threading.Lock();self.running=True
        self.commit=self.mmio.read(0x10);self.sequence=self.commit>>2
        self.mmio.write(0,0x81)
        self.thread=threading.Thread(target=self.worker,daemon=True);self.thread.start()
    def update(self,selected,matches,sequence,timestamp,pair_ms,errors=0,capture_fps=0.0,recognition_fps=0.0,calibrated=False):
        with self.lock:self.data=(selected,matches,sequence,timestamp,pair_ms,errors,capture_fps,recognition_fps,calibrated)
        if self.error:raise RuntimeError('HDMI publisher failed: '+self.error)
    def publish(self,data,page):
        if self.mmio.read(0x18)!=self.commit:return False
        selected,matches,sequence,timestamp,pair_ms=data[:5]
        errors=data[5] if len(data)>5 else 0
        bank=1-(self.commit&1);boxes=np.zeros(128,dtype=np.uint32)
        ids={eye:{} for eye in ('L','R')}
        for p in matches:
            ids['L'][p['left']]=p['id'];ids['R'][p['right']]=p['id']
        index=0
        for eye in ('R','L'):
            offset=640 if eye=='L' else 0
            for i,p in enumerate(selected[eye][:16]):
                x,y,w,h=p['bbox'];cx,cy=round(p['u']),round(p['v'])
                boxes[index*4:index*4+4]=[x+offset|(y<<16),x+offset+w-1|((y+h-1)<<16),cx+offset|(cy<<16),0x80000000|(ids[eye].get(i,0)<<16)|RGB[p['color']]]
                index+=1
        age_ms=max(0,(time.monotonic()*1000000-timestamp)/1000)
        rows=['PAGE 2  PL MARKERS / CPP STEREO  FRAME %d  XYZ UNCAL  PUBLISH AGE %.0f MS  PROCESS %.0f MS'%(sequence,age_ms,pair_ms),
              'PAIRS %d  CANDIDATES L=%d R=%d  IDS ARE FRAME LOCAL  LIVE BACKGROUND / DELAYED DETECTIONS'%(len(matches),len(selected['L']),len(selected['R']))]
        if errors:
            rows[0]='PAGE 2 FRAME INVALID  ERROR %d  LABEL OVERFLOW OR INPUT PROTOCOL  NEXT FRAME CONTINUES  XYZ UNCAL'%errors
        capture_fps=data[6] if len(data)>6 else 0.0
        recognition_fps=data[7] if len(data)>7 else 0.0
        rows[0]+='  CAP FPS %.1f  DET FPS %.1f'%(capture_fps,recognition_fps)
        calibrated=data[8] if len(data)>8 else False
        if calibrated:rows[0]=rows[0].replace('XYZ UNCAL','XYZ EXP MM')
        entries=[]
        for p in matches:
            l=selected['L'][p['left']];r=selected['R'][p['right']]
            if p.get('xyz_valid') and p.get('xyz_mm') is not None:
                x,y,z=p['xyz_mm']
                entries.append('P%02d %s X %+.1f Y %+.1f Z %.1f MM'%(p['id'],l['color'].upper(),x,y,z))
                continue
            entries.append('P%02d %s L %.1f %.1f R %.1f %.1f D %.1f XYZ:UNCAL'%(p['id'],l['color'].upper(),l['u'],l['v'],r['u'],r['v'],p.get('disparity_px',l['u']-r['u'])))
        for i in range(6):
            a=entries[i] if i<len(entries) else ''
            b=entries[i+6] if i+6<len(entries) else ''
            rows.append(a[:80].ljust(80)+b[:80].ljust(80))
        text=''.join(row[:160].ljust(160) for row in rows).encode('ascii','replace')
        text_words=np.frombuffer(text,dtype='<u4')
        self.mmio.array[0x400//4+bank*128:0x400//4+(bank+1)*128]=boxes
        self.mmio.array[0x1000//4+bank*320:0x1000//4+(bank+1)*320]=text_words
        self.sequence+=1;self.commit=(self.sequence<<2)|(int(page)<<1)|bank
        self.mmio.write(0x10,self.commit)
        return True
    def worker(self):
        previous=stable=bool(self.button.read(0)&1);changed=time.monotonic()
        sent=None
        try:
            while self.running:
                now=time.monotonic();level=bool(self.button.read(0)&1)
                if level!=previous:previous=level;changed=now
                if level!=stable and now-changed>=.035:
                    stable=level
                    if not stable:self.page=not self.page;print('S2 HDMI page=%d'%(2 if self.page else 1),flush=True)
                with self.lock:data=self.data
                if data is not None:
                    version=(data[2],self.page)
                    if version!=sent and self.publish(data,self.page):sent=version
                time.sleep(.008)
        except Exception as exc:self.error=str(exc)
    def close(self):
        self.running=False;self.thread.join(timeout=1)
