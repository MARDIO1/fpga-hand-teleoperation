#pragma once
#include <stdint.h>
struct MarkerPoint {uint32_t color;double u,v,area;};
struct MarkerPair {uint32_t left,right,id;double cost,disparity,vertical;};
struct MatchConfig {double right_y_shift_px,max_vertical_error_px,min_disparity_px,max_disparity_px,max_area_ratio,uniqueness_margin;};
// Exact double-precision port of marker_stereo.py; negative result means invalid/capacity error.
extern "C" int marker_match(const MarkerPoint*,unsigned,const MarkerPoint*,unsigned,MarkerPair*,const MatchConfig*);
