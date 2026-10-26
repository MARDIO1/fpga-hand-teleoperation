// Little-endian UDP wire protocol shared by the PC client and PS server.
#pragma once

#include <cstdint>

namespace hand_udp {

constexpr std::uint32_t MAGIC = 0x444E4148; // "HAND" in little endian.
constexpr std::uint16_t VERSION = 2;
constexpr std::uint16_t REQUEST = 1;
constexpr std::uint16_t REPLY = 2;
constexpr std::uint16_t PORT = 47000;

#pragma pack(push, 1)
struct Request {
    std::uint32_t magic;
    std::uint16_t version;
    std::uint16_t type;
    std::uint32_t sequence;
    std::uint32_t timestamp_us;
    std::uint8_t reset;
    std::uint8_t camera_valid;
    std::uint8_t imu_valid;
    std::uint8_t reserved0;
    float camera_position[3];
    float imu_quaternion[4];
    float linear_acceleration[3];
    float angular_velocity[3];
    std::uint16_t flex_raw[5];
    std::uint16_t reserved1;
};

struct Reply {
    std::uint32_t magic;
    std::uint16_t version;
    std::uint16_t type;
    std::uint32_t sequence;
    std::uint32_t timestamp_us;
    float position[3];
    float rotation[9];
    float bend[5];
    float spread[5];
    std::uint16_t valid;
    std::uint8_t state;
    std::uint8_t reserved;
};
#pragma pack(pop)

static_assert(sizeof(Request) == 84, "UDP request layout changed");
static_assert(sizeof(Reply) == 108, "UDP reply layout changed");

} // namespace hand_udp
