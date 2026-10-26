# Fusion standalone overlay v0.1.0

Independent ACZ7015 test overlay containing PS7, AXI control interconnect and the floating-point `hand_core` IP.

This is a module verification image, not the final combined product bitstream.

This image uses the retired marker-input v0.1 interface. It is retained only as
a historical artifact and must not be loaded with the v0.2 PS software.

- Part: `xc7z015clg485-2`
- PL clock: 100 MHz
- `hand_core`: `0x43C00000` to `0x43C00FFF`
- Vivado/Vitis: 2025.2
