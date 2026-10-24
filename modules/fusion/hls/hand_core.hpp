// Stateful hand reconstruction for Vitis HLS.
// Units: metres, seconds, radians; marker order: four palm points then five fingers.
// Call reset on the first packet of each sequence. Missing XYZ entries are ignored.
#pragma once
#include <cstdint>

enum TrackingState : uint8_t { TRACKING, PREDICT, DAMP, HOLD, REACQUIRE };

struct HandInput {
    uint32_t timestamp_us;
    uint16_t marker_valid;
    float marker_xyz[9][3];
    uint16_t flex_raw[5];
};

struct HandOutput {
    float position[3];
    float rotation[9]; // Row-major, local palm frame to world frame.
    float bend[5];     // 0..1
    float spread[5];   // -1..1, thumb first
    uint16_t valid;    // Bit 0: measured palm; bits 1..5: measured finger spread.
    TrackingState state;
};

void hand_core(const HandInput &input, bool reset, HandOutput &output);
