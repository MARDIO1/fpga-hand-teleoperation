set here [file normalize [file dirname [info script]]]
set root [file normalize [file join $here .. .. ..]]
open_project [file join $root output hls_geometry project]
open_solution solution1
csim_design -argv [list [file join $root output hls_geometry fixtures.txt]]
set implementation [file join $root output hls_geometry project solution1 impl]
if {[file exists $implementation]} {file rename $implementation ${implementation}_cache_[clock seconds]}
csynth_design
export_design -format ip_catalog -rtl verilog -output [file join $root output hls_geometry marker_geometry.zip]
exit
