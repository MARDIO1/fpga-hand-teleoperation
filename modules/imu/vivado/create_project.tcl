set script_dir [file dirname [file normalize [info script]]]
set root [file dirname $script_dir]
set output [file join $script_dir output]
set reports [file join $script_dir reports]
file mkdir $output
file mkdir $reports
create_project -force mpu6050_studio [file join $script_dir project] -part xc7z015clg485-2
set_property target_language Verilog [current_project]
add_files -norecurse [glob [file join $root rtl *.v]]
add_files -fileset constrs_1 -norecurse [file join $script_dir mpu6050.xdc]
update_compile_order -fileset sources_1
create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* ps7]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_EN_CLK0_PORT {1} CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41K256M16 RE-125} \
    CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH {32 Bit}] $ps
make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7/FIXED_IO]
set imu [create_bd_cell -type module -reference mpu6050_axi imu]
# Standalone test drains packets; the same packet is readable at 0xC0..0xFC.
# Final integration connects m_axis to a FIFO/DMA/fusion stream instead.
set ready [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* packet_ready]
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] $ready
connect_bd_net [get_bd_pins packet_ready/dout] [get_bd_pins imu/m_axis_tready]
set axi [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* control_axi]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $axi
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* ps_reset]
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins control_axi/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control_axi/M00_AXI] [get_bd_intf_pins imu/s_axi]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ps7/M_AXI_GP0_ACLK] \
    [get_bd_pins control_axi/ACLK] [get_bd_pins control_axi/S00_ACLK] \
    [get_bd_pins control_axi/M00_ACLK] [get_bd_pins ps_reset/slowest_sync_clk] \
    [get_bd_pins imu/s_axi_aclk]
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins ps_reset/ext_reset_in]
connect_bd_net [get_bd_pins ps_reset/peripheral_aresetn] [get_bd_pins control_axi/ARESETN] \
    [get_bd_pins control_axi/S00_ARESETN] [get_bd_pins control_axi/M00_ARESETN] \
    [get_bd_pins imu/s_axi_aresetn]
foreach pin {mpu_scl mpu_sda} {
    set port [create_bd_port -dir IO $pin]
    connect_bd_net $port [get_bd_pins imu/$pin]
}
set segments [get_bd_addr_segs -of_objects [get_bd_intf_pins imu/s_axi]]
assign_bd_address -offset 0x43C10000 -range 0x1000 \
    -target_address_space [get_bd_addr_spaces ps7/Data] $segments -force
validate_bd_design
save_bd_design
set bd [get_files system.bd]
generate_target all $bd
add_files -norecurse [make_wrapper -files $bd -top]
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
if {[lsearch -exact $argv build] >= 0} {
    launch_runs synth_1 -jobs 2
    wait_on_run synth_1
    if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} { error "Synthesis failed" }
    launch_runs impl_1 -to_step write_bitstream -jobs 2
    wait_on_run impl_1
    if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} { error "Implementation failed" }
    open_run impl_1
    report_timing_summary -file [file join $reports timing_summary.rpt]
    report_utilization -file [file join $reports utilization.rpt]
    report_drc -file [file join $reports drc.rpt]
    set slack [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
    if {$slack < 0} { error "Timing failed: WNS=$slack" }
    set project_dir [file join $script_dir project]
    file copy -force [file join $project_dir mpu6050_studio.runs impl_1 system_wrapper.bit] \
        [file join $output mpu6050.bit]
    file copy -force [file join $project_dir mpu6050_studio.gen sources_1 bd system hw_handoff system.hwh] \
        [file join $output mpu6050.hwh]
    puts "MPU6050_BUILD_OK WNS=$slack"
}
