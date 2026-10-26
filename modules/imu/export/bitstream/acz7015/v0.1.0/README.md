# MPU6050 standalone ACZ7015 prototype v0.1.0

Vivado 2025.2, xc7z015clg485-2, PL 100 MHz, post-route WNS +3.442 ns, DRC clean.
The bit/HWH pair is imported unchanged from the final standalone studio build;
its RTL is byte-identical to this module's RTL. Rebuild scripts live in
`../../../../vivado/`; no bit-identical rebuild from a different path is claimed.

On 2026-10-25 the final pair was loaded on ACZ7015 and automatically initialized
the real MPU6050 without a manual wake command. A six-second probe saw 2853
samples, status=3, zero I2C errors, and about 499.947 Hz raw acquisition.
The separate 60-second ARM/PC test measured about 491.800 Hz steady pose output.
See `../../../../docs/status.md` for stage-specific evidence and limitations.

`build_info.json` records source/artifact SHA256 hashes and validation provenance.
Private AXI-Lite address: imu=0x43C10000, range=0x1000. This is a standalone test
overlay and replaces any currently loaded PL configuration. It is not the final
combined image; final integration must instantiate the separately packaged IP.
