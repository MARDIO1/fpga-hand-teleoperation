// Camera position + dorsal IMU orientation + five flex channels.
// Units: metres, seconds, radians. IMU quaternion order is w, x, y, z.
#pragma once
#include <cstdint>

enum TrackingState : uint8_t { TRACKING, PREDICT, DAMP, HOLD, REACQUIRE };

struct HandInput {
    uint32_t timestamp_us;
    uint8_t camera_valid;
    uint8_t imu_valid;
    uint16_t reserved0;
    float camera_position[3];
    float imu_quaternion[4];
    float linear_acceleration[3]; // Gravity-free, IMU body frame.
    float angular_velocity[3];    // IMU body frame.
    uint16_t flex_raw[5];
    uint16_t reserved1;
};

struct HandOutput {
    float position[3];
    float rotation[9]; // Row-major palm frame to world frame.
    float bend[5];     // 0..1
    float spread[5];   // Inferred -1..1, thumb first.
    uint16_t valid;    // Bit 0 camera, bit 1 IMU, bit 2 inertial prediction, bit 3 ZUPT.
    TrackingState state;
};

void hand_core(const HandInput &input, bool reset, HandOutput &output);
