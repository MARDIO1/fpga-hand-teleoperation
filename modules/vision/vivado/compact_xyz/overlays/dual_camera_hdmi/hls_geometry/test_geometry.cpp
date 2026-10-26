#include "marker_geometry.hpp"
#include <fstream>
#include <iostream>
#include <cmath>
#include <cstdlib>
int main(int argc,char** argv){
 if(argc!=2)return 2;std::ifstream f(argv[1]);unsigned batches;f>>batches;
 double input[1024]={},output[1024]={};double max_error=0;
 for(unsigned b=0;b<batches;++b){unsigned count,op;f>>count>>op;
  for(unsigned i=0;i<count*8;++i)f>>input[i];
  marker_geometry(input,output,count,op);
  for(unsigned i=0;i<count;++i)for(int j=0;j<8;++j){double expected;f>>expected;
   double error=std::abs(output[i*8+j]-expected);if(error>max_error)max_error=error;
   double tolerance=op==2?.01:1e-7;
   if(!std::isfinite(output[i*8+j])||error>tolerance){std::cerr<<"FAIL batch "<<b<<" item "<<i<<" field "<<j<<" actual "<<output[i*8+j]<<" expected "<<expected<<" error "<<error<<"\n";return 1;}
  }
 }
 if(!f)return 3;std::cout<<"GEOMETRY PASS "<<batches<<" batches max error "<<max_error<<" (rectification px / XYZ mm)\n";
}
