// Minimal userspace MMIO wrapper for the hand_core AXI4-Lite registers.
#pragma once

#include <cstdint>

#include "../../hls/hand_core.hpp"

class HandAccel {
  public:
    explicit HandAccel(std::uintptr_t physical_base);
    ~HandAccel();

    HandAccel(const HandAccel &) = delete;
    HandAccel &operator=(const HandAccel &) = delete;

    bool run(const HandInput &input, bool reset, HandOutput &output);

  private:
    int memory_fd_ = -1;
    volatile std::uint32_t *registers_ = nullptr;
};
