#include "marker_match.hpp"
#include <cmath>
#include <limits>
static bool valid(const MarkerPoint& p,bool rectified){return p.color>=1&&p.color<=4&&std::isfinite(p.u)&&(rectified||(p.u>=0&&p.u<640))&&std::isfinite(p.v)&&(rectified||(p.v>=0&&p.v<720))&&std::isfinite(p.area)&&p.area>0&&p.area<=640*720;}
static int match_impl(const MarkerPoint* l,unsigned nl,const MarkerPoint* r,unsigned nr,MarkerPair* out,const MatchConfig* c,bool rectified){
 if(!l||!r||!out||!c||nl>128||nr>128)return -1;
 if(!std::isfinite(c->right_y_shift_px)||!std::isfinite(c->max_vertical_error_px)||!std::isfinite(c->min_disparity_px)||!std::isfinite(c->max_disparity_px)||!std::isfinite(c->max_area_ratio)||!std::isfinite(c->uniqueness_margin)||c->max_vertical_error_px<=0||c->max_area_ratio<=1||c->uniqueness_margin<=0||c->min_disparity_px<0||c->min_disparity_px>c->max_disparity_px||c->max_disparity_px>639)return -1;
 for(unsigned i=0;i<nl;++i)if(!valid(l[i],rectified))return -1;
 for(unsigned j=0;j<nr;++j)if(!valid(r[j],rectified))return -1;
 const double inf=std::numeric_limits<double>::infinity();
 double costs[128][128];int lb[128],rb[128];
 for(unsigned i=0;i<nl;++i)for(unsigned j=0;j<nr;++j){
  costs[i][j]=inf;if(l[i].color!=r[j].color)continue;
  double d=l[i].u-r[j].u,dy=l[i].v-(r[j].v+c->right_y_shift_px);
  double ratio=(l[i].area>r[j].area?l[i].area:r[j].area)/(l[i].area<r[j].area?l[i].area:r[j].area);
  if(d<c->min_disparity_px||d>c->max_disparity_px||std::abs(dy)>c->max_vertical_error_px||ratio>c->max_area_ratio)continue;
  costs[i][j]=std::abs(dy)/c->max_vertical_error_px+0.35*std::log(ratio)/std::log(c->max_area_ratio);
 }
 for(unsigned i=0;i<nl;++i){double best=inf,second=inf;int index=-1;
  for(unsigned j=0;j<nr;++j){double v=costs[i][j];if(v<best){second=best;best=v;index=j;}else if(v<second)second=v;}
  lb[i]=(index>=0&&second-best>=c->uniqueness_margin)?index:-1;
 }
 for(unsigned j=0;j<nr;++j){double best=inf,second=inf;int index=-1;
  for(unsigned i=0;i<nl;++i){double v=costs[i][j];if(v<best){second=best;best=v;index=i;}else if(v<second)second=v;}
  rb[j]=(index>=0&&second-best>=c->uniqueness_margin)?index:-1;
 }
 unsigned n=0;
 for(unsigned i=0;i<nl;++i){int j=lb[i];if(j<0||rb[j]!=int(i))continue;
  out[n]={i,unsigned(j),n+1,costs[i][j],l[i].u-r[j].u,l[i].v-(r[j].v+c->right_y_shift_px)};++n;
 }
 return n;
}

extern "C" int marker_match(const MarkerPoint* l,unsigned nl,const MarkerPoint* r,unsigned nr,MarkerPair* out,const MatchConfig* c){return match_impl(l,nl,r,nr,out,c,false);}
extern "C" int marker_match_rectified(const MarkerPoint* l,unsigned nl,const MarkerPoint* r,unsigned nr,MarkerPair* out,const MatchConfig* c){return match_impl(l,nl,r,nr,out,c,true);}
