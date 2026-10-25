set script_dir [file dirname [file normalize [info script]]]
set root [file dirname $script_dir]
set destination [file join $script_dir output ip]
create_project -force mpu6050_ip_package [file join $script_dir project ip_package] -part xc7z015clg485-2
add_files -norecurse [glob [file join $root rtl *.v]]
set_property top mpu6050_axi [current_fileset]
update_compile_order -fileset sources_1
ipx::package_project -root_dir $destination -vendor local.fpga -library sensor \
    -taxonomy /UserIP -import_files -set_current true
set core [ipx::current_core]
set_property name mpu6050_imu $core
set_property display_name {MPU6050 acquisition and attitude packet} $core
set_property description {I2C acquisition with PL timestamps, ARM pose writeback and atomic raw+pose AXI4-Stream output} $core
set_property version 1.0 $core
ipx::associate_bus_interfaces -busif s_axi -clock s_axi_aclk $core
ipx::associate_bus_interfaces -busif m_axis -clock s_axi_aclk $core
ipx::create_xgui_files $core
ipx::check_integrity $core
ipx::save_core $core
puts "MPU6050_IP_PACKAGED $destination"
