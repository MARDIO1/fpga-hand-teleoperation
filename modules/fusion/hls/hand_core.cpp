// Marker geometry, flex decoding and temporal reconstruction in one HLS core.
// Palm loss: predict 100 ms, damp to a stop by 300 ms, then hold position.
// Flex remains live during visual loss; unavailable spread relaxes after 300 ms.
#include "hand_core.hpp"
#include <cmath>

namespace {
constexpr float PI = 3.14159265358979323846f;
constexpr float ALPHA = 0.75f, BETA = 0.08f;
constexpr float RECOVERY = 0.10f, SPREAD_RETURN = 0.60f;
constexpr float PREDICT_TIME = 0.10f, STOP_TIME = 0.30f;
constexpr float PALM[4][3] = {{0.026f, -0.018f, 0.016f},
                              {-0.026f, -0.018f, 0.016f},
                              {0.026f, -0.018f, 0.076f},
                              {-0.014f, -0.018f, 0.082f}};
constexpr float BASE[5][3] = {{0.034f, -0.00858f, 0.029f},
                              {0.033f, 0, 0.095f},
                              {0.011f, 0, 0.099f},
                              {-0.011f, 0, 0.095f},
                              {-0.033f, 0, 0.0865f}};
struct History {
    bool initialized, palm_known;
    uint32_t timestamp;
    float position[3], velocity[3];
    float quaternion[4], quaternion_rate[4];
    float bend[5], spread[5], finger_age[5];
    float palm_age, recovery;
};

float limit(float x, float low, float high) { return std::fmax(low, std::fmin(high, x)); }

void normalize(float *v, int n) {
    float square = 0;
    for (int i = 0; i < n; ++i)
        square += v[i] * v[i];
    float scale = 1.0f / std::sqrt(square);
    for (int i = 0; i < n; ++i)
        v[i] *= scale;
}

void cross(const float a[3], const float b[3], float c[3]) {
    c[0] = a[1] * b[2] - a[2] * b[1];
    c[1] = a[2] * b[0] - a[0] * b[2];
    c[2] = a[0] * b[1] - a[1] * b[0];
}

void to_rotation(const float q[4], float r[9]) {
    float w = q[0], x = q[1], y = q[2], z = q[3];
    r[0] = 1 - 2 * (y * y + z * z);
    r[1] = 2 * (x * y - w * z);
    r[2] = 2 * (x * z + w * y);
    r[3] = 2 * (x * y + w * z);
    r[4] = 1 - 2 * (x * x + z * z);
    r[5] = 2 * (y * z - w * x);
    r[6] = 2 * (x * z - w * y);
    r[7] = 2 * (y * z + w * x);
    r[8] = 1 - 2 * (x * x + y * y);
}

void to_quaternion(const float r[9], float q[4]) {
    float trace = r[0] + r[4] + r[8];
    if (trace > 0) {
        float s = 2 * std::sqrt(trace + 1);
        q[0] = 0.25f * s;
        q[1] = (r[7] - r[5]) / s;
        q[2] = (r[2] - r[6]) / s;
        q[3] = (r[3] - r[1]) / s;
    } else {
        int i = r[4] > r[0] ? 1 : 0;
        if (r[8] > r[3 * i + i])
            i = 2;
        int j = (i + 1) % 3, k = (i + 2) % 3;
        float s = 2 * std::sqrt(1 + r[3 * i + i] - r[3 * j + j] - r[3 * k + k]);
        q[0] = (r[3 * k + j] - r[3 * j + k]) / s;
        q[i + 1] = 0.25f * s;
        q[j + 1] = (r[3 * j + i] + r[3 * i + j]) / s;
        q[k + 1] = (r[3 * k + i] + r[3 * i + k]) / s;
    }
    normalize(q, 4);
}

// Three known, non-collinear palm markers determine a rigid frame.
// Use the same triangle in model/world coordinates; four visible points improve translation.
bool measure_palm(const HandInput &in, float position[3], float rotation[9]) {
    int ids[4], count = 0;
    for (int i = 0; i < 4; ++i)
        if (in.marker_valid & (1u << i))
            ids[count++] = i;
    if (count < 3)
        return false;
    float basis[2][3][3];
    for (int frame = 0; frame < 2; ++frame) {
        const float(*points)[3] = frame ? in.marker_xyz : PALM;
        float direction[3];
        for (int a = 0; a < 3; ++a) {
            basis[frame][0][a] = points[ids[1]][a] - points[ids[0]][a];
            direction[a] = points[ids[2]][a] - points[ids[0]][a];
        }
        normalize(basis[frame][0], 3);
        cross(basis[frame][0], direction, basis[frame][1]);
        normalize(basis[frame][1], 3);
        cross(basis[frame][0], basis[frame][1], basis[frame][2]);
    }
    for (int row = 0; row < 3; ++row)
        for (int col = 0; col < 3; ++col) {
            rotation[3 * row + col] = 0;
            for (int a = 0; a < 3; ++a)
                rotation[3 * row + col] += basis[1][a][row] * basis[0][a][col];
        }
    for (int row = 0; row < 3; ++row) {
        float sum = 0;
        for (int i = 0; i < count; ++i) {
            float value = in.marker_xyz[ids[i]][row];
            for (int col = 0; col < 3; ++col)
                value -= rotation[3 * row + col] * PALM[ids[i]][col];
            sum += value;
        }
        position[row] = sum / count;
    }
    return true;
}

bool measure_spread(int finger, const float marker[3], float bend, float &spread) {
    float v[3];
    for (int i = 0; i < 3; ++i)
        v[i] = marker[i] - BASE[finger][i];
    float angle, reference, range;
    if (finger == 0) {
        float x = 0.707106781f * (v[0] - v[2]);
        if (x * x + v[1] * v[1] < 0.000004f)
            return false;
        angle = std::atan2(-x, -v[1]);
        reference = 0; // The thumb reference Y remains negative for bend in 0..1.
        range = 0.70f;
    } else {
        if (v[0] * v[0] + v[2] * v[2] < 0.000004f)
            return false;
        angle = std::atan2(finger < 3 ? -v[0] : v[0], v[2]);
        // atan2(0,z) only needs z's sign: z crosses zero at this bend value.
        reference = bend > 0.973133077f ? PI : 0;
        range = 0.28f;
    }
    float difference = angle - reference;
    if (difference > PI)
        difference -= 2 * PI;
    if (difference < -PI)
        difference += 2 * PI;
    spread = limit(difference / range, -1, 1);
    return true;
}
} // namespace

void hand_core(const HandInput &input, bool reset, HandOutput &output) {
#pragma HLS INTERFACE s_axilite port = input bundle = control
#pragma HLS INTERFACE s_axilite port = reset bundle = control
#pragma HLS INTERFACE s_axilite port = output bundle = control
#pragma HLS INTERFACE s_axilite port = return bundle = control
    static History h = {};
    if (reset) {
        h = History{};
        h.quaternion[0] = 1;
    }
    float dt = h.initialized ? uint32_t(input.timestamp_us - h.timestamp) * 1e-6f : 0;
    h.timestamp = input.timestamp_us;
    float measured_position[3], measured_rotation[9];
    bool palm = measure_palm(input, measured_position, measured_rotation);
    output.valid = palm ? 1 : 0;
    if (palm) {
        float q[4];
        to_quaternion(measured_rotation, q);
        float dot = 0;
        for (int i = 0; i < 4; ++i)
            dot += q[i] * h.quaternion[i];
        if (dot < 0)
            for (int i = 0; i < 4; ++i)
                q[i] = -q[i];
        if (!h.palm_known) {
            for (int i = 0; i < 3; ++i)
                h.position[i] = measured_position[i];
            for (int i = 0; i < 4; ++i)
                h.quaternion[i] = q[i];
            h.palm_known = true;
            h.recovery = 0;
        } else if (dt > 0) {
            if (h.palm_age > 0)
                h.recovery = RECOVERY;
            float gain = h.recovery > 0 ? dt / (RECOVERY + dt) : ALPHA;
            for (int i = 0; i < 3; ++i) {
                float predicted = h.position[i] + h.velocity[i] * dt;
                float residual = measured_position[i] - predicted;
                h.position[i] = predicted + gain * residual;
                h.velocity[i] = limit(h.velocity[i] + BETA * gain / ALPHA * residual / dt, -1, 1);
            }
            for (int i = 0; i < 4; ++i) {
                float predicted = h.quaternion[i] + h.quaternion_rate[i] * dt;
                float residual = q[i] - predicted;
                h.quaternion[i] = predicted + gain * residual;
                h.quaternion_rate[i] =
                    limit(h.quaternion_rate[i] + BETA * gain / ALPHA * residual / dt, -2, 2);
            }
            normalize(h.quaternion, 4);
            // Quaternion velocity must lie in the unit sphere's tangent plane.
            float radial = 0;
            for (int i = 0; i < 4; ++i)
                radial += h.quaternion[i] * h.quaternion_rate[i];
            for (int i = 0; i < 4; ++i)
                h.quaternion_rate[i] -= radial * h.quaternion[i];
            h.recovery = std::fmax(0.0f, h.recovery - dt);
        }
        h.palm_age = 0;
        output.state = h.recovery > 0 ? REACQUIRE : TRACKING;
    } else {
        // Integrate a linear velocity envelope exactly, including timeout crossings.
        float start = h.palm_age, end = start + dt;
        float duration = STOP_TIME - PREDICT_TIME;
        float a = std::fmin(start, PREDICT_TIME), b = std::fmin(end, PREDICT_TIME);
        float c = limit(start - PREDICT_TIME, 0, duration),
              d = limit(end - PREDICT_TIME, 0, duration);
        float integral = b - a + (d - c) - (d * d - c * c) / (2 * duration);
        float old_scale = start < PREDICT_TIME ? 1 : limit((STOP_TIME - start) / duration, 0, 1);
        float new_scale = end < PREDICT_TIME ? 1 : limit((STOP_TIME - end) / duration, 0, 1);
        float advance = old_scale > 0 ? integral / old_scale : 0;
        float damping = old_scale > 0 ? new_scale / old_scale : 0;
        for (int i = 0; i < 3; ++i) {
            h.position[i] += h.velocity[i] * advance;
            h.velocity[i] *= damping;
        }
        for (int i = 0; i < 4; ++i) {
            h.quaternion[i] += h.quaternion_rate[i] * advance;
            h.quaternion_rate[i] *= damping;
        }
        normalize(h.quaternion, 4);
        h.palm_age = end;
        output.state = end < PREDICT_TIME ? PREDICT : (end < STOP_TIME ? DAMP : HOLD);
    }
    for (int i = 0; i < 3; ++i)
        output.position[i] = h.position[i];
    to_rotation(h.quaternion, output.rotation);
    for (int f = 0; f < 5; ++f) {
        // The existing flex LUT is linear, so the quantized index is sufficient.
        float index =
            std::nearbyint(limit((int(input.flex_raw[f]) - 300) * (255.0f / 3400), 0, 255));
        float bend = index / 255;
        float finger_gain = !h.initialized ? 1 : dt / (0.015f + dt);
        h.bend[f] += finger_gain * (bend - h.bend[f]);
        float local[3] = {}, spread = 0;
        bool visible = palm && (input.marker_valid & (1u << (f + 4)));
        if (visible)
            for (int col = 0; col < 3; ++col)
                for (int row = 0; row < 3; ++row)
                    local[col] += measured_rotation[3 * row + col] *
                                  (input.marker_xyz[f + 4][row] - measured_position[row]);
        bool measured = visible && measure_spread(f, local, bend, spread);
        if (measured) {
            output.valid |= 1u << (f + 1);
            float gain = !h.initialized ? 1 : dt / ((h.finger_age[f] > 0 ? RECOVERY : 0.02f) + dt);
            h.spread[f] += gain * (spread - h.spread[f]);
            h.finger_age[f] = 0;
        } else {
            float previous = h.finger_age[f];
            h.finger_age[f] += dt;
            float relax = std::fmax(0.0f, h.finger_age[f] - STOP_TIME) -
                          std::fmax(0.0f, previous - STOP_TIME);
            h.spread[f] *= SPREAD_RETURN / (SPREAD_RETURN + relax);
        }
        output.bend[f] = h.bend[f];
        output.spread[f] = h.spread[f];
    }
    h.initialized = true;
}
