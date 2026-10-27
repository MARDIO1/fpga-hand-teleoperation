#pragma once
#include <ap_int.h>
#include <ap_axi_sdata.h>
#include <hls_stream.h>

constexpr int MAX_WIDTH = 640;
constexpr int MAX_HEIGHT = 720;
constexpr int MAX_LABELS = 2048; // Label 0 is reserved for background.

using Pixel = ap_axiu<16, 1, 1, 1>;
using Packet = ap_axiu<320, 1, 1, 1>;

struct ColorThreshold {
    ap_uint<8> h_min, h_max, s_min, v_min;
};

enum ErrorFlags { BAD_CONFIG = 1, BAD_VIDEO = 2, LABEL_OVERFLOW = 4 };

// One invocation consumes one eye, width*height pixels. USER marks SOF;
// LAST marks every line end. The caller must supply a stable frame config.
void glove_markers(hls::stream<Pixel>& pixels, hls::stream<Packet>& regions,
                   const ColorThreshold thresholds[4], unsigned width, unsigned height,
                   unsigned min_area, unsigned max_area,
                   ap_uint<32> frame_id, ap_uint<64> timestamp_us);

ap_uint<3> classify_pixel(ap_uint<16> pixel, const ColorThreshold thresholds[4]);
