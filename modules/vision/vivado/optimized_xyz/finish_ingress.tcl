launch_runs impl_1 -to_step write_bitstream -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Compact implementation failed"}
open_run impl_1
report_utilization -file [file join $output_dir utilization.rpt]
report_timing_summary -file [file join $output_dir timing_summary.rpt]
set lut [llength [get_cells -hier -filter {REF_NAME =~ LUT*}]]
set ff [llength [get_cells -hier -filter {REF_NAME =~ FD*}]]
set dsp [llength [get_cells -hier -filter {REF_NAME =~ DSP48*}]]
set bram [expr {[llength [get_cells -hier -filter {REF_NAME =~ RAMB36*}]]+0.5*[llength [get_cells -hier -filter {REF_NAME =~ RAMB18*}]]}]
set utilization [report_utilization -return_string]
if {![regexp {\| Slice LUTs[^|]*\|\s*([0-9]+)} $utilization _ actual_lut]} {error "Cannot read implemented LUT use"}
set lut $actual_lut
set usage [list LUT $lut FF $ff DSP $dsp BRAM36 $bram]
puts "COMPACT_USAGE $usage"
set f [open [file join $output_dir resource_gate.txt] w];puts $f $usage;close $f
if {$lut>27720 || $ff>55440 || $dsp>96 || $bram>57} {error "Resource use exceeds 60 percent; refusing release"}
if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]<0} {error "Setup timing failed; refusing release"}
if {[get_property SLACK [get_timing_paths -delay_type min -max_paths 1]]<0} {error "Hold timing failed; refusing release"}
file copy -force [file join $project_dir vxyz.runs impl_1 system_wrapper.bit] [file join $output_dir pl_stereo_compact_optimized.bit]
file copy -force [file join $project_dir vxyz.gen sources_1 bd system hw_handoff system.hwh] [file join $output_dir pl_stereo_compact_optimized.hwh]
puts OPTIMIZED_BUILD_PASS
exit
