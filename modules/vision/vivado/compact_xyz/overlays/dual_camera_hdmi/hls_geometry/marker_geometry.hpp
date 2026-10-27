#pragma once
// op 0/1: rectify left/right, inputs u,v in first 2 slots of each stride-8 record.
// op 2: triangulate, input raw Lu,Lv,Ru,Rv,rectified Lu,Lv,Ru,Rv.
// output stride 8: rectified u,v,valid or X,Y,Z,max reprojection error,valid.
void marker_geometry(const double input[1024],double output[1024],unsigned count,unsigned operation);
