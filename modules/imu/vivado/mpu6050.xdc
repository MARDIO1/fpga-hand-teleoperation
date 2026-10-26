# ACZ7015 GPIO0/P7: board master XDC GPIO0_0_tri_io[8:9].
set_property PACKAGE_PIN H5 [get_ports mpu_scl]
set_property PACKAGE_PIN H6 [get_ports mpu_sda]
set_property IOSTANDARD LVCMOS33 [get_ports {mpu_scl mpu_sda}]
# Use external 2.2k..4.7k pull-ups to 3.3 V on both lines.
