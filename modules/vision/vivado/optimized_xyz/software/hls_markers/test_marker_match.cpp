#include "marker_match.hpp"
#include <cassert>
#include <iostream>
int main(){
 MatchConfig c={4.12,6,20,190,4,.15};MarkerPair p[128];
 MarkerPoint l[2]={{4,200,100,300},{4,250,180,300}},r[2]={{4,100,96,300},{4,150,176,300}};
 assert(marker_match(l,2,r,2,p,&c)==2);assert(p[0].right==0&&p[1].right==1);
 MarkerPoint a[2]={{4,100,96,300},{4,110,96,300}};
 assert(marker_match(l,1,a,2,p,&c)==0);assert(marker_match(l,129,r,2,p,&c)==-1);
 std::cout<<"MATCH PASS PC-reference settings repeated colors ambiguity and bounds\n";
}
