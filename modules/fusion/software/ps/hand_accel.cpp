// Map hand_core through /dev/mem and execute one AXI4-Lite transaction.
#include "hand_accel.hpp"

#include <chrono>
#include <cstddef>
#include <cstring>
#include <fcntl.h>
#include <stdexcept>
#include <sys/mman.h>
#include <unistd.h>

namespace {
constexpr std::size_t MAP_SIZE = 4096;
constexpr std::size_t CONTROL = 0x000 / 4;
constexpr std::size_t RESET = 0x018 / 4;
constexpr std::size_t INPUT = 0x080 / 4;
constexpr std::size_t OUTPUT = 0x100 / 4;
constexpr std::uint32_t START = 1u << 0;
constexpr std::uint32_t DONE = 1u << 1;
constexpr auto TIMEOUT = std::chrono::milliseconds(5);

static_assert(sizeof(HandInput) == 128, "HLS input layout changed");
static_assert(offsetof(HandInput, marker_valid) == 4, "HLS input layout changed");
static_assert(offsetof(HandInput, marker_xyz) == 8, "HLS input layout changed");
static_assert(offsetof(HandInput, flex_raw) == 116, "HLS input layout changed");
static_assert(sizeof(HandOutput) == 92, "HLS output layout changed");
static_assert(offsetof(HandOutput, rotation) == 12, "HLS output layout changed");
static_assert(offsetof(HandOutput, bend) == 48, "HLS output layout changed");
static_assert(offsetof(HandOutput, spread) == 68, "HLS output layout changed");
static_assert(offsetof(HandOutput, valid) == 88, "HLS output layout changed");
static_assert(offsetof(HandOutput, state) == 90, "HLS output layout changed");
} // namespace

HandAccel::HandAccel(std::uintptr_t physical_base) {
    memory_fd_ = open("/dev/mem", O_RDWR | O_SYNC);
    if (memory_fd_ < 0)
        throw std::runtime_error("cannot open /dev/mem");

    void *mapping = mmap(nullptr, MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED,
                         memory_fd_, static_cast<off_t>(physical_base));
    if (mapping == MAP_FAILED) {
        close(memory_fd_);
        memory_fd_ = -1;
        throw std::runtime_error("cannot map hand_core");
    }
    registers_ = static_cast<volatile std::uint32_t *>(mapping);
}

HandAccel::~HandAccel() {
    if (registers_)
        munmap(const_cast<std::uint32_t *>(registers_), MAP_SIZE);
    if (memory_fd_ >= 0)
        close(memory_fd_);
}

bool HandAccel::run(const HandInput &input, bool reset, HandOutput &output) {
    std::uint32_t input_words[32];
    std::uint32_t output_words[23];
    std::memcpy(input_words, &input, sizeof(input_words));

    for (std::size_t i = 0; i < 32; ++i)
        registers_[INPUT + i] = input_words[i];
    registers_[RESET] = reset ? 1u : 0u;
    __sync_synchronize();
    registers_[CONTROL] = START;

    const auto deadline = std::chrono::steady_clock::now() + TIMEOUT;
    while ((registers_[CONTROL] & DONE) == 0) {
        if (std::chrono::steady_clock::now() >= deadline)
            return false;
    }
    __sync_synchronize();
    for (std::size_t i = 0; i < 23; ++i)
        output_words[i] = registers_[OUTPUT + i];
    std::memcpy(&output, output_words, sizeof(output));
    return true;
}
