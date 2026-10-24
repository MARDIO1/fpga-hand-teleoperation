# Rebuild the minimal ACZ7015 PS-to-hand_core overlay and export PYNQ artifacts.
set script_dir [file dirname [file normalize [info script]]]
set root_dir [file normalize [file join $script_dir ..]]
set project_dir [file join $script_dir project]
set output_dir [file join $script_dir output]
set reports_dir [file join $script_dir reports]
set ip_repo [file join $root_dir build hls impl ip]

if {![file exists [file join $ip_repo component.xml]]} {
    error "Missing HLS IP: $ip_repo/component.xml"
}

file mkdir $output_dir
file mkdir $reports_dir
create_project -force hand_core_overlay $project_dir -part xc7z015clg485-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list $ip_repo] [current_project]
update_ip_catalog

if {[llength [get_ipdefs -all -quiet xilinx.com:hls:hand_core:1.0]] != 1} {
    error "Expected one xilinx.com:hls:hand_core:1.0"
}

create_bd_design hand_system
set ps7 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* ps7]
set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41K256M16 RE-125} \
    CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH {32 Bit} \
    CONFIG.PCW_EN_CLK0_PORT {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000}] $ps7
make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR]
set_property name DDR [get_bd_intf_ports DDR_0]
make_bd_intf_pins_external [get_bd_intf_pins ps7/FIXED_IO]
set_property name FIXED_IO [get_bd_intf_ports FIXED_IO_0]

set core [create_bd_cell -type ip -vlnv xilinx.com:hls:hand_core:1.0 hand_core]
set axi [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* control_axi]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $axi
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* ps_reset]

connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins control_axi/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins control_axi/M00_AXI] [get_bd_intf_pins hand_core/s_axi_control]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] \
    [get_bd_pins ps7/M_AXI_GP0_ACLK] \
    [get_bd_pins control_axi/ACLK] \
    [get_bd_pins control_axi/S00_ACLK] \
    [get_bd_pins control_axi/M00_ACLK] \
    [get_bd_pins ps_reset/slowest_sync_clk] \
    [get_bd_pins hand_core/ap_clk]
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins ps_reset/ext_reset_in]
connect_bd_net [get_bd_pins ps_reset/peripheral_aresetn] \
    [get_bd_pins control_axi/ARESETN] \
    [get_bd_pins control_axi/S00_ARESETN] \
    [get_bd_pins control_axi/M00_ARESETN] \
    [get_bd_pins hand_core/ap_rst_n]

set segments [get_bd_addr_segs -quiet -of_objects [get_bd_intf_pins hand_core/s_axi_control]]
if {[llength $segments] != 1} {
    error "Expected one hand_core AXI segment, got: $segments"
}
assign_bd_address -offset 0x43C00000 -range 0x00001000 \
    -target_address_space [get_bd_addr_spaces ps7/Data] $segments -force
validate_bd_design
save_bd_design

set bd_file [get_files -quiet hand_system.bd]
if {[llength $bd_file] != 1} {
    error "Expected one hand_system.bd, got: $bd_file"
}
generate_target all $bd_file
set wrapper [make_wrapper -files $bd_file -top]
add_files -norecurse $wrapper
set_property top hand_system_wrapper [current_fileset]
update_compile_order -fileset sources_1

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
report_drc -file [file join $reports_dir drc.rpt]
report_timing_summary -file [file join $reports_dir timing_summary.rpt]
report_utilization -file [file join $reports_dir utilization.rpt]
write_checkpoint -force [file join $output_dir hand_core_post_route.dcp]
file copy -force \
    [file join $project_dir hand_core_overlay.runs impl_1 hand_system_wrapper.bit] \
    [file join $output_dir hand_core.bit]
write_hw_platform -fixed -include_bit -force -file [file join $output_dir hand_core.xsa]
file copy -force \
    [file join $project_dir hand_core_overlay.gen sources_1 bd hand_system hw_handoff hand_system.hwh] \
    [file join $output_dir hand_core.hwh]
write_bd_tcl -force [file join $output_dir recreate_hand_system.tcl]

set map_file [open [file join $output_dir address_map.txt] w]
puts $map_file "hand_core 0x43C00000 0x00001000"
close $map_file
puts "HAND_CORE_OVERLAY_BUILD_OK"
