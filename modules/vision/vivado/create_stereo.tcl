set script_dir [file normalize [file dirname [info script]]]
set with_stream_depth [expr {[lsearch -exact $argv pl_stream] >= 0}]
set with_dma_depth [expr {[lsearch -exact $argv pl_depth] >= 0}]
set with_ch19_display [expr {[lsearch -exact $argv ch19_display] >= 0}]
if {$with_ch19_display && ($with_stream_depth || $with_dma_depth)} {
    error "ch19_display is a raw-video comparison build; do not combine with depth variants"
}
set with_pl_depth [expr {$with_stream_depth || $with_dma_depth}]
set project_name [expr {$with_stream_depth ? "pl_stereo_hdmi_stream_depth" : ($with_dma_depth ? "pl_stereo_hdmi_pl_depth" : "pl_stereo_hdmi")}]
set module_dir [file normalize [file join $script_dir ..]]
set variant [expr {$with_stream_depth ? "pl_stream" : ($with_dma_depth ? "pl_depth" : ($with_ch19_display ? "ch19_display" : "stereo"))}]
if {$with_ch19_display} { set project_name pl_stereo_hdmi_ch19 }
set project_dir [file join $script_dir project $variant]
set output_dir [file join $script_dir output $variant]
set vendor [file join $module_dir rtl vendor acz7015_ch62]
set ip_repo [file join $script_dir ip_repo]
file mkdir $output_dir

create_project -force $project_name $project_dir -part xc7z015clg485-2
set_property target_language Verilog [current_project]
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog

# Generate vendor IP beside the ignored project, never beside source XCI files.
foreach name {pll dc_fifo} {
    file mkdir [file join $project_dir ip $name]
    file copy -force [file join $script_dir ip $name ${name}.xci] \
        [file join $project_dir ip $name ${name}.xci]
}

foreach src [list \
    [file join $module_dir rtl capture stereo_camera_axis.v] \
    [file join $module_dir rtl capture stereo_line_controller.v] \
    [file join $module_dir rtl display axis_osd_rgb565.v] \
    [file join $module_dir rtl display axis_video_probe.v] \
    [file join $vendor cache.v] \
    [file join $vendor Camera_ETH_Formator.v] \
    [file join $vendor camera_init camera_init.v] \
    [file join $vendor camera_init ov5640_init_table_rgb.v] \
    [file join $vendor camera_init ov5640_init_table_jpeg.v] \
    [file join $vendor camera_init ov7725_init_table_rgb.v] \
    [file join $vendor camera_init i2c_control i2c_control.v] \
    [file join $vendor camera_init i2c_control i2c_bit_shift.v] \
    [file join $project_dir ip pll pll.xci] \
    [file join $project_dir ip dc_fifo dc_fifo.xci]] {
    add_files -norecurse $src
}
if {$with_pl_depth} {
    add_files -norecurse [file join $module_dir rtl depth stereo_sad.sv]
    if {$with_stream_depth} {
        foreach source {stereo_sad_stream_bd.v stereo_stream_preproc.v depth_video_overlay.v} {
            add_files -norecurse [file join $module_dir rtl depth $source]
        }
        add_files -norecurse [file join $module_dir rtl depth depth_palette.vh]
        set_property file_type {Verilog Header} [get_files depth_palette.vh]
        set_property include_dirs [file join $module_dir rtl depth] [current_fileset]
    } else {
        add_files -norecurse [file join $module_dir rtl depth stereo_sad_bd.v]
    }
}
add_files -fileset constrs_1 -norecurse [file join $script_dir constraints hdmi.xdc]
add_files -fileset constrs_1 -norecurse [file join $script_dir constraints camera_pins.xdc]
upgrade_ip [get_ips]
generate_target all [get_ips]
update_compile_order -fileset sources_1

create_bd_design system
set ps7 [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* ps7]
set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 {1} CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} \
    CONFIG.PCW_DDR_RAM_HIGHADDR {0x3FFFFFFF} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000} \
    CONFIG.PCW_I2C1_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_I2C1_I2C1_IO {EMIO}] $ps7

set vdma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_vdma:* display_vdma]
set video_frames [expr {$with_stream_depth ? 3 : 1}]
set video_genlock [expr {$with_stream_depth ? 1 : 0}]
set video_mm2s_mode [expr {$with_stream_depth ? 3 : 0}]
if {$with_ch19_display} {
    set video_genlock 1
    set video_mm2s_mode 3
}
set read_line_depth [expr {$with_ch19_display ? 1024 : 4096}]
set video_s2mm_mode [expr {$with_stream_depth ? 2 : 0}]
set_property -dict [list \
    CONFIG.c_include_sg {0} CONFIG.c_num_fstores $video_frames \
    CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {1} \
    CONFIG.c_include_mm2s_dre {0} CONFIG.c_include_s2mm_dre {0} \
    CONFIG.c_include_mm2s_sf {0} CONFIG.c_include_s2mm_sf {0} \
    CONFIG.c_include_internal_genlock $video_genlock \
    CONFIG.c_mm2s_genlock_mode $video_mm2s_mode CONFIG.c_s2mm_genlock_mode $video_s2mm_mode \
    CONFIG.c_m_axi_mm2s_data_width {64} CONFIG.c_m_axi_s2mm_data_width {64} \
    CONFIG.c_m_axis_mm2s_tdata_width {16} \
    CONFIG.c_mm2s_linebuffer_depth $read_line_depth CONFIG.c_s2mm_linebuffer_depth {4096} \
    CONFIG.c_mm2s_max_burst_length {64} CONFIG.c_s2mm_max_burst_length {64} \
    CONFIG.c_mm2s_sof_enable {1} CONFIG.c_s2mm_sof_enable {1} \
    CONFIG.c_use_mm2s_fsync {0} CONFIG.c_use_s2mm_fsync {2}] $vdma

set camera [create_bd_cell -type module -reference stereo_camera_axis camera]
set osd [create_bd_cell -type module -reference axis_osd_rgb565 osd]
set_property -dict [list CONFIG.LABEL_LATENCY {2}] $osd
set probe [create_bd_cell -type module -reference axis_video_probe probe]
set rgb565 [create_bd_cell -type ip -vlnv xilinx.com:user:rgb565to888:1.0 rgb565to888]
set vidout [create_bd_cell -type ip -vlnv xilinx.com:ip:v_axi4s_vid_out:* vidout]
set_property -dict [list CONFIG.C_HAS_ASYNC_CLK {1}] $vidout
set vtc [create_bd_cell -type ip -vlnv xilinx.com:ip:v_tc:* vtc]
set_property -dict [list CONFIG.enable_detection {false}] $vtc
set rgb2lcd [create_bd_cell -type ip -vlnv www.xilinx.com:user:rgb2lcd:1.0 rgb2lcd]
set dynclk [create_bd_cell -type ip -vlnv digilentinc.com:ip:axi_dynclk:1.0 dynclk]

set osd_cfg [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* osd_cfg]
set_property -dict [list CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_GPIO_WIDTH {32} \
    CONFIG.C_IS_DUAL {1} CONFIG.C_ALL_OUTPUTS_2 {1} CONFIG.C_GPIO2_WIDTH {32}] $osd_cfg
set probe_gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* probe_gpio]
set_property -dict [list CONFIG.C_ALL_INPUTS {1} CONFIG.C_GPIO_WIDTH {32} \
    CONFIG.C_IS_DUAL {1} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_GPIO2_WIDTH {32}] $probe_gpio
set camera_gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* camera_gpio]
set_property -dict [list CONFIG.C_ALL_INPUTS {1} CONFIG.C_GPIO_WIDTH {32} \
    CONFIG.C_IS_DUAL {1} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_GPIO2_WIDTH {32}] $camera_gpio
set button_gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* button_gpio]
set_property -dict [list CONFIG.C_ALL_INPUTS {1} CONFIG.C_GPIO_WIDTH {1}] $button_gpio
if {$with_pl_depth} {
    set depth [create_bd_cell -type module -reference [expr {$with_stream_depth ? "stereo_sad_stream_bd" : "stereo_sad_bd"}] depth_sad]
    set_property -dict [list CONFIG.LANES {8}] $depth
}
if {$with_dma_depth} {
    set depth_dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:* depth_dma]
    set_property -dict [list CONFIG.c_include_sg {0} \
        CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {1} \
        CONFIG.c_sg_length_width {16} \
        CONFIG.c_m_axis_mm2s_tdata_width {16} \
        CONFIG.c_s_axis_s2mm_tdata_width {8} \
        CONFIG.c_m_axi_mm2s_data_width {64} \
        CONFIG.c_m_axi_s2mm_data_width {64}] $depth_dma
}

if {$with_stream_depth} {
    set preproc [create_bd_cell -type module -reference stereo_stream_preproc preproc]
    set depth_view [create_bd_cell -type module -reference depth_video_overlay depth_view]
    set mode_gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* mode_gpio]
    set_property -dict [list CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_GPIO_WIDTH {1}] $mode_gpio
    set depth_stats [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:* depth_stats]
    set_property -dict [list CONFIG.C_ALL_INPUTS {1} CONFIG.C_GPIO_WIDTH {32} \
        CONFIG.C_IS_DUAL {1} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_GPIO2_WIDTH {32}] $depth_stats
}
set ctrl_ic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* ctrl_ic]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI [expr {$with_stream_depth ? 9 : ($with_dma_depth ? 8 : 7)}]] $ctrl_ic
set mem_ic [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* mem_ic]
set_property -dict [list CONFIG.NUM_SI [expr {$with_dma_depth ? 4 : 2}] CONFIG.NUM_MI {1}] $mem_ic
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* rst_100m]
set locked [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* const_locked]
set_property -dict [list CONFIG.CONST_WIDTH {1} CONFIG.CONST_VAL {1}] $locked

make_bd_intf_pins_external [get_bd_intf_pins ps7/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7/FIXED_IO]
make_bd_intf_pins_external [get_bd_intf_pins ps7/IIC_1]
make_bd_intf_pins_external [get_bd_intf_pins rgb2lcd/lcd]
set_property name DDR [get_bd_intf_ports DDR_0]
set_property name FIXED_IO [get_bd_intf_ports FIXED_IO_0]
make_bd_pins_external [get_bd_pins camera/clk_50m]
set_property name clk [get_bd_ports clk_50m_0]
foreach pin {camera1_sclk camera1_sdat camera1_vsync camera1_href camera1_pclk camera1_xclk camera1_data camera1_rst_n camera1_pwdn camera2_sclk camera2_sdat camera2_vsync camera2_href camera2_pclk camera2_xclk camera2_data camera2_rst_n camera2_pwdn} {
    make_bd_pins_external [get_bd_pins camera/$pin]
    set_property name $pin [get_bd_ports ${pin}_0]
}
make_bd_pins_external [get_bd_pins button_gpio/gpio_io_i]
set_property name mode_button [get_bd_ports gpio_io_i_0]

connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins ctrl_ic/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M00_AXI] [get_bd_intf_pins dynclk/s00_axi]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M01_AXI] [get_bd_intf_pins vtc/ctrl]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M02_AXI] [get_bd_intf_pins display_vdma/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M03_AXI] [get_bd_intf_pins probe_gpio/S_AXI]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M04_AXI] [get_bd_intf_pins osd_cfg/S_AXI]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M05_AXI] [get_bd_intf_pins camera_gpio/S_AXI]
connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M06_AXI] [get_bd_intf_pins button_gpio/S_AXI]
if {$with_dma_depth} {
    connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M07_AXI] [get_bd_intf_pins depth_dma/S_AXI_LITE]
}
if {$with_stream_depth} {
    connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M07_AXI] [get_bd_intf_pins mode_gpio/S_AXI]
    connect_bd_intf_net [get_bd_intf_pins ctrl_ic/M08_AXI] [get_bd_intf_pins depth_stats/S_AXI]
}

connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXI_MM2S] [get_bd_intf_pins mem_ic/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXI_S2MM] [get_bd_intf_pins mem_ic/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins mem_ic/M00_AXI] [get_bd_intf_pins ps7/S_AXI_HP0]
if {$with_dma_depth} {
    connect_bd_intf_net [get_bd_intf_pins depth_dma/M_AXI_MM2S] [get_bd_intf_pins mem_ic/S02_AXI]
    connect_bd_intf_net [get_bd_intf_pins depth_dma/M_AXI_S2MM] [get_bd_intf_pins mem_ic/S03_AXI]
    connect_bd_intf_net [get_bd_intf_pins depth_dma/M_AXIS_MM2S] [get_bd_intf_pins depth_sad/S_AXIS]
    connect_bd_intf_net [get_bd_intf_pins depth_sad/M_AXIS] [get_bd_intf_pins depth_dma/S_AXIS_S2MM]
}
if {$with_stream_depth} {
    connect_bd_intf_net [get_bd_intf_pins camera/M_AXIS] [get_bd_intf_pins preproc/S_AXIS]
    connect_bd_intf_net [get_bd_intf_pins preproc/M_AXIS] [get_bd_intf_pins display_vdma/S_AXIS_S2MM]
    connect_bd_intf_net [get_bd_intf_pins preproc/PAIR] [get_bd_intf_pins depth_sad/S_AXIS]
    connect_bd_intf_net [get_bd_intf_pins depth_sad/M_AXIS] [get_bd_intf_pins depth_view/DISPARITY]
    connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXIS_MM2S] [get_bd_intf_pins depth_view/S_AXIS]
    connect_bd_intf_net [get_bd_intf_pins depth_view/M_AXIS] [get_bd_intf_pins osd/S_AXIS]
    connect_bd_net [get_bd_pins mode_gpio/gpio_io_o] [get_bd_pins depth_view/mode_depth]
    connect_bd_net [get_bd_pins depth_view/completed_frames] [get_bd_pins depth_stats/gpio_io_i]
    connect_bd_net [get_bd_pins preproc/dropped_pairs] [get_bd_pins depth_stats/gpio2_io_i]
} elseif {$with_ch19_display} {
    # Keep the ch19 display path direct. OSD/probe observe the capture side.
    connect_bd_intf_net [get_bd_intf_pins camera/M_AXIS] [get_bd_intf_pins osd/S_AXIS]
    connect_bd_intf_net [get_bd_intf_pins probe/M_AXIS] [get_bd_intf_pins display_vdma/S_AXIS_S2MM]
    connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXIS_MM2S] [get_bd_intf_pins rgb565to888/S_AXIS]
} else {
    connect_bd_intf_net [get_bd_intf_pins camera/M_AXIS] [get_bd_intf_pins display_vdma/S_AXIS_S2MM]
    connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXIS_MM2S] [get_bd_intf_pins osd/S_AXIS]
}
connect_bd_intf_net [get_bd_intf_pins osd/M_AXIS] [get_bd_intf_pins probe/S_AXIS]
if {!$with_ch19_display} {
    connect_bd_intf_net [get_bd_intf_pins probe/M_AXIS] [get_bd_intf_pins rgb565to888/S_AXIS]
}
connect_bd_intf_net [get_bd_intf_pins rgb565to888/M_AXIS] [get_bd_intf_pins vidout/video_in]
connect_bd_intf_net [get_bd_intf_pins vidout/vid_io_out] [get_bd_intf_pins rgb2lcd/vid_rgb]
connect_bd_intf_net [get_bd_intf_pins vtc/vtiming_out] [get_bd_intf_pins vidout/vtiming_in]
connect_bd_net [get_bd_pins vidout/vtg_ce] [get_bd_pins vtc/gen_clken]
connect_bd_net [get_bd_pins osd_cfg/gpio_io_o] [get_bd_pins osd/cfg_resolution]
connect_bd_net [get_bd_pins osd_cfg/gpio2_io_o] [get_bd_pins osd/cfg_control]
connect_bd_net [get_bd_pins probe/last_line_pixels] [get_bd_pins probe_gpio/gpio_io_i]
connect_bd_net [get_bd_pins probe/last_frame_lines] [get_bd_pins probe_gpio/gpio2_io_i]
connect_bd_net [get_bd_pins camera/overflow_count] [get_bd_pins camera_gpio/gpio_io_i]
connect_bd_net [get_bd_pins camera/source_frame_count] [get_bd_pins camera_gpio/gpio2_io_i]

set fclk [get_bd_pins ps7/FCLK_CLK0]
foreach pin [list ps7/M_AXI_GP0_ACLK ps7/S_AXI_HP0_ACLK \
    display_vdma/s_axi_lite_aclk display_vdma/m_axi_mm2s_aclk display_vdma/m_axis_mm2s_aclk \
    display_vdma/m_axi_s2mm_aclk display_vdma/s_axis_s2mm_aclk camera/axis_clk \
    osd/aclk probe/aclk rgb565to888/m_clk rgb565to888/s_clk vidout/aclk vtc/s_axi_aclk \
    dynclk/REF_CLK_I dynclk/s00_axi_aclk osd_cfg/s_axi_aclk probe_gpio/s_axi_aclk camera_gpio/s_axi_aclk button_gpio/s_axi_aclk \
    ctrl_ic/ACLK ctrl_ic/S00_ACLK ctrl_ic/M00_ACLK ctrl_ic/M01_ACLK ctrl_ic/M02_ACLK \
    ctrl_ic/M03_ACLK ctrl_ic/M04_ACLK ctrl_ic/M05_ACLK ctrl_ic/M06_ACLK \
    mem_ic/ACLK mem_ic/S00_ACLK mem_ic/S01_ACLK mem_ic/M00_ACLK \
    rst_100m/slowest_sync_clk] {
    connect_bd_net $fclk [get_bd_pins $pin]
}
if {$with_dma_depth} {
    foreach pin {depth_sad/clk depth_dma/s_axi_lite_aclk depth_dma/m_axi_mm2s_aclk depth_dma/m_axi_s2mm_aclk ctrl_ic/M07_ACLK mem_ic/S02_ACLK mem_ic/S03_ACLK} {
        connect_bd_net $fclk [get_bd_pins $pin]
    }
}
if {$with_stream_depth} {
    foreach pin {depth_sad/clk preproc/clk depth_view/clk mode_gpio/s_axi_aclk depth_stats/s_axi_aclk ctrl_ic/M07_ACLK ctrl_ic/M08_ACLK} {
        connect_bd_net $fclk [get_bd_pins $pin]
    }
}
set pclk [get_bd_pins dynclk/PXL_CLK_O]
connect_bd_net $pclk [get_bd_pins vidout/vid_io_out_clk]
connect_bd_net $pclk [get_bd_pins vtc/clk]
connect_bd_net $pclk [get_bd_pins rgb2lcd/pixel_clk]
connect_bd_net [get_bd_pins dynclk/LOCKED_O] [get_bd_pins rgb2lcd/vid_rst]

connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins rst_100m/ext_reset_in]
connect_bd_net [get_bd_pins const_locked/dout] [get_bd_pins rst_100m/dcm_locked]
set aresetn [get_bd_pins rst_100m/peripheral_aresetn]
foreach pin [list display_vdma/axi_resetn camera/axis_resetn osd/aresetn probe/aresetn \
    dynclk/s00_axi_aresetn vtc/s_axi_aresetn osd_cfg/s_axi_aresetn probe_gpio/s_axi_aresetn camera_gpio/s_axi_aresetn button_gpio/s_axi_aresetn \
    ctrl_ic/ARESETN ctrl_ic/S00_ARESETN ctrl_ic/M00_ARESETN ctrl_ic/M01_ARESETN \
    ctrl_ic/M02_ARESETN ctrl_ic/M03_ARESETN ctrl_ic/M04_ARESETN ctrl_ic/M05_ARESETN ctrl_ic/M06_ARESETN \
    mem_ic/ARESETN mem_ic/S00_ARESETN mem_ic/S01_ARESETN mem_ic/M00_ARESETN] {
    connect_bd_net $aresetn [get_bd_pins $pin]
}
if {$with_dma_depth} {
    foreach pin {depth_sad/resetn depth_dma/axi_resetn ctrl_ic/M07_ARESETN mem_ic/S02_ARESETN mem_ic/S03_ARESETN} {
        connect_bd_net $aresetn [get_bd_pins $pin]
    }
}
if {$with_stream_depth} {
    foreach pin {depth_sad/resetn preproc/resetn depth_view/resetn mode_gpio/s_axi_aresetn depth_stats/s_axi_aresetn ctrl_ic/M07_ARESETN ctrl_ic/M08_ARESETN} {
        connect_bd_net $aresetn [get_bd_pins $pin]
    }
}

assign_bd_address
set_property offset 0x43C00000 [get_bd_addr_segs ps7/Data/SEG_dynclk_reg0]
set_property offset 0x43C10000 [get_bd_addr_segs ps7/Data/SEG_vtc_Reg]
set_property offset 0x43000000 [get_bd_addr_segs ps7/Data/SEG_display_vdma_Reg]
assign_bd_address -offset 0x41200000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs camera_gpio/S_AXI/Reg] -force
assign_bd_address -offset 0x41210000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs osd_cfg/S_AXI/Reg] -force
assign_bd_address -offset 0x41220000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs probe_gpio/S_AXI/Reg] -force
assign_bd_address -offset 0x41230000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs button_gpio/S_AXI/Reg] -force
if {$with_dma_depth} {
    assign_bd_address -offset 0x40400000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs depth_dma/S_AXI_LITE/Reg] -force
}
if {$with_stream_depth} {
    assign_bd_address -offset 0x41240000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs mode_gpio/S_AXI/Reg] -force
    assign_bd_address -offset 0x41250000 -range 0x00010000 -target_address_space [get_bd_addr_spaces ps7/Data] [get_bd_addr_segs depth_stats/S_AXI/Reg] -force
}
validate_bd_design
save_bd_design

set bd_file [get_files system.bd]
generate_target all $bd_file
make_wrapper -files $bd_file -top
add_files -norecurse [file join $project_dir ${project_name}.gen sources_1 bd system hdl system_wrapper.v]
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
write_bd_tcl -force [file join $output_dir system_bd.tcl]

if {[llength $argv] > 0 && [lindex $argv 0] eq "build"} {
    launch_runs impl_1 -to_step write_bitstream -jobs 1
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
        error "Implementation failed: [get_property STATUS [get_runs impl_1]]"
    }
    set bit_name $project_name
    file copy -force [file join $project_dir ${project_name}.runs impl_1 system_wrapper.bit] \
        [file join $output_dir ${bit_name}.bit]
    set hwh [file join $project_dir ${project_name}.gen sources_1 bd system hw_handoff system.hwh]
    file copy -force $hwh [file join $output_dir ${bit_name}.hwh]
    open_run impl_1
    report_timing_summary -file [file join $output_dir timing_summary.rpt]
    report_utilization -file [file join $output_dir utilization.rpt]
}
puts "PROJECT_OK"
exit
