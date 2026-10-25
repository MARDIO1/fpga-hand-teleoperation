# Hardware source provenance and redistribution status

This migration was requested by the workspace owner. It selects files already
present in `vision_studio`; it does not import whole example archives or tools.
Original copyright/license headers in copied files are retained unchanged.

| Files | Source | License evidence in selected material |
| --- | --- | --- |
| rtl/vendor/acz7015_ch62/ | ACZ7015 ch62_acz7015_ov5640x2_udp_rgmii board example | Vendor/author headers; no standalone distribution license located |
| vivado/ip_repo/rgb2lcd, rgb565to888 | ACZ7015 ch19 RGB TFT HDMI display example | No standalone distribution license located |
| vivado/ip_repo/axi_dynclk_v1_0 | Digilent dynamic-clock/display code, as shipped with the board examples | BSD 3-clause text in C driver headers; per-file Xilinx notices also apply |
| vivado/ip/*.xci | Existing Vivado 2025.2 configuration inputs | AMD tool-generated configuration, not generated core implementations |
| Exported HDMI baseline bit/HWH | Historical ch19-derived ACZ7015 build | Contains generated/vendor IP; board-tested binary, not relicensed here |

The absence of a standalone license must not be represented as an open-source
grant. Public redistribution permission for the board-vendor source and derived
artifacts has not been established by this migration. Resolve it before public
publication. No blanket license is added over vendor material.

User-suggested repositories were reviewed as references during HDMI work:

- https://github.com/briansune/Artix-7-Parallel-OV5640
- https://github.com/luyixdu/ZYNQ_ov5640_hdmi_frame_difference
- https://github.com/laperex/image_processing_fpga

No files from these repositories are copied by this migration. The last repository
is a future color-processing reference, not an implemented dependency. No new
dependency on them is introduced for building or running the migrated prototype.
