set script_dir [file normalize [file dirname [info script]]]
set project_dir [file join $script_dir project hdmi_baseline]
set output_dir [file join $script_dir output hdmi_baseline]
set ip_repo [file normalize [file join $script_dir ip_repo]]
file mkdir $output_dir

create_project -force pl_hdmi_official_baseline $project_dir -part xc7z015clg485-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog
add_files -fileset constrs_1 -norecurse [file join $script_dir constraints hdmi.xdc]
update_compile_order -fileset sources_1

create_bd_design system
set ps7 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* ps7]
set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} \
    CONFIG.PCW_DDR_RAM_HIGHADDR {0x3FFFFFFF} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000} \
    CONFIG.PCW_I2C1_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_I2C1_I2C1_IO {EMIO} \
] $ps7

set display_vdma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_vdma:* display_vdma]
set_property -dict [list \
    CONFIG.c_include_sg {0} CONFIG.c_num_fstores {1} \
    CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {0} \
    CONFIG.c_include_mm2s_dre {0} CONFIG.c_include_mm2s_sf {0} \
    CONFIG.c_m_axi_mm2s_data_width {64} \
    CONFIG.c_m_axis_mm2s_tdata_width {16} \
    CONFIG.c_mm2s_linebuffer_depth {1024} \
    CONFIG.c_mm2s_max_burst_length {64} \
] $display_vdma

set rgb565 [create_bd_cell -type ip -vlnv xilinx.com:user:rgb565to888:1.0 rgb565to888]
set vidout [create_bd_cell -type ip -vlnv xilinx.com:ip:v_axi4s_vid_out:* vidout]
set_property -dict [list CONFIG.C_HAS_ASYNC_CLK {1}] $vidout
set vtc [create_bd_cell -type ip -vlnv xilinx.com:ip:v_tc:* vtc]
set_property -dict [list CONFIG.enable_detection {false}] $vtc
set rgb2lcd [create_bd_cell -type ip -vlnv www.xilinx.com:user:rgb2lcd:1.0 rgb2lcd]
set dynclk [create_bd_cell -type ip -vlnv digilentinc.com:ip:axi_dynclk:1.0 dynclk]
set video_status [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* video_status]
set_property -dict [list CONFIG.C_ALL_INPUTS {1} CONFIG.C_GPIO_WIDTH {32} \
    CONFIG.C_IS_DUAL {1} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_GPIO2_WIDTH {1}] $video_status

set ctrl_ic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* ctrl_ic]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {4}] $ctrl_ic
set mem_smc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:* mem_smc]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $mem_smc
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* rst_100m]
set locked [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* const_locked]
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] $locked

make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7/FIXED_IO]
make_bd_intf_pins_external [get_bd_intf_pins ps7/IIC_1]
make_bd_intf_pins_external [get_bd_intf_pins rgb2lcd/lcd]
set_property name DDR [get_bd_intf_ports DDR_0]
set_property name FIXED_IO [get_bd_intf_ports FIXED_IO_0]

connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins ctrl_ic/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M00_AXI] [get_bd_intf_pins dynclk/s00_axi]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M01_AXI] [get_bd_intf_pins vtc/ctrl]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M02_AXI] [get_bd_intf_pins display_vdma/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M03_AXI] [get_bd_intf_pins video_status/S_AXI]

connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXI_MM2S] [get_bd_intf_pins mem_smc/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins mem_smc/M00_AXI] [get_bd_intf_pins ps7/S_AXI_HP0]
connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXIS_MM2S] [get_bd_intf_pins rgb565to888/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins rgb565to888/M_AXIS] [get_bd_intf_pins vidout/video_in]
connect_bd_intf_net [get_bd_intf_pins vidout/vid_io_out] [get_bd_intf_pins rgb2lcd/vid_rgb]
connect_bd_intf_net [get_bd_intf_pins vtc/vtiming_out] [get_bd_intf_pins vidout/vtiming_in]
connect_bd_net [get_bd_pins vidout/vtg_ce] [get_bd_pins vtc/gen_clken]
connect_bd_net [get_bd_pins vidout/status] [get_bd_pins video_status/gpio_io_i]
connect_bd_net [get_bd_pins vidout/locked] [get_bd_pins video_status/gpio2_io_i]

set fclk [get_bd_pins ps7/FCLK_CLK0]
foreach pin [list ps7/M_AXI_GP0_ACLK ps7/S_AXI_HP0_ACLK \
    display_vdma/s_axi_lite_aclk display_vdma/m_axi_mm2s_aclk display_vdma/m_axis_mm2s_aclk \
    rgb565to888/m_clk rgb565to888/s_clk vidout/aclk vtc/s_axi_aclk \
    dynclk/REF_CLK_I dynclk/s00_axi_aclk video_status/s_axi_aclk \
    ctrl_ic/ACLK ctrl_ic/S00_ACLK ctrl_ic/M00_ACLK ctrl_ic/M01_ACLK ctrl_ic/M02_ACLK \
    ctrl_ic/M03_ACLK mem_smc/aclk rst_100m/slowest_sync_clk] {
    connect_bd_net $fclk [get_bd_pins $pin]
}
set pclk [get_bd_pins dynclk/PXL_CLK_O]
connect_bd_net $pclk [get_bd_pins vidout/vid_io_out_clk]
connect_bd_net $pclk [get_bd_pins vtc/clk]
connect_bd_net $pclk [get_bd_pins rgb2lcd/pixel_clk]
connect_bd_net [get_bd_pins dynclk/LOCKED_O] [get_bd_pins rgb2lcd/vid_rst]

connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins rst_100m/ext_reset_in]
connect_bd_net [get_bd_pins const_locked/dout] [get_bd_pins rst_100m/dcm_locked]
set aresetn [get_bd_pins rst_100m/peripheral_aresetn]
foreach pin [list display_vdma/axi_resetn \
    dynclk/s00_axi_aresetn vtc/s_axi_aresetn video_status/s_axi_aresetn \
    ctrl_ic/ARESETN ctrl_ic/S00_ARESETN ctrl_ic/M00_ARESETN ctrl_ic/M01_ARESETN \
    ctrl_ic/M02_ARESETN ctrl_ic/M03_ARESETN mem_smc/aresetn] {
    connect_bd_net $aresetn [get_bd_pins $pin]
}

assign_bd_address
set_property offset 0x43C00000 [get_bd_addr_segs ps7/Data/SEG_dynclk_reg0]
set_property offset 0x43C10000 [get_bd_addr_segs ps7/Data/SEG_vtc_Reg]
set_property offset 0x43000000 [get_bd_addr_segs ps7/Data/SEG_display_vdma_Reg]
set_property offset 0x41200000 [get_bd_addr_segs ps7/Data/SEG_video_status_Reg]
validate_bd_design
save_bd_design

set bd_file [get_files system.bd]
generate_target all $bd_file
make_wrapper -files $bd_file -top
add_files -norecurse [file join $project_dir pl_hdmi_official_baseline.gen sources_1 bd system hdl system_wrapper.v]
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
write_bd_tcl -force [file join $output_dir system_bd.tcl]

if {[llength $argv] > 0 && [lindex $argv 0] eq "build"} {
    launch_runs impl_1 -to_step write_bitstream -jobs 1
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
        error "Implementation did not complete: [get_property STATUS [get_runs impl_1]]"
    }
    file copy -force [file join $project_dir pl_hdmi_official_baseline.runs impl_1 system_wrapper.bit] \
        [file join $output_dir pl_hdmi_official_baseline.bit]
    set hwh [file join $project_dir pl_hdmi_official_baseline.gen sources_1 bd system hw_handoff system.hwh]
    file copy -force $hwh [file join $output_dir pl_hdmi_official_baseline.hwh]
    write_hw_platform -fixed -include_bit -force -file [file join $output_dir pl_hdmi_official_baseline.xsa]
    open_run impl_1
    report_timing_summary -file [file join $output_dir timing_summary.rpt]
    report_utilization -file [file join $output_dir utilization.rpt]
}
puts "PROJECT_OK mode=[expr {[llength $argv] ? [lindex $argv 0] : {validate}}]"
exit
