// Native regression for camera + dorsal IMU + five-flex reconstruction.
#include "hand_core.hpp"
#include <cmath>
#include <iostream>

namespace {
constexpr uint32_t STEP_US = 16667;

void step(HandInput &input, HandOutput &output, bool reset = false) {
    hand_core(input, reset, output);
    input.timestamp_us += STEP_US;
}
}

int main() {
    HandInput input{};
    HandOutput output{};
    input.camera_valid = 1;
    input.imu_valid = 1;
    input.camera_position[2] = 0.3f;
    input.imu_quaternion[0] = 0.70710678f;
    input.imu_quaternion[3] = 0.70710678f;
    for (uint16_t &value : input.flex_raw)
        value = 300;
    step(input, output, true);

    bool passed = output.state == TRACKING && output.valid == 3;
    passed &= std::fabs(output.position[2] - 0.3f) < 1e-6f;
    passed &= std::fabs(output.rotation[1] + 1.0f) < 1e-4f;

    for (int frame = 0; frame < 60; ++frame) {
        input.camera_position[0] += 0.001f;
        for (uint16_t &value : input.flex_raw)
            value = 3700;
        step(input, output);
    }
    passed &= output.bend[0] > 0.99f && output.spread[0] < -0.15f;
    float measured = output.position[0];

    input.camera_valid = 0;
    for (int frame = 0; frame < 9; ++frame)
        step(input, output);
    passed &= output.state == DAMP && (output.valid & 4) != 0;
    passed &= output.position[0] > measured;
    for (int frame = 0; frame < 12; ++frame)
        step(input, output);
    float held = output.position[0];
    passed &= output.state == HOLD;
    for (int frame = 0; frame < 20; ++frame)
        step(input, output);
    passed &= output.position[0] == held;

    input.camera_valid = 1;
    input.camera_position[0] = held + 0.1f;
    step(input, output);
    passed &= output.state == REACQUIRE && output.position[0] < held + 0.03f;
    for (int frame = 0; frame < 60; ++frame)
        step(input, output);
    passed &= output.state == TRACKING;
    passed &= std::fabs(output.position[0] - input.camera_position[0]) < 0.001f;

    // A settled hand must zero velocity and hold immediately during loss.
    for (int frame = 0; frame < 4; ++frame)
        step(input, output);
    input.camera_valid = 0;
    step(input, output);
    passed &= (output.valid & 8) != 0;
    float stationary = output.position[0];
    for (int frame = 0; frame < 8; ++frame)
        step(input, output);
    passed &= output.position[0] == stationary;

    // Timestamp subtraction remains valid through uint32 wrap.
    input.camera_valid = 1;
    input.timestamp_us = 0xfffffff0u;
    step(input, output, true);
    step(input, output);
    passed &= std::isfinite(output.position[0]);

    std::cout << "camera_imu_flex=" << (passed ? "PASS" : "FAIL") << '\n';
    return passed ? 0 : 1;
}
