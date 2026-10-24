// UDP request/reply bridge between the PC simulator and the PL hand_core.
#include "hand_accel.hpp"
#include "../protocol/hand_udp_protocol.hpp"

#include <arpa/inet.h>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <sys/socket.h>
#include <unistd.h>

namespace {
constexpr std::uintptr_t HAND_CORE_BASE = 0x43C00000;

bool newer(std::uint32_t sequence, std::uint32_t previous) {
    return static_cast<std::int32_t>(sequence - previous) > 0;
}
} // namespace

int main() {
    try {
        HandAccel accelerator(HAND_CORE_BASE);
        const int socket_fd = socket(AF_INET, SOCK_DGRAM, 0);
        if (socket_fd < 0)
            throw std::runtime_error("cannot create UDP socket");

        sockaddr_in local{};
        local.sin_family = AF_INET;
        local.sin_addr.s_addr = htonl(INADDR_ANY);
        local.sin_port = htons(hand_udp::PORT);
        if (bind(socket_fd, reinterpret_cast<sockaddr *>(&local), sizeof(local)) < 0) {
            close(socket_fd);
            throw std::runtime_error("cannot bind UDP port 47000");
        }

        std::cout << "hand_server listening on UDP 47000\n";
        bool have_sequence = false;
        std::uint32_t last_sequence = 0;

        for (;;) {
            hand_udp::Request request{};
            sockaddr_in peer{};
            socklen_t peer_size = sizeof(peer);
            const ssize_t received = recvfrom(socket_fd, &request, sizeof(request), 0,
                                              reinterpret_cast<sockaddr *>(&peer), &peer_size);
            if (received != sizeof(request) || request.magic != hand_udp::MAGIC ||
                request.version != hand_udp::VERSION || request.type != hand_udp::REQUEST)
                continue;
            if (have_sequence && !request.reset && !newer(request.sequence, last_sequence))
                continue;

            HandInput input{};
            input.timestamp_us = request.timestamp_us;
            input.marker_valid = request.marker_valid;
            std::memcpy(input.marker_xyz, request.marker_xyz, sizeof(input.marker_xyz));
            std::memcpy(input.flex_raw, request.flex_raw, sizeof(input.flex_raw));

            HandOutput output{};
            if (!accelerator.run(input, request.reset != 0, output))
                continue;
            have_sequence = true;
            last_sequence = request.sequence;

            hand_udp::Reply reply{};
            reply.magic = hand_udp::MAGIC;
            reply.version = hand_udp::VERSION;
            reply.type = hand_udp::REPLY;
            reply.sequence = request.sequence;
            reply.timestamp_us = request.timestamp_us;
            std::memcpy(reply.position, output.position, sizeof(reply.position));
            std::memcpy(reply.rotation, output.rotation, sizeof(reply.rotation));
            std::memcpy(reply.bend, output.bend, sizeof(reply.bend));
            std::memcpy(reply.spread, output.spread, sizeof(reply.spread));
            reply.valid = output.valid;
            reply.state = static_cast<std::uint8_t>(output.state);
            sendto(socket_fd, &reply, sizeof(reply), 0,
                   reinterpret_cast<const sockaddr *>(&peer), peer_size);
        }
    } catch (const std::exception &error) {
        std::cerr << "hand_server: " << error.what() << '\n';
        return 1;
    }
}
