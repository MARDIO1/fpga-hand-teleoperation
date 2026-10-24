# Shared contracts

These documents define the boundaries between independently developed modules. Payload fields are little-endian. Cross-module PL streams use 32-bit AXI4-Stream words and assert `TLAST` on the final word of one frame.

Current contract version: `0.1`.
