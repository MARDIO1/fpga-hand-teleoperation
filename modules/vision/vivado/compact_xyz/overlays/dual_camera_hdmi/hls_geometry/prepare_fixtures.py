from pathlib import Path
import cv2,numpy as np
root=Path(__file__).resolve().parents[3];out=root/'output/hls_geometry';out.mkdir(parents=True,exist_ok=True)
a=np.load(root/'../../data/samples/compact_xyz/candidate_calibration.npz')
rng=np.random.default_rng(233);batches=[]
for eye in [1,2]:
 uv=np.column_stack((rng.uniform(0,639,128),rng.uniform(0,719,128)))
 q=cv2.undistortPoints(uv[:,None],a['K'+str(eye)],a['D'+str(eye)],R=a['R'+str(eye)],P=a['P'+str(eye)])[:,0]
 inp=np.zeros((128,8));inp[:,:2]=uv;expected=np.zeros((128,8));expected[:,:2]=q;expected[:,2]=1
 batches.append((eye-1,inp,expected))
xyz=np.column_stack((rng.uniform(-10,160,128),rng.uniform(-100,100,128),rng.uniform(350,1000,128)))
lu=cv2.projectPoints(xyz,np.zeros(3),np.zeros(3),a['K1'],a['D1'])[0][:,0]
ru=cv2.projectPoints(xyz,cv2.Rodrigues(a['R'])[0],a['T'],a['K2'],a['D2'])[0][:,0]
ru[:,1]+=rng.uniform(-3,3,128)
lq=cv2.undistortPoints(lu[:,None],a['K1'],a['D1'],R=a['R1'],P=a['P1'])[:,0]
rq=cv2.undistortPoints(ru[:,None],a['K2'],a['D2'],R=a['R2'],P=a['P2'])[:,0]
h=cv2.triangulatePoints(a['P1'],a['P2'],lq.T,rq.T);x=(a['R1'].T@(h[:3]/h[3])).T
pl=cv2.projectPoints(x,np.zeros(3),np.zeros(3),a['K1'],a['D1'])[0][:,0]
pr=cv2.projectPoints(x,cv2.Rodrigues(a['R'])[0],a['T'],a['K2'],a['D2'])[0][:,0]
error=np.maximum(np.linalg.norm(pl-lu,axis=1),np.linalg.norm(pr-ru,axis=1))
expected=np.zeros((128,8));expected[:,:3]=x;expected[:,3]=error;expected[:,4]=(error<=2)&(x[:,2]>0)&((x@a['R'].T+a['T'].reshape(3))[:,2]>0)
batches.append((2,np.column_stack((lu,ru,lq,rq)),expected))
with (out/'fixtures.txt').open('w') as f:
 f.write(str(len(batches))+'\n')
 for op,inp,exp in batches:
  f.write('%d %d\n'%(len(inp),op));np.savetxt(f,inp,fmt='%.17g');np.savetxt(f,exp,fmt='%.17g')
print('wrote geometry fixtures',out/'fixtures.txt')
