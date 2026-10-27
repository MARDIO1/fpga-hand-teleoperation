set here [file normalize [file dirname [info script]]]
set_param general.maxThreads 2
set camera_dir [file join $here camera]
set geometry_dir [file join $camera_dir hls_geometry]
set root $here
set project_dir [file join $here output project]
if {[info exists ::env(VISION_OPTIMIZED_PROJECT)]} {set project_dir $::env(VISION_OPTIMIZED_PROJECT)}
set output_dir [file join $here output release]
file mkdir $output_dir
create_project -force vxyz $project_dir -part xc7z015clg485-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list [file join $here ip markers] [file join $here ip geometry]] [current_project]
update_ip_catalog
set vendor [file join $here vendor]
foreach name {pll dc_fifo} {
 file mkdir [file join $project_dir source_ip $name]
 file copy -force [file join $camera_dir ip $name ${name}.xci] [file join $project_dir source_ip $name ${name}.xci]
}
foreach src [list [file join $camera_dir stereo_camera_axis.v] [file join $camera_dir stereo_line_controller.v] [file join $camera_dir hls_markers marker_axis_bridge.v] [file join $vendor cache.v] [file join $vendor Camera_ETH_Formator.v] [file join $vendor camera_init camera_init.v] [file join $vendor camera_init ov5640_init_table_rgb.v] [file join $vendor camera_init ov5640_init_table_jpeg.v] [file join $vendor camera_init ov7725_init_table_rgb.v] [file join $vendor camera_init i2c_control i2c_control.v] [file join $vendor camera_init i2c_control i2c_bit_shift.v] [file join $project_dir source_ip pll pll.xci] [file join $project_dir source_ip dc_fifo dc_fifo.xci]] {add_files -norecurse $src}
add_files -fileset constrs_1 -norecurse [file join $camera_dir camera_pins.xdc]
generate_target all [get_ips]
update_compile_order -fileset sources_1
add_files -norecurse [list [file join $here rtl marker_ddr_eye_reader_fifo.sv] [file join $here rtl marker_ingress_control_v2.v]]
update_compile_order -fileset sources_1
create_bd_design system
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* ps7
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 1 CONFIG.PCW_USE_S_AXI_HP0 1 CONFIG.PCW_S_AXI_HP0_DATA_WIDTH 64 CONFIG.PCW_DDR_RAM_HIGHADDR 0x3FFFFFFF CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ 100.000000] [get_bd_cells ps7]
create_bd_cell -type module -reference stereo_camera_axis camera
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_vdma:* capture_vdma
set_property -dict [list CONFIG.c_include_sg 0 CONFIG.c_num_fstores 1 CONFIG.c_include_mm2s 0 CONFIG.c_include_s2mm 1 CONFIG.c_include_s2mm_dre 0 CONFIG.c_include_s2mm_sf 0 CONFIG.c_m_axi_s2mm_data_width 64 CONFIG.c_s2mm_linebuffer_depth 4096 CONFIG.c_s2mm_max_burst_length 64 CONFIG.c_s2mm_sof_enable 1 CONFIG.c_use_s2mm_fsync 2] [get_bd_cells capture_vdma]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* camera_gpio
set_property -dict [list CONFIG.C_ALL_INPUTS 1 CONFIG.C_GPIO_WIDTH 32 CONFIG.C_IS_DUAL 1 CONFIG.C_ALL_INPUTS_2 1 CONFIG.C_GPIO2_WIDTH 32] [get_bd_cells camera_gpio]
create_bd_cell -type ip -vlnv xilinx.com:hls:glove_markers:1.0 markers
create_bd_cell -type ip -vlnv xilinx.com:hls:marker_geometry:1.0 marker_geometry
create_bd_cell -type module -reference marker_axis_bridge marker_bridge
create_bd_cell -type module -reference marker_ingress_control_v2 ingress
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:* marker_dma
set_property -dict [list CONFIG.c_include_sg 0 CONFIG.c_include_mm2s 0 CONFIG.c_include_s2mm 1 CONFIG.c_sg_length_width 23 CONFIG.c_m_axis_mm2s_tdata_width 16 CONFIG.c_s_axis_s2mm_tdata_width 64 CONFIG.c_m_axi_mm2s_data_width 64 CONFIG.c_m_axi_s2mm_data_width 64] [get_bd_cells marker_dma]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* ctrl_ic
set_property -dict [list CONFIG.NUM_SI 1 CONFIG.NUM_MI 6] [get_bd_cells ctrl_ic]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* mem_ic
set_property -dict [list CONFIG.NUM_SI 3 CONFIG.NUM_MI 1] [get_bd_cells mem_ic]
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* rst_100m
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* locked
set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 1] [get_bd_cells locked]
foreach name {DDR FIXED_IO} {make_bd_intf_pins_external [get_bd_intf_pins ps7/$name];set_property name $name [get_bd_intf_ports ${name}_0]}
make_bd_pins_external [get_bd_pins camera/clk_50m];set_property name clk [get_bd_ports clk_50m_0]
foreach pin {camera1_sclk camera1_sdat camera1_vsync camera1_href camera1_pclk camera1_xclk camera1_data camera1_rst_n camera1_pwdn camera2_sclk camera2_sdat camera2_vsync camera2_href camera2_pclk camera2_xclk camera2_data camera2_rst_n camera2_pwdn} {make_bd_pins_external [get_bd_pins camera/$pin];set_property name $pin [get_bd_ports ${pin}_0]}
foreach {a b} {
 ps7/M_AXI_GP0 ctrl_ic/S00_AXI
 ctrl_ic/M00_AXI capture_vdma/S_AXI_LITE
 ctrl_ic/M01_AXI camera_gpio/S_AXI
 ctrl_ic/M02_AXI marker_dma/S_AXI_LITE
 ctrl_ic/M03_AXI markers/s_axi_control
 ctrl_ic/M04_AXI marker_geometry/s_axi_control
 camera/M_AXIS ingress/CAM_IN
 ingress/CAP_OUT capture_vdma/S_AXIS_S2MM
 ctrl_ic/M05_AXI ingress/S_AXI
 capture_vdma/M_AXI_S2MM mem_ic/S00_AXI
 ingress/M_AXI mem_ic/S01_AXI
 marker_dma/M_AXI_S2MM mem_ic/S02_AXI
 mem_ic/M00_AXI ps7/S_AXI_HP0
 ingress/VIDEO_OUT markers/pixels
 markers/regions marker_bridge/REGIONS_IN
 marker_bridge/DMA_OUT marker_dma/S_AXIS_S2MM
} {connect_bd_intf_net [get_bd_intf_pins $a] [get_bd_intf_pins $b]}
connect_bd_net [get_bd_pins camera/overflow_count] [get_bd_pins camera_gpio/gpio_io_i]
connect_bd_net [get_bd_pins camera/source_frame_count] [get_bd_pins camera_gpio/gpio2_io_i]
foreach pin {ps7/M_AXI_GP0_ACLK ps7/S_AXI_HP0_ACLK camera/axis_clk capture_vdma/s_axi_lite_aclk capture_vdma/m_axi_s2mm_aclk capture_vdma/s_axis_s2mm_aclk camera_gpio/s_axi_aclk markers/ap_clk marker_geometry/ap_clk marker_bridge/clk ingress/clk marker_dma/s_axi_lite_aclk marker_dma/m_axi_s2mm_aclk ctrl_ic/ACLK ctrl_ic/S00_ACLK mem_ic/ACLK mem_ic/M00_ACLK rst_100m/slowest_sync_clk} {connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins $pin]}
foreach n {00 01 02 03 04 05} {connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ctrl_ic/M${n}_ACLK]}
foreach n {00 01 02} {connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins mem_ic/S${n}_ACLK]}
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins rst_100m/ext_reset_in]
connect_bd_net [get_bd_pins locked/dout] [get_bd_pins rst_100m/dcm_locked]
foreach pin {camera/axis_resetn capture_vdma/axi_resetn camera_gpio/s_axi_aresetn marker_geometry/ap_rst_n ingress/resetn ctrl_ic/ARESETN ctrl_ic/S00_ARESETN mem_ic/ARESETN mem_ic/M00_ARESETN} {connect_bd_net [get_bd_pins rst_100m/peripheral_aresetn] [get_bd_pins $pin]}
foreach n {00 01 02 03 04 05} {connect_bd_net [get_bd_pins rst_100m/peripheral_aresetn] [get_bd_pins ctrl_ic/M${n}_ARESETN]}
foreach n {00 01 02} {connect_bd_net [get_bd_pins rst_100m/peripheral_aresetn] [get_bd_pins mem_ic/S${n}_ARESETN]}
connect_bd_net [get_bd_pins ingress/branch_resetn] [get_bd_pins markers/ap_rst_n] [get_bd_pins marker_bridge/resetn] [get_bd_pins marker_dma/axi_resetn]
# The old bridge is retained only as the unchanged 320-to-64 result packer.
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* zero16
set_property -dict [list CONFIG.CONST_WIDTH 16 CONFIG.CONST_VAL 0] [get_bd_cells zero16]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* zero2
set_property -dict [list CONFIG.CONST_WIDTH 2 CONFIG.CONST_VAL 0] [get_bd_cells zero2]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* zero1
set_property -dict [list CONFIG.CONST_WIDTH 1 CONFIG.CONST_VAL 0] [get_bd_cells zero1]
connect_bd_net [get_bd_pins zero16/dout] [get_bd_pins marker_bridge/s_tdata]
connect_bd_net [get_bd_pins zero2/dout] [get_bd_pins marker_bridge/s_tkeep]
connect_bd_net [get_bd_pins zero1/dout] [get_bd_pins marker_bridge/s_tvalid] [get_bd_pins marker_bridge/s_tlast] [get_bd_pins marker_bridge/v_tready]
assign_bd_address
foreach {cell intf address} {capture_vdma S_AXI_LITE 0x43000000 camera_gpio S_AXI 0x41200000 marker_dma S_AXI_LITE 0x40400000 markers s_axi_control 0x43C20000 marker_geometry s_axi_control 0x43C40000 ingress S_AXI 0x43C60000} {assign_bd_address -offset $address -range 0x10000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs $cell/$intf/*] -force}
validate_bd_design
save_bd_design
set bd [get_files system.bd];generate_target all $bd;make_wrapper -files $bd -top
add_files -norecurse [file join $project_dir vxyz.gen sources_1 bd system hdl system_wrapper.v]
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
source [file join $here finish_ingress.tcl]
