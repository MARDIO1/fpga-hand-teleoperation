"""PS control for PL sparse rectification/triangulation and native candidate matching."""
import ctypes as C
import json,time
from pathlib import Path
import numpy as np
from marker_display_control import SparseMatcher,Point,Pair,Config,COLORS,select_candidates
class GeometryIP:
    def __init__(self):
        from pynq import MMIO
        self.ip=MMIO(0x43c40000,0x10000)
        # Filled from the generated register map at build time.
        self.layout=json.loads(Path(__file__).with_name('geometry_registers.json').read_text())
    def run(self,records,operation):
        n=len(records)
        if n==0:return np.zeros((0,8),np.float64)
        if not 0<n<=128:raise ValueError('geometry point capacity exceeded')
        data=np.zeros((n,8),dtype='<f8');data[:,:np.asarray(records).shape[1]]=records
        offset=self.layout['input']//4
        self.ip.array[offset:offset+n*16]=data.view('<u4').reshape(-1)
        self.ip.write(self.layout['count'],n);self.ip.write(self.layout['operation'],operation);self.ip.write(0,1)
        deadline=time.monotonic()+2
        while not self.ip.read(0)&2:
            if time.monotonic()>deadline:raise RuntimeError('Geometry HLS timeout')
            time.sleep(.0001)
        offset=self.layout['output']//4
        return self.ip.array[offset:offset+n*16].copy().view('<f8').reshape(n,8)
class CalibratedHardwareMatcher(SparseMatcher):
    def __init__(self):
        super().__init__();self.geometry_ip=GeometryIP()
        self.lib.marker_match_rectified.argtypes=self.lib.marker_match.argtypes
        self.lib.marker_match_rectified.restype=C.c_int
        self.config.right_y_shift_px=0.;self.config.max_vertical_error_px=2.5
        self.calibration=json.loads(Path(__file__).with_name('calibration.json').read_text())
    def process(self,candidates):
        selected={e:select_candidates(candidates[e],self.geometry) for e in ('L','R')}
        corrected={}
        for eye,op in [('L',0),('R',1)]:
            points=selected[eye]
            q=self.geometry_ip.run([[p['u'],p['v']] for p in points],op)
            if len(q) and (not np.isfinite(q[:,:2]).all() or not (q[:,2]==1).all()):raise RuntimeError('Invalid rectification')
            corrected[eye]=q
        arrays={e:(Point*128)(*[Point(COLORS.index(p['color'])+1,q[0],q[1],p['area_px']) for p,q in zip(selected[e],corrected[e])]) for e in ('L','R')}
        pairs=(Pair*128)();n=self.lib.marker_match_rectified(arrays['L'],len(selected['L']),arrays['R'],len(selected['R']),pairs,C.byref(self.config))
        if n<0:raise RuntimeError('Invalid calibrated matching input')
        records=[]
        for p in pairs[:n]:
            l=selected['L'][p.left];r=selected['R'][p.right]
            records.append([l['u'],l['v'],r['u'],r['v'],*corrected['L'][p.left,:2],*corrected['R'][p.right,:2]])
        xyz=self.geometry_ip.run(records,2)
        accepted=[]
        for p,q in zip(pairs[:n],xyz):
            if q[4]!=1:continue
            accepted.append(dict(left=int(p.left),right=int(p.right),id=len(accepted)+1,cost=p.cost,
                disparity_px=p.disparity,vertical_residual_px=p.vertical,xyz_valid=True,xyz_mm=q[:3].tolist(),reprojection_error_px=float(q[3]),
                left_rectified_uv=corrected['L'][p.left,:2].tolist(),right_rectified_uv=corrected['R'][p.right,:2].tolist()))
        return selected,accepted
