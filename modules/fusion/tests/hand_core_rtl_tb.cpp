// Short HLS co-simulation sequence covering tracking, prediction, hold and recovery.
#include "hand_core.hpp"
#include <cmath>
#include <iostream>

int main() {
    HandInput input{};
    HandOutput output{};
    input.camera_valid = input.imu_valid = 1;
    input.camera_position[2] = 0.3f;
    input.imu_quaternion[0] = 1;
    for (uint16_t &value : input.flex_raw)
        value = 300;
    hand_core(input, true, output);
    bool passed = output.state == TRACKING && output.valid == 3;

    for (int frame = 0; frame < 8; ++frame) {
        input.timestamp_us += 33333;
        input.camera_position[0] += 0.002f;
        hand_core(input, false, output);
    }
    input.camera_valid = 0;
    for (uint16_t &value : input.flex_raw)
        value = 3700;
    const uint32_t gaps[] = {50000, 100000, 200000};
    const TrackingState states[] = {PREDICT, DAMP, HOLD};
    for (int i = 0; i < 3; ++i) {
        input.timestamp_us += gaps[i];
        hand_core(input, false, output);
        passed &= output.state == states[i];
    }
    passed &= output.bend[0] > 0.9f;

    input.camera_valid = 1;
    input.camera_position[0] += 0.1f;
    input.timestamp_us += 33333;
    hand_core(input, false, output);
    passed &= output.state == REACQUIRE;
    passed &= std::isfinite(output.position[0]) && std::isfinite(output.rotation[0]);
    std::cout << "RTL sequence " << (passed ? "PASS" : "FAIL") << '\n';
    return passed ? 0 : 1;
}
