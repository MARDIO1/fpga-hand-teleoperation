// Short visual dropouts use bounded inertial prediction; long dropouts hold.
#include "hand_core.hpp"
#include <cmath>

namespace {
constexpr float POSITION_DEAD_ZONE = 0.0005f;
constexpr float ACCEL_DEAD_ZONE = 0.12f;
constexpr float GYRO_DEAD_ZONE = 0.05f;
constexpr float STATIONARY_SPEED = 0.03f;
constexpr float PREDICT_TIME = 0.12f;
constexpr float HOLD_TIME = 0.25f;
constexpr float RECOVERY_TIME = 0.08f;
constexpr float VELOCITY_LIMIT = 1.5f;
constexpr float VELOCITY_DAMPING = 4.0f;
constexpr float BEND_TAU = 0.015f;
constexpr float FLEX_MIN = 300.0f;
constexpr float FLEX_MAX = 3700.0f;
constexpr float SPREAD_OPEN[5] = {0.45f, 0.55f, 0.18f, -0.18f, -0.55f};
constexpr float SPREAD_CLOSED[5] = {-0.18f, 0.08f, 0.03f, -0.03f, -0.08f};

struct History {
    bool initialized, camera_known, camera_visible;
    uint32_t timestamp;
    float position[3], velocity[3], last_camera[3], accel_bias[3];
    float quaternion[4], bend[5];
    float camera_age, recovery;
};

float limit(float value, float low, float high) {
    return std::fmax(low, std::fmin(high, value));
}

float norm3(const float value[3]) {
    return std::sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2]);
}

void normalize4(float value[4]) {
    float square = 0;
    for (int i = 0; i < 4; ++i)
        square += value[i] * value[i];
    if (square < 1e-12f) {
        value[0] = 1;
        value[1] = value[2] = value[3] = 0;
        return;
    }
    float scale = 1.0f / std::sqrt(square);
    for (int i = 0; i < 4; ++i)
        value[i] *= scale;
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

void rotate_vector(const float q[4], const float v[3], float out[3]) {
    float r[9];
    to_rotation(q, r);
    for (int row = 0; row < 3; ++row)
        out[row] = r[3 * row] * v[0] + r[3 * row + 1] * v[1] + r[3 * row + 2] * v[2];
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
    float elapsed = h.initialized ? uint32_t(input.timestamp_us - h.timestamp) * 1e-6f : 0;
    float dt = limit(elapsed, 0, 0.05f);
    h.timestamp = input.timestamp_us;
    output.valid = 0;

    if (input.imu_valid) {
        float q[4], dot = 0;
        for (int i = 0; i < 4; ++i) {
            q[i] = input.imu_quaternion[i];
            dot += q[i] * h.quaternion[i];
        }
        normalize4(q);
        if (dot < 0)
            for (float &value : q)
                value = -value;
        float gain = !h.initialized ? 1.0f : dt / (0.02f + dt);
        for (int i = 0; i < 4; ++i)
            h.quaternion[i] += gain * (q[i] - h.quaternion[i]);
        normalize4(h.quaternion);
        output.valid |= 2;
    }

    if (input.camera_valid) {
        bool reacquire = h.camera_known && !h.camera_visible;
        if (!h.camera_known) {
            for (int i = 0; i < 3; ++i)
                h.position[i] = input.camera_position[i];
            h.camera_known = true;
        } else if (dt > 0) {
            float delta[3];
            for (int i = 0; i < 3; ++i)
                delta[i] = input.camera_position[i] - h.last_camera[i];
            bool still = norm3(delta) < POSITION_DEAD_ZONE;
            float gain = reacquire || h.recovery > 0 ? dt / (RECOVERY_TIME + dt) : 0.75f;
            for (int i = 0; i < 3; ++i) {
                float measured_velocity = still ? 0 : delta[i] / dt;
                h.velocity[i] += 0.25f * (limit(measured_velocity, -VELOCITY_LIMIT, VELOCITY_LIMIT) - h.velocity[i]);
                h.position[i] += gain * (input.camera_position[i] - h.position[i]);
            }
            if (still)
                for (float &value : h.velocity)
                    value = 0;
            if (still && input.imu_valid && norm3(input.angular_velocity) < GYRO_DEAD_ZONE &&
                norm3(input.linear_acceleration) < 0.4f) {
                for (int i = 0; i < 3; ++i)
                    h.accel_bias[i] += 0.02f * (input.linear_acceleration[i] - h.accel_bias[i]);
                output.valid |= 8;
            }
        }
        for (int i = 0; i < 3; ++i)
            h.last_camera[i] = input.camera_position[i];
        if (reacquire)
            h.recovery = RECOVERY_TIME;
        else
            h.recovery = std::fmax(0.0f, h.recovery - dt);
        h.camera_age = 0;
        h.camera_visible = true;
        output.valid |= 1;
        output.state = h.recovery > 0 ? REACQUIRE : TRACKING;
    } else {
        h.camera_visible = false;
        h.camera_age += elapsed;
        float corrected_body[3], world_accel[3];
        for (int i = 0; i < 3; ++i)
            corrected_body[i] = input.linear_acceleration[i] - h.accel_bias[i];
        rotate_vector(h.quaternion, corrected_body, world_accel);
        float speed = norm3(h.velocity);
        bool stationary = input.imu_valid && norm3(corrected_body) < ACCEL_DEAD_ZONE &&
                          norm3(input.angular_velocity) < GYRO_DEAD_ZONE && speed < STATIONARY_SPEED;
        if (stationary) {
            for (int i = 0; i < 3; ++i) {
                h.velocity[i] = 0;
                h.accel_bias[i] += 0.02f * (input.linear_acceleration[i] - h.accel_bias[i]);
            }
            output.valid |= 8;
        } else if (h.camera_known && h.camera_age <= HOLD_TIME) {
            for (int i = 0; i < 3; ++i) {
                float acceleration = std::fabs(world_accel[i]) < ACCEL_DEAD_ZONE ? 0 : world_accel[i];
                h.position[i] += h.velocity[i] * dt + 0.5f * acceleration * dt * dt;
                h.velocity[i] = (h.velocity[i] + acceleration * dt) / (1 + VELOCITY_DAMPING * dt);
            }
            output.valid |= input.imu_valid ? 4 : 0;
        }
        if (h.camera_age >= HOLD_TIME)
            for (float &value : h.velocity)
                value = 0;
        output.state = h.camera_age < PREDICT_TIME ? PREDICT :
                       (h.camera_age < HOLD_TIME ? DAMP : HOLD);
    }

    for (int i = 0; i < 3; ++i)
        output.position[i] = h.position[i];
    to_rotation(h.quaternion, output.rotation);
    for (int finger = 0; finger < 5; ++finger) {
        float raw = limit((input.flex_raw[finger] - FLEX_MIN) / (FLEX_MAX - FLEX_MIN), 0, 1);
        float gain = !h.initialized ? 1 : dt / (BEND_TAU + dt);
        h.bend[finger] += gain * (raw - h.bend[finger]);
        output.bend[finger] = h.bend[finger];
        output.spread[finger] = SPREAD_OPEN[finger] +
                                h.bend[finger] * (SPREAD_CLOSED[finger] - SPREAD_OPEN[finger]);
    }
    h.initialized = true;
}
