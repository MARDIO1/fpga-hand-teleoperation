# ACZ7015 full integration: optimized stereo XYZ, MPU6050 and hand_core.
# This creates a new top-level image; standalone module projects remain unchanged.

set script_dir [file dirname [file normalize [info script]]]
set repo_root [file normalize [file join $script_dir ../..]]
set vision_dir [file join $repo_root modules vision vivado optimized_xyz]
set camera_dir [file join $vision_dir camera]
set project_dir [file join $repo_root .vivado full_board]
if {[info exists ::env(FULL_BOARD_PROJECT)]} {
    set project_dir [file normalize $::env(FULL_BOARD_PROJECT)]
}
set output_dir [file join $script_dir full_output]
set reports_dir [file join $script_dir full_reports]
set fusion_ip [file join $repo_root modules fusion build hls impl ip]
set imu_ip [file join $repo_root modules imu export ip v0.1.0]
set marker_ip [file join $vision_dir ip markers]
set geometry_ip [file join $vision_dir ip geometry]

# The standalone camera constraints also contain its mode button and a second
# definition of the 50 MHz input clock. Neither belongs to this top level.
set camera_xdc [file join $project_dir camera_pins.xdc]
file mkdir [file dirname $camera_xdc]
set source_xdc [open [file join $camera_dir camera_pins.xdc] r]
set target_xdc [open $camera_xdc w]
while {[gets $source_xdc line] >= 0} {
    if {![regexp {mode_button|^create_clock} $line]} { puts $target_xdc $line }
}
close $source_xdc
close $target_xdc

foreach component [list \
        [file join $fusion_ip component.xml] \
        [file join $imu_ip component.xml] \
        [file join $marker_ip component.xml] \
        [file join $geometry_ip component.xml]] {
    if {![file exists $component]} { error "Missing packaged IP: $component" }
}

set_param general.maxThreads 2
file mkdir $output_dir
file mkdir $reports_dir
create_project -force full_board $project_dir -part xc7z015clg485-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list $marker_ip $geometry_ip $fusion_ip $imu_ip] [current_project]
update_ip_catalog

# The camera's PLL/FIFO XCI files are copied so the module release stays immutable.
foreach name {pll dc_fifo} {
    set target [file join $project_dir source_ip $name]
    file mkdir $target
    file copy -force [file join $camera_dir ip $name ${name}.xci] \
        [file join $target ${name}.xci]
}
set vendor [file join $vision_dir vendor]
foreach src [list \
        [file join $camera_dir stereo_camera_axis.v] \
        [file join $camera_dir stereo_line_controller.v] \
        [file join $camera_dir hls_markers marker_axis_bridge.v] \
        [file join $vendor cache.v] \
        [file join $vendor Camera_ETH_Formator.v] \
        [file join $vendor camera_init camera_init.v] \
        [file join $vendor camera_init ov5640_init_table_rgb.v] \
        [file join $vendor camera_init ov5640_init_table_jpeg.v] \
        [file join $vendor camera_init ov7725_init_table_rgb.v] \
        [file join $vendor camera_init i2c_control i2c_control.v] \
        [file join $vendor camera_init i2c_control i2c_bit_shift.v] \
        [file join $project_dir source_ip pll pll.xci] \
        [file join $project_dir source_ip dc_fifo dc_fifo.xci]] {
    add_files -norecurse [list $src]
}
add_files -norecurse [list \
    [file join $vision_dir rtl marker_ddr_eye_reader_fifo.sv] \
    [file join $vision_dir rtl marker_ingress_control_v2.v] \
    [file join $script_dir camera_frame_probe.v]]
add_files -fileset constrs_1 -norecurse [list \
    $camera_xdc \
    [file join $script_dir first_board.xdc]]
generate_target all [get_ips]
update_compile_order -fileset sources_1

create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* ps7]
set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 1 \
    CONFIG.PCW_USE_S_AXI_HP0 1 \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH 64 \
    CONFIG.PCW_DDR_RAM_HIGHADDR 0x3FFFFFFF \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ 100.000000 \
    CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41K256M16 RE-125} \
    CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH {32 Bit}] $ps

create_bd_cell -type module -reference stereo_camera_axis camera
set capture_vdma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_vdma:* capture_vdma]
set_property -dict [list CONFIG.c_include_sg 0 CONFIG.c_num_fstores 1 \
    CONFIG.c_include_mm2s 0 CONFIG.c_include_s2mm 1 CONFIG.c_include_s2mm_dre 0 \
    CONFIG.c_include_s2mm_sf 0 CONFIG.c_m_axi_s2mm_data_width 64 \
    CONFIG.c_s2mm_linebuffer_depth 4096 CONFIG.c_s2mm_max_burst_length 64 \
    CONFIG.c_s2mm_sof_enable 1 CONFIG.c_use_s2mm_fsync 2] $capture_vdma
set camera_gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* camera_gpio]
set_property -dict [list CONFIG.C_ALL_INPUTS 1 CONFIG.C_GPIO_WIDTH 32 \
    CONFIG.C_IS_DUAL 1 CONFIG.C_ALL_INPUTS_2 1 CONFIG.C_GPIO2_WIDTH 32] $camera_gpio
set camera_debug [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* camera_debug]
set_property -dict [list CONFIG.C_ALL_INPUTS 1 CONFIG.C_GPIO_WIDTH 32 \
    CONFIG.C_IS_DUAL 1 CONFIG.C_ALL_INPUTS_2 1 CONFIG.C_GPIO2_WIDTH 32] $camera_debug
create_bd_cell -type module -reference camera_frame_probe camera_probe
create_bd_cell -type ip -vlnv xilinx.com:hls:glove_markers:1.0 markers
create_bd_cell -type ip -vlnv xilinx.com:hls:marker_geometry:1.0 marker_geometry
create_bd_cell -type module -reference marker_axis_bridge marker_bridge
create_bd_cell -type module -reference marker_ingress_control_v2 ingress
set marker_dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:* marker_dma]
set_property -dict [list CONFIG.c_include_sg 0 CONFIG.c_include_mm2s 0 \
    CONFIG.c_include_s2mm 1 CONFIG.c_sg_length_width 23 \
    CONFIG.c_m_axis_mm2s_tdata_width 16 CONFIG.c_s_axis_s2mm_tdata_width 64 \
    CONFIG.c_m_axi_mm2s_data_width 64 CONFIG.c_m_axi_s2mm_data_width 64] $marker_dma
create_bd_cell -type ip -vlnv xilinx.com:hls:hand_core:1.0 hand_core
create_bd_cell -type ip -vlnv local.fpga:sensor:mpu6050_imu:1.0 imu

set ctrl_ic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* ctrl_ic]
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 9] $ctrl_ic
set mem_ic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* mem_ic]
set_property -dict [list CONFIG.NUM_SI 3 CONFIG.NUM_MI 1] $mem_ic
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* rst_100m
foreach {name width value} {locked 1 1 packet_ready 1 1 zero16 16 0 zero2 2 0 zero1 1 0} {
    create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* $name
    set_property -dict [list CONFIG.CONST_WIDTH $width CONFIG.CONST_VAL $value] [get_bd_cells $name]
}

foreach name {DDR FIXED_IO} {
    make_bd_intf_pins_external [get_bd_intf_pins ps7/$name]
    set_property name $name [get_bd_intf_ports ${name}_0]
}
make_bd_pins_external [get_bd_pins camera/clk_50m]
set_property name clk [get_bd_ports clk_50m_0]
foreach pin {camera1_sclk camera1_sdat camera1_vsync camera1_href camera1_pclk \
        camera1_xclk camera1_data camera1_rst_n camera1_pwdn camera2_sclk \
        camera2_sdat camera2_vsync camera2_href camera2_pclk camera2_xclk \
        camera2_data camera2_rst_n camera2_pwdn} {
    make_bd_pins_external [get_bd_pins camera/$pin]
    set_property name $pin [get_bd_ports ${pin}_0]
}
foreach pin {mpu_scl mpu_sda} {
    set port [create_bd_port -dir IO $pin]
    connect_bd_net $port [get_bd_pins imu/$pin]
}

foreach {a b} {
    ps7/M_AXI_GP0 ctrl_ic/S00_AXI
    ctrl_ic/M00_AXI capture_vdma/S_AXI_LITE
    ctrl_ic/M01_AXI camera_gpio/S_AXI
    ctrl_ic/M02_AXI marker_dma/S_AXI_LITE
    ctrl_ic/M03_AXI markers/s_axi_control
    ctrl_ic/M04_AXI marker_geometry/s_axi_control
    ctrl_ic/M05_AXI ingress/S_AXI
    ctrl_ic/M06_AXI hand_core/s_axi_control
    ctrl_ic/M07_AXI imu/s_axi
    ctrl_ic/M08_AXI camera_debug/S_AXI
    camera/M_AXIS ingress/CAM_IN
    ingress/CAP_OUT capture_vdma/S_AXIS_S2MM
    capture_vdma/M_AXI_S2MM mem_ic/S00_AXI
    ingress/M_AXI mem_ic/S01_AXI
    marker_dma/M_AXI_S2MM mem_ic/S02_AXI
    mem_ic/M00_AXI ps7/S_AXI_HP0
    ingress/VIDEO_OUT markers/pixels
    markers/regions marker_bridge/REGIONS_IN
    marker_bridge/DMA_OUT marker_dma/S_AXIS_S2MM
} {
    connect_bd_intf_net [get_bd_intf_pins $a] [get_bd_intf_pins $b]
}
connect_bd_net [get_bd_pins camera/overflow_count] [get_bd_pins camera_gpio/gpio_io_i]
connect_bd_net [get_bd_pins camera/source_frame_count] [get_bd_pins camera_gpio/gpio2_io_i]
connect_bd_net [get_bd_ports camera1_pclk] [get_bd_pins camera_probe/camera1_pclk]
connect_bd_net [get_bd_ports camera1_vsync] [get_bd_pins camera_probe/camera1_vsync]
connect_bd_net [get_bd_ports camera2_pclk] [get_bd_pins camera_probe/camera2_pclk]
connect_bd_net [get_bd_ports camera2_vsync] [get_bd_pins camera_probe/camera2_vsync]
connect_bd_net [get_bd_pins camera_probe/camera1_frames] [get_bd_pins camera_debug/gpio_io_i]
connect_bd_net [get_bd_pins camera_probe/camera2_frames] [get_bd_pins camera_debug/gpio2_io_i]
connect_bd_net [get_bd_pins packet_ready/dout] [get_bd_pins imu/m_axis_tready]
connect_bd_net [get_bd_pins zero16/dout] [get_bd_pins marker_bridge/s_tdata]
connect_bd_net [get_bd_pins zero2/dout] [get_bd_pins marker_bridge/s_tkeep]
connect_bd_net [get_bd_pins zero1/dout] [get_bd_pins marker_bridge/s_tvalid] \
    [get_bd_pins marker_bridge/s_tlast] [get_bd_pins marker_bridge/v_tready]

set clock_pins {ps7/M_AXI_GP0_ACLK ps7/S_AXI_HP0_ACLK camera/axis_clk \
    capture_vdma/s_axi_lite_aclk capture_vdma/m_axi_s2mm_aclk \
    capture_vdma/s_axis_s2mm_aclk camera_gpio/s_axi_aclk camera_debug/s_axi_aclk markers/ap_clk \
    marker_geometry/ap_clk marker_bridge/clk ingress/clk \
    marker_dma/s_axi_lite_aclk marker_dma/m_axi_s2mm_aclk hand_core/ap_clk \
    imu/s_axi_aclk ctrl_ic/ACLK ctrl_ic/S00_ACLK mem_ic/ACLK mem_ic/M00_ACLK \
    rst_100m/slowest_sync_clk}
foreach pin $clock_pins {
    connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins $pin]
}
foreach n {00 01 02 03 04 05 06 07 08} {
    connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ctrl_ic/M${n}_ACLK]
}
foreach n {00 01 02} {
    connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins mem_ic/S${n}_ACLK]
}
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins rst_100m/ext_reset_in]
connect_bd_net [get_bd_pins locked/dout] [get_bd_pins rst_100m/dcm_locked]
set reset_pins {camera/axis_resetn camera_probe/resetn capture_vdma/axi_resetn camera_gpio/s_axi_aresetn \
    camera_debug/s_axi_aresetn \
    marker_geometry/ap_rst_n ingress/resetn hand_core/ap_rst_n imu/s_axi_aresetn \
    ctrl_ic/ARESETN ctrl_ic/S00_ARESETN mem_ic/ARESETN mem_ic/M00_ARESETN}
foreach pin $reset_pins {
    connect_bd_net [get_bd_pins rst_100m/peripheral_aresetn] [get_bd_pins $pin]
}
foreach n {00 01 02 03 04 05 06 07 08} {
    connect_bd_net [get_bd_pins rst_100m/peripheral_aresetn] [get_bd_pins ctrl_ic/M${n}_ARESETN]
}
foreach n {00 01 02} {
    connect_bd_net [get_bd_pins rst_100m/peripheral_aresetn] [get_bd_pins mem_ic/S${n}_ARESETN]
}
# ingress owns branch reset for the streaming marker path.
connect_bd_net [get_bd_pins ingress/branch_resetn] [get_bd_pins markers/ap_rst_n] \
    [get_bd_pins marker_bridge/resetn] [get_bd_pins marker_dma/axi_resetn]

assign_bd_address
foreach {cell intf address range} {
    capture_vdma S_AXI_LITE 0x43000000 0x00010000
    camera_gpio S_AXI 0x41200000 0x00010000
    marker_dma S_AXI_LITE 0x40400000 0x00010000
    markers s_axi_control 0x43C20000 0x00010000
    marker_geometry s_axi_control 0x43C40000 0x00010000
    ingress S_AXI 0x43C60000 0x00010000
    hand_core s_axi_control 0x43C00000 0x00001000
    imu s_axi 0x43C10000 0x00001000
    camera_debug S_AXI 0x41210000 0x00010000
} {
    assign_bd_address -offset $address -range $range \
        -target_address_space [get_bd_addr_spaces ps7/Data] \
        [get_bd_addr_segs $cell/$intf/*] -force
}

validate_bd_design
save_bd_design
set bd [get_files system.bd]
generate_target all $bd
add_files -norecurse [make_wrapper -files $bd -top]
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1

if {[lsearch -exact $argv build] >= 0} {
    # Parallel OOC workers intermittently crash on exit on this Windows host
    # after writing a valid DCP. One worker is slower but deterministic.
    launch_runs synth_1 -jobs 1
    wait_on_run synth_1
    if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {
        error "Synthesis failed: [get_property STATUS [get_runs synth_1]]"
    }
    launch_runs impl_1 -to_step write_bitstream -jobs 1
    wait_on_run impl_1
    if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {
        error "Implementation failed: [get_property STATUS [get_runs impl_1]]"
    }
    open_run impl_1
    report_timing_summary -file [file join $reports_dir timing_summary.rpt]
    report_utilization -file [file join $reports_dir utilization.rpt]
    report_drc -file [file join $reports_dir drc.rpt]
    set setup_slack [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
    set hold_slack [get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]
    if {$setup_slack < 0 || $hold_slack < 0} {
        error "Timing failed: setup=$setup_slack hold=$hold_slack"
    }
    file copy -force [file join $project_dir full_board.runs impl_1 system_wrapper.bit] \
        [file join $output_dir full_board.bit]
    file copy -force [file join $project_dir full_board.gen sources_1 bd system hw_handoff system.hwh] \
        [file join $output_dir full_board.hwh]
    write_hw_platform -fixed -include_bit -force -file [file join $output_dir full_board.xsa]
    set map [open [file join $output_dir address_map.txt] w]
    foreach line {
        {hand_core 0x43C00000 0x00001000}
        {mpu6050_imu 0x43C10000 0x00001000}
        {camera_gpio 0x41200000 0x00010000}
        {camera_debug 0x41210000 0x00010000}
        {marker_dma 0x40400000 0x00010000}
        {capture_vdma 0x43000000 0x00010000}
        {glove_markers 0x43C20000 0x00010000}
        {marker_geometry 0x43C40000 0x00010000}
        {marker_ingress 0x43C60000 0x00010000}
    } { puts $map $line }
    close $map
    puts "FULL_BOARD_BUILD_OK setup=$setup_slack hold=$hold_slack"
}
