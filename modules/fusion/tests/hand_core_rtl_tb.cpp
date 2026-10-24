// Short RTL co-simulation sequence; the long numerical replay is hand_core_tb.cpp.
// Cover reset, moving/partial tracking, loss timeouts, recovery and timestamp wrap.
#include "hand_core.hpp"
#include <cmath>
#include <fstream>
#include <iostream>

int main() {
    std::ifstream packets("packets.txt");
    if (!packets) packets.open("tests/data/packets.txt");
    HandInput input{};
    HandOutput output{};
    int reset;
    if (!(packets >> reset >> input.timestamp_us >> input.marker_valid)) return 1;
    for (auto& marker : input.marker_xyz)
        for (float& value : marker) packets >> value;
    for (auto& value : input.flex_raw) packets >> value;
    float expected_x;
    packets >> expected_x;
    hand_core(input, true, output);
    bool passed = std::fabs(output.position[0] - expected_x) < 0.002f;
    for (int i = 0; i < 6; ++i) {
        input.timestamp_us += 33333;
        for (auto& marker : input.marker_xyz) marker[0] += 0.002f;
        hand_core(input, false, output);
    }
    for (int missing = 0; missing < 4; ++missing) {
        input.timestamp_us += 33333;
        input.marker_valid = 511u & ~(1u << missing);
        hand_core(input, false, output);
        passed &= (output.valid & 1) != 0;
    }
    input.marker_valid = 511u & ~(1u << 5);
    input.timestamp_us += 33333;
    hand_core(input, false, output);
    passed &= (output.valid & 4) == 0;
    input.marker_valid = 0;
    for (auto& value : input.flex_raw) value = 3700;
    const uint32_t gaps[] = {50000, 100000, 200000, 200000};
    const TrackingState states[] = {PREDICT, DAMP, HOLD, HOLD};
    float held = 0;
    for (int i = 0; i < 4; ++i) {
        input.timestamp_us += gaps[i];
        hand_core(input, false, output);
        passed &= output.state == states[i] && output.valid == 0;
        if (i == 2) held = output.position[0];
        if (i == 3) passed &= output.position[0] == held;
    }
    passed &= output.bend[0] > 0.9f;
    input.marker_valid = 511;
    for (int i = 0; i < 8; ++i) {
        input.timestamp_us += 33333;
        hand_core(input, false, output);
        if (i == 0) passed &= output.state == REACQUIRE;
    }
    passed &= output.state == TRACKING;
    // Rotate by pi about world Z, exercising the negative-trace quaternion branch.
    for (auto& marker : input.marker_xyz) { marker[0] = -marker[0]; marker[1] = -marker[1]; }
    input.timestamp_us = 0xfffffff0u;
    hand_core(input, true, output);
    passed &= output.rotation[0] < -0.9f;
    input.timestamp_us += 33333;
    hand_core(input, false, output);
    passed &= std::isfinite(output.position[0]) && output.state == TRACKING;
    std::cout << "RTL sequence " << (passed ? "PASS" : "FAIL") << '\n';
    return passed ? 0 : 1;
}
