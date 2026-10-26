# ACZ7015 first-board integration: MPU6050 acquisition plus hand fusion.
set script_dir [file dirname [file normalize [info script]]]
set repo_root [file normalize [file join $script_dir ../..]]
set project_dir [file join $script_dir project]
set output_dir [file join $script_dir output]
set reports_dir [file join $script_dir reports]
set fusion_ip [file join $repo_root modules fusion build hls impl ip]
set imu_ip [file join $repo_root modules imu export ip v0.1.0]

foreach component [list [file join $fusion_ip component.xml] [file join $imu_ip component.xml]] {
    if {![file exists $component]} { error "Missing packaged IP: $component" }
}

file mkdir $output_dir
file mkdir $reports_dir
create_project -force first_board $project_dir -part xc7z015clg485-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list $fusion_ip $imu_ip] [current_project]
update_ip_catalog
add_files -fileset constrs_1 -norecurse [list [file join $script_dir first_board.xdc]]

create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* ps7]
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_EN_CLK0_PORT {1} CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41K256M16 RE-125} \
    CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH {32 Bit}] $ps
make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7/FIXED_IO]

set fusion [create_bd_cell -type ip -vlnv xilinx.com:hls:hand_core:1.0 hand_core]
set imu [create_bd_cell -type ip -vlnv local.fpga:sensor:mpu6050_imu:1.0 imu]
set ready [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* packet_ready]
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] $ready
connect_bd_net [get_bd_pins packet_ready/dout] [get_bd_pins imu/m_axis_tready]

set axi [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* control_axi]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {2}] $axi
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* ps_reset]
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins control_axi/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control_axi/M00_AXI] [get_bd_intf_pins hand_core/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins control_axi/M01_AXI] [get_bd_intf_pins imu/s_axi]

connect_bd_net [get_bd_pins ps7/FCLK_CLK0] \
    [get_bd_pins ps7/M_AXI_GP0_ACLK] [get_bd_pins control_axi/ACLK] \
    [get_bd_pins control_axi/S00_ACLK] [get_bd_pins control_axi/M00_ACLK] \
    [get_bd_pins control_axi/M01_ACLK] [get_bd_pins ps_reset/slowest_sync_clk] \
    [get_bd_pins hand_core/ap_clk] [get_bd_pins imu/s_axi_aclk]
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins ps_reset/ext_reset_in]
connect_bd_net [get_bd_pins ps_reset/peripheral_aresetn] \
    [get_bd_pins control_axi/ARESETN] [get_bd_pins control_axi/S00_ARESETN] \
    [get_bd_pins control_axi/M00_ARESETN] [get_bd_pins control_axi/M01_ARESETN] \
    [get_bd_pins hand_core/ap_rst_n] [get_bd_pins imu/s_axi_aresetn]

foreach pin {mpu_scl mpu_sda} {
    set port [create_bd_port -dir IO $pin]
    connect_bd_net $port [get_bd_pins imu/$pin]
}

set fusion_segment [get_bd_addr_segs -of_objects [get_bd_intf_pins hand_core/s_axi_control]]
set imu_segment [get_bd_addr_segs -of_objects [get_bd_intf_pins imu/s_axi]]
assign_bd_address -offset 0x43C00000 -range 0x1000 \
    -target_address_space [get_bd_addr_spaces ps7/Data] $fusion_segment -force
assign_bd_address -offset 0x43C10000 -range 0x1000 \
    -target_address_space [get_bd_addr_spaces ps7/Data] $imu_segment -force

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
    if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {
        error "Synthesis failed: [get_property STATUS [get_runs synth_1]]"
    }
    launch_runs impl_1 -to_step write_bitstream -jobs 2
    wait_on_run impl_1
    if {[get_property STATUS [get_runs impl_1]] ne "write_bitstream Complete!"} {
        error "Implementation failed: [get_property STATUS [get_runs impl_1]]"
    }
    open_run impl_1
    report_timing_summary -file [file join $reports_dir timing_summary.rpt]
    report_utilization -file [file join $reports_dir utilization.rpt]
    report_drc -file [file join $reports_dir drc.rpt]
    set slack [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
    if {$slack < 0} { error "Timing failed: WNS=$slack" }
    file copy -force [file join $project_dir first_board.runs impl_1 system_wrapper.bit] \
        [file join $output_dir first_board.bit]
    file copy -force [file join $project_dir first_board.gen sources_1 bd system hw_handoff system.hwh] \
        [file join $output_dir first_board.hwh]
    write_hw_platform -fixed -include_bit -force -file [file join $output_dir first_board.xsa]
    set map [open [file join $output_dir address_map.txt] w]
    puts $map "hand_core 0x43C00000 0x00001000"
    puts $map "mpu6050_imu 0x43C10000 0x00001000"
    close $map
    puts "FIRST_BOARD_BUILD_OK WNS=$slack"
}
