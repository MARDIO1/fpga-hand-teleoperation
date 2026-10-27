#include "marker_geometry.hpp"
extern "C" void geometry_native(const double* input,double* output,unsigned count,unsigned operation){marker_geometry(input,output,count,operation);}
