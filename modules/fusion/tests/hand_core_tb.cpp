// CSim/RTL testbench: compare existing MuJoCo targets and exercise tracking loss.
// Test-only file I/O and assertions do not enter the synthesized core.
#include "hand_core.hpp"
#include <cmath>
#include <fstream>
#include <iostream>
#include <limits>

int main() {
    std::ifstream packets("packets.txt");
    if (!packets)
        packets.open("tests/data/packets.txt");
    if (!packets) {
        std::cerr << "Generate packets with simulation/virtual_hand/export_hand_vectors.py\n";
        return 1;
    }
    HandInput input{};
    HandOutput output{};
    float max_position = 0, max_rotation = 0, max_bend = 0, max_spread = 0;
    int reset, frame = 0, sequence_frame = 0;
    while (packets >> reset >> input.timestamp_us >> input.marker_valid) {
        for (auto &marker : input.marker_xyz)
            for (float &value : marker)
                packets >> value;
        for (auto &value : input.flex_raw)
            packets >> value;
        float expected[22];
        for (float &value : expected)
            packets >> value;
        hand_core(input, reset, output);
        if (reset)
            sequence_frame = 0;
        // Settled static poses and continuous motion; exclude intentional startup settling.
        if (sequence_frame > 90) {
            for (int i = 0; i < 3; ++i)
                max_position = std::fmax(max_position, std::fabs(output.position[i] - expected[i]));
            for (int i = 0; i < 9; ++i)
                max_rotation =
                    std::fmax(max_rotation, std::fabs(output.rotation[i] - expected[i + 3]));
            for (int i = 0; i < 5; ++i) {
                max_bend = std::fmax(max_bend, std::fabs(output.bend[i] - expected[i + 12]));
                max_spread = std::fmax(max_spread, std::fabs(output.spread[i] - expected[i + 17]));
            }
        }
        ++sequence_frame;
        ++frame;
    }
    // Spread is normalized to approximately 20 degrees in the existing display metric.
    bool passed = frame == 2160 && max_position < 0.002f && max_rotation < 0.02f &&
                  max_bend < 0.03f && max_spread < 0.25f;
    std::cout << "reference=" << passed << '\n';
    // Each of the four palm triangles must reconstruct the settled pose.
    float settled[3];
    for (int i = 0; i < 3; ++i)
        settled[i] = output.position[i];
    for (int missing = 0; missing < 4; ++missing) {
        input.marker_valid = 511u & ~(1u << missing);
        input.timestamp_us += 16667;
        hand_core(input, true, output);
        passed &= (output.valid & 1) != 0;
        for (int i = 0; i < 3; ++i)
            passed &= std::fabs(output.position[i] - settled[i]) < 0.002f;
    }
    std::cout << "palm_triangles=" << passed << '\n';
    // Missing coordinates are NaN to catch accidental reads of invalid markers.
    input.marker_valid = 0;
    for (auto &marker : input.marker_xyz)
        for (float &value : marker)
            value = std::numeric_limits<float>::quiet_NaN();
    for (int f = 0; f < 5; ++f)
        input.flex_raw[f] = 300;
    float held[3] = {};
    for (int i = 0; i < 120; ++i) {
        input.timestamp_us += 16667;
        hand_core(input, false, output);
        if (i == 30)
            for (int a = 0; a < 3; ++a)
                held[a] = output.position[a];
        if (i > 30)
            for (int a = 0; a < 3; ++a)
                passed &= output.position[a] == held[a];
        for (float value : output.rotation)
            passed &= std::isfinite(value);
        passed &= output.valid == 0;
    }
    passed &= output.state == HOLD && output.bend[0] < 0.001f;
    std::cout << "loss_hold=" << passed << '\n';
    // Reacquire at an offset, then settle without a one-frame teleport.
    packets.clear();
    packets.seekg(0);
    packets >> reset >> input.timestamp_us >> input.marker_valid;
    for (auto &marker : input.marker_xyz)
        for (float &value : marker)
            packets >> value;
    for (auto &value : input.flex_raw)
        packets >> value;
    input.timestamp_us = 10'000'000;
    hand_core(input, true, output);
    input.marker_valid = 0;
    input.timestamp_us += 500000;
    hand_core(input, false, output);
    float before = output.position[0];
    input.marker_valid = 511;
    for (auto &marker : input.marker_xyz)
        marker[0] += 0.1f;
    input.timestamp_us += 16667;
    hand_core(input, false, output);
    passed &= output.state == REACQUIRE && std::fabs(output.position[0] - before) < 0.03f;
    for (int i = 0; i < 180; ++i) {
        input.timestamp_us += 16667;
        hand_core(input, false, output);
    }
    passed &= output.state == TRACKING && std::fabs(output.position[0] - before - 0.1f) < 0.002f;
    std::cout << "recovery=" << passed << '\n';
    // Startup without markers, followed by the first actual pose.
    input.marker_valid = 0;
    hand_core(input, true, output);
    input.timestamp_us += 16667;
    input.marker_valid = 511;
    hand_core(input, false, output);
    passed &= std::fabs(output.position[0] - before - 0.1f) < 0.002f;

    // Constant translation develops velocity; visual loss must coast, then stop.
    for (int i = 0; i < 90; ++i) {
        input.timestamp_us += 16667;
        for (auto &marker : input.marker_xyz)
            marker[0] += 0.001f;
        hand_core(input, false, output);
    }
    float moving = output.position[0];
    input.marker_valid = 0;
    for (int i = 0; i < 60; ++i) {
        input.timestamp_us += 16667;
        hand_core(input, false, output);
        if (i == 30)
            held[0] = output.position[0];
        if (i > 30)
            passed &= output.position[0] == held[0];
    }
    passed &= held[0] > moving + 0.005f && held[0] < moving + 0.02f;
    std::cout << "moving_loss=" << passed << '\n';

    // Export the existing animated sequence for the PC renderer, including dropouts.
    packets.clear();
    packets.seekg(0);
    std::ofstream replay("reconstruction.txt");
    int sample = 0;
    while (packets >> reset >> input.timestamp_us >> input.marker_valid) {
        for (auto &marker : input.marker_xyz)
            for (float &value : marker)
                packets >> value;
        for (auto &value : input.flex_raw)
            packets >> value;
        float expected[22];
        for (float &value : expected)
            packets >> value;
        if (sample++ < 1800)
            continue;
        int step = sample - 1801;
        if (step >= 60 && step < 90)
            input.marker_valid &= ~(1u << 5);
        if (step >= 120 && step < 180)
            input.marker_valid = 0;
        hand_core(input, reset, output);
        replay << input.timestamp_us << ' ' << int(output.state) << ' ' << output.valid;
        for (float value : output.position)
            replay << ' ' << value;
        for (float value : output.rotation)
            replay << ' ' << value;
        for (float value : output.bend)
            replay << ' ' << value;
        for (float value : output.spread)
            replay << ' ' << value;
        replay << '\n';
    }
    std::cout << "frames=" << frame << " max_position_m=" << max_position
              << " rotation_element=" << max_rotation << " bend=" << max_bend
              << " spread=" << max_spread << '\n';
    std::cout << (passed ? "PASS" : "FAIL") << '\n';
    return passed ? 0 : 1;
}
