#include "marker_geometry.hpp"
#include "calibration.hpp"
#include <cmath>
static void rectify(double u,double v,int eye,double& ru,double& rv){
#pragma HLS INLINE
 const double* k=eye?C_K2:C_K1;const double* d=eye?C_D2:C_D1;
 const double* r=eye?C_R2:C_R1;const double* p=eye?C_P2:C_P1;
 double x0=(u-k[2])/k[0],y0=(v-k[5])/k[4],x=x0,y=y0;
 for(int i=0;i<5;++i){
  double rr=x*x+y*y;
  double inverse=1./(1.+((d[4]*rr+d[1])*rr+d[0])*rr);
  if(inverse<0){x=x0;y=y0;break;}
  double dx=2*d[2]*x*y+d[3]*(rr+2*x*x),dy=d[2]*(rr+2*y*y)+2*d[3]*x*y;
  x=(x0-dx)*inverse;y=(y0-dy)*inverse;
 }
 double a=r[0]*x+r[1]*y+r[2],b=r[3]*x+r[4]*y+r[5],c=r[6]*x+r[7]*y+r[8];
 ru=p[0]*a/c+p[2];rv=p[5]*b/c+p[6];
}
static void project(const double xyz[3],int eye,double& u,double& v){
#pragma HLS INLINE
 double a=xyz[0],b=xyz[1],c=xyz[2];
 if(eye){a=C_R[0]*xyz[0]+C_R[1]*xyz[1]+C_R[2]*xyz[2]+C_T[0];b=C_R[3]*xyz[0]+C_R[4]*xyz[1]+C_R[5]*xyz[2]+C_T[1];c=C_R[6]*xyz[0]+C_R[7]*xyz[1]+C_R[8]*xyz[2]+C_T[2];}
 const double* k=eye?C_K2:C_K1;const double* d=eye?C_D2:C_D1;
 double x=a/c,y=b/c,rr=x*x+y*y,radial=1+((d[4]*rr+d[1])*rr+d[0])*rr;
 u=k[0]*(x*radial+2*d[2]*x*y+d[3]*(rr+2*x*x))+k[2];
 v=k[4]*(y*radial+d[2]*(rr+2*y*y)+2*d[3]*x*y)+k[5];
}
static void triangulate(const double in[8],double out[8]){
#pragma HLS INLINE
 // Smallest right singular vector of the same 4x4 DLT matrix as OpenCV.
 double a[4][4],n[4][4],e[4][4];
 for(int row=0;row<4;++row)for(int col=0;col<4;++col){
  const double* p=row<2?C_P1:C_P2;int axis=row%2;
  a[row][col]=in[4+row]*p[8+col]-p[axis*4+col];
  e[row][col]=row==col?1.:0.;n[row][col]=0;
 }
 for(int i=0;i<4;++i)for(int j=0;j<4;++j)for(int k=0;k<4;++k)n[i][j]+=a[k][i]*a[k][j];
 for(int sweep=0;sweep<12;++sweep)for(int p=0;p<3;++p)for(int q=p+1;q<4;++q){
  double off=n[p][q];
  if(std::abs(off)>1e-16){
   double tau=(n[q][q]-n[p][p])/(2*off);
   double t=(tau>=0?1.:-1.)/(std::abs(tau)+std::sqrt(1+tau*tau));
   double c=1./std::sqrt(1+t*t),s=t*c;
   double pp=n[p][p],qq=n[q][q];
   n[p][p]=pp-t*off;n[q][q]=qq+t*off;n[p][q]=n[q][p]=0;
   for(int k=0;k<4;++k){
    if(k!=p&&k!=q){double kp=n[k][p],kq=n[k][q];n[k][p]=n[p][k]=c*kp-s*kq;n[k][q]=n[q][k]=s*kp+c*kq;}
    double ep=e[k][p],eq=e[k][q];e[k][p]=c*ep-s*eq;e[k][q]=s*ep+c*eq;
   }
  }
 }
 int index=0;for(int i=1;i<4;++i)if(n[i][i]<n[index][index])index=i;
 if(std::abs(e[3][index])<1e-10)return;
 double rect[3],xyz[3];for(int i=0;i<3;++i)rect[i]=e[i][index]/e[3][index];
 for(int i=0;i<3;++i){xyz[i]=0;for(int j=0;j<3;++j)xyz[i]+=C_R1[j*3+i]*rect[j];out[i]=xyz[i];}
 double rz=C_R[6]*xyz[0]+C_R[7]*xyz[1]+C_R[8]*xyz[2]+C_T[2];
 double lu,lv,ru,rv;project(xyz,0,lu,lv);project(xyz,1,ru,rv);
 double le=(lu-in[0])*(lu-in[0])+(lv-in[1])*(lv-in[1]);
 double re=(ru-in[2])*(ru-in[2])+(rv-in[3])*(rv-in[3]);
 out[3]=std::sqrt(le>re?le:re);
 out[4]=(std::isfinite(xyz[0])&&std::isfinite(xyz[1])&&std::isfinite(xyz[2])&&xyz[2]>0&&rz>0&&out[3]<=2)?1:0;
}
void marker_geometry(const double input[1024],double output[1024],unsigned count,unsigned operation){
#pragma HLS INTERFACE s_axilite port=input bundle=control
#pragma HLS INTERFACE s_axilite port=output bundle=control
#pragma HLS INTERFACE s_axilite port=count bundle=control
#pragma HLS INTERFACE s_axilite port=operation bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS ALLOCATION operation instances=dmul limit=1
#pragma HLS ALLOCATION operation instances=dadd limit=1
#pragma HLS ALLOCATION operation instances=dsub limit=1
#pragma HLS ALLOCATION operation instances=ddiv limit=1
 if(count>128||operation>2)return;
 for(unsigned i=0;i<count;++i){
#pragma HLS LOOP_TRIPCOUNT min=0 max=128
  double in[8],out[8];for(int j=0;j<8;++j){in[j]=input[i*8+j];out[j]=0;}
  if(operation<2){rectify(in[0],in[1],operation,out[0],out[1]);out[2]=std::isfinite(out[0])&&std::isfinite(out[1]);}
  else triangulate(in,out);
  for(int j=0;j<8;++j)output[i*8+j]=out[j];
 }
}
