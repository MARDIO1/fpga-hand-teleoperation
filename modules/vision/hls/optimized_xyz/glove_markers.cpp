#include "glove_markers.hpp"

struct Run {
    ap_uint<10> first, last, y;
    ap_uint<3> color;
    ap_uint<1> end;
    ap_uint<3> errors;
};

struct Region {
    ap_uint<3> color;
    ap_uint<19> area;
    ap_uint<28> sum_x, sum_y;
    ap_uint<10> xmin, xmax, ymin, ymax;
};

ap_uint<3> classify_pixel(ap_uint<16> pixel, const ColorThreshold thresholds[4]) {
#pragma HLS INLINE
    unsigned r = ((pixel.to_uint() >> 11) & 31) << 3;
    unsigned g = ((pixel.to_uint() >> 5) & 63) << 2;
    unsigned b = (pixel.to_uint() & 31) << 3;
    unsigned maximum = r > g ? r : g;
    maximum = maximum > b ? maximum : b;
    unsigned minimum = r < g ? r : g;
    minimum = minimum < b ? minimum : b;
    unsigned delta = maximum - minimum;
    unsigned h = 0;
    unsigned s = 0;
    if (delta != 0) {
        int numerator = maximum == r ? 30 * (int(g) - int(b)) :
                        maximum == g ? 30 * (int(b) - int(r)) + 60 * int(delta) :
                                       30 * (int(r) - int(g)) + 120 * int(delta);
        if (numerator < 0) numerator += 180 * delta;
        // Exact integer golden-model rounding. Resource cost is measured in HLS.
        ap_uint<16> hn = unsigned(numerator) + delta / 2;
        ap_uint<8> hd = delta;
        h = (hn / hd).to_uint();
        if (h >= 180) h -= 180;
    }
    if (maximum != 0) {
        ap_uint<16> sn = 255 * delta + maximum / 2;
        ap_uint<8> sd = maximum;
        s = (sn / sd).to_uint();
    }
    ap_uint<3> result = 0;
    for (int i = 0; i < 4; ++i) {
#pragma HLS UNROLL
        bool hue = thresholds[i].h_min <= thresholds[i].h_max ?
            h >= thresholds[i].h_min && h <= thresholds[i].h_max :
            h >= thresholds[i].h_min || h <= thresholds[i].h_max;
        if (result == 0 && hue && s >= thresholds[i].s_min && maximum >= thresholds[i].v_min)
            result = i + 1;
    }
    return result;
}

static void make_runs(hls::stream<Pixel>& pixels, hls::stream<Run>& runs,
                      const ColorThreshold thresholds[4], unsigned width, unsigned height) {
    ap_uint<3> errors = 0;
    for (unsigned y = 0; y < height; ++y) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=720
        ap_uint<3> previous = 0;
        unsigned start = 0;
        for (unsigned x = 0; x <= width; ++x) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=2 max=641
            // The sentinel flushes the last run without a second write in one iteration.
            ap_uint<3> color = 0;
            if (x < width) {
                Pixel input = pixels.read();
                if (bool(input.user) != (x == 0 && y == 0) || bool(input.last) != (x + 1 == width)
                        || input.keep != 3 || input.strb != 3)
                    errors |= BAD_VIDEO;
                color = classify_pixel(input.data, thresholds);
            }
            if (color != previous) {
                if (previous != 0) {
                    Run run = {start, x - 1, y, previous, 0, 0};
                    runs.write(run);
                }
                previous = color;
                start = x;
            }
        }
    }
    Run end = {0, 0, 0, 0, 1, errors};
    runs.write(end);
}

using Label = ap_uint<12>;
struct RowRun { ap_uint<10> first, last; ap_uint<3> color; Label label; };

static Label find_root(Label label, Label parent[MAX_LABELS]) {
#pragma HLS INLINE off
    for (int depth = 0; depth < MAX_LABELS; ++depth) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=2048
        Label next = parent[label];
        if (next == label) break;
        label = next;
    }
    return label;
}

static Region add_regions(Region a, Region b) {
#pragma HLS INLINE
    a.area += b.area;
    a.sum_x += b.sum_x;
    a.sum_y += b.sum_y;
    if (b.xmin < a.xmin) a.xmin = b.xmin;
    if (b.xmax > a.xmax) a.xmax = b.xmax;
    if (b.ymin < a.ymin) a.ymin = b.ymin;
    if (b.ymax > a.ymax) a.ymax = b.ymax;
    return a;
}

static Packet packet(bool summary, unsigned flags, unsigned color, unsigned area,
                     unsigned sx, unsigned sy, unsigned xmin, unsigned ymin,
                     unsigned xmax, unsigned ymax, ap_uint<32> frame_id,
                     ap_uint<64> timestamp, unsigned count) {
#pragma HLS INLINE
    Packet output;
    output.data = 0;
    output.data.range(7, 0) = summary;
    output.data.range(15, 8) = color;
    output.data.range(31, 16) = flags;
    output.data.range(63, 32) = area;
    output.data.range(95, 64) = sx;
    output.data.range(127, 96) = sy;
    output.data.range(143, 128) = xmin;
    output.data.range(159, 144) = ymin;
    output.data.range(175, 160) = xmax;
    output.data.range(191, 176) = ymax;
    output.data.range(223, 192) = frame_id;
    output.data.range(287, 224) = timestamp;
    output.data.range(319, 288) = count;
    output.keep = -1;
    output.strb = -1;
    output.user = summary;
    output.last = summary;
    output.id = 0;
    output.dest = 0;
    return output;
}

static void label_runs(hls::stream<Run>& runs, hls::stream<Packet>& output,
                       unsigned width, unsigned height, unsigned min_area, unsigned max_area,
                       ap_uint<32> frame_id, ap_uint<64> timestamp) {
    static Label parent[MAX_LABELS];
    static Region table[MAX_LABELS];
    static RowRun previous[MAX_WIDTH], current[MAX_WIDTH];
#pragma HLS BIND_STORAGE variable=parent type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=table type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=previous type=ram_2p impl=bram
#pragma HLS BIND_STORAGE variable=current type=ram_2p impl=bram
    unsigned next_label = 1, previous_count = 0, current_count = 0;
    unsigned last_y = 0, cursor = 0, total_runs = 0, max_row_runs = 0;
    unsigned flags = 0;
    bool first = true;
    while (true) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=6077
        Run run = runs.read();
        if (run.end) {
            flags |= run.errors.to_uint();
            break;
        }
        ++total_runs;
        if (flags) continue; // Drain the entire frame even after overflow.
        if (first || run.y != last_y) {
            previous_count = !first && run.y == last_y + 1 ? current_count : 0;
            for (unsigned i = 0; i < previous_count; ++i) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=0 max=640
                previous[i] = current[i];
            }
            first = false;
            last_y = run.y;
            current_count = 0;
            cursor = 0;
        }
        // Skip old intervals which cannot overlap this run, including diagonals.
        while (cursor < previous_count && unsigned(previous[cursor].last) + 1 < run.first) {
#pragma HLS LOOP_TRIPCOUNT min=0 max=640
            ++cursor;
        }
        Label label = 0;
        for (unsigned i = cursor; i < previous_count; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=0 max=640
            RowRun old = previous[i];
            if (unsigned(old.first) > unsigned(run.last) + 1) break;
            if (old.color != run.color || unsigned(old.last) + 1 < run.first) continue;
            Label other = find_root(old.label, parent);
            if (label == 0) label = other;
            else {
                label = find_root(label, parent);
                if (label != other) {
                    Label low = label < other ? label : other;
                    Label high = label < other ? other : label;
                    table[low] = add_regions(table[low], table[high]);
                    parent[high] = low;
                    label = low;
                }
            }
        }
        if (label == 0) {
            if (next_label >= MAX_LABELS) {
                flags |= LABEL_OVERFLOW;
                continue;
            }
            label = next_label++;
            parent[label] = label;
            Region empty = {run.color, 0, 0, 0, run.first, run.last, run.y, run.y};
            table[label] = empty;
        }
        unsigned length = unsigned(run.last) - unsigned(run.first) + 1;
        Region increment = {run.color, length,
                            (unsigned(run.first) + unsigned(run.last)) * length / 2,
                            unsigned(run.y) * length, run.first, run.last, run.y, run.y};
        table[label] = add_regions(table[label], increment);
        RowRun stored = {run.first, run.last, run.color, label};
        current[current_count++] = stored; // At most width runs per row.
        if (current_count > max_row_runs) max_row_runs = current_count;
    }
    unsigned count = 0;
    if (!flags) {
        for (unsigned i = 1; i < next_label; ++i) {
#pragma HLS LOOP_TRIPCOUNT min=0 max=2047
            if (parent[i] != i) continue;
            Region r = table[i];
            if (r.area < min_area || r.area > max_area || r.xmin == 0 || r.ymin == 0
                    || unsigned(r.xmax) + 1 == width || unsigned(r.ymax) + 1 == height) continue;
            output.write(packet(false, 0, r.color, r.area, r.sum_x, r.sum_y,
                                r.xmin, r.ymin, r.xmax, r.ymax, frame_id, timestamp, 0));
            ++count;
        }
    }
    // Summary: words 1/2/3 carry total runs / max row runs / allocated labels.
    output.write(packet(true, flags, 0, total_runs, max_row_runs, next_label - 1,
                        0, 0, 0, 0, frame_id, timestamp, count));
}

static void frame_pipeline(hls::stream<Pixel>& input, hls::stream<Packet>& output,
                           const ColorThreshold thresholds[4], unsigned width, unsigned height,
                           unsigned min_area, unsigned max_area,
                           ap_uint<32> frame_id, ap_uint<64> timestamp) {
#pragma HLS DATAFLOW
    hls::stream<Run> runs("runs");
#pragma HLS STREAM variable=runs depth=64
    make_runs(input, runs, thresholds, width, height);
    label_runs(runs, output, width, height, min_area, max_area, frame_id, timestamp);
}

void glove_markers(hls::stream<Pixel>& pixels, hls::stream<Packet>& regions,
                   const ColorThreshold thresholds[4], unsigned width, unsigned height,
                   unsigned min_area, unsigned max_area,
                   ap_uint<32> frame_id, ap_uint<64> timestamp_us) {
#pragma HLS INTERFACE axis port=pixels
#pragma HLS INTERFACE axis port=regions
#pragma HLS INTERFACE s_axilite port=thresholds bundle=control
#pragma HLS INTERFACE s_axilite port=width bundle=control
#pragma HLS INTERFACE s_axilite port=height bundle=control
#pragma HLS INTERFACE s_axilite port=min_area bundle=control
#pragma HLS INTERFACE s_axilite port=max_area bundle=control
#pragma HLS INTERFACE s_axilite port=frame_id bundle=control
#pragma HLS INTERFACE s_axilite port=timestamp_us bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
    bool valid = width > 0 && width <= MAX_WIDTH && height > 0 && height <= MAX_HEIGHT
                 && min_area > 0 && min_area <= max_area;
    for (int i = 0; i < 4; ++i)
        if (thresholds[i].h_min > 179 || thresholds[i].h_max > 179) valid = false;
    if (!valid) {
        regions.write(packet(true, BAD_CONFIG, 0, 0, 0, 0, 0, 0, 0, 0, frame_id, timestamp_us, 0));
        return; // Invalid configuration consumes no input; driver must reset/retry.
    }
    frame_pipeline(pixels, regions, thresholds, width, height, min_area, max_area, frame_id, timestamp_us);
}
