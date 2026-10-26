set here [file normalize [file dirname [info script]]]
set root [file normalize [file join $here .. .. ..]]
open_project [file join $root output hls_geometry project]
set_top marker_geometry
add_files [file join $here marker_geometry.cpp] -cflags "-std=c++17"
add_files -tb [file join $here test_geometry.cpp] -cflags "-std=c++17"
open_solution solution1 -flow_target vivado
set_part xc7z015clg485-2
create_clock -period 10 -name default
csim_design -argv [list [file join $root output hls_geometry fixtures.txt]]
set implementation [file join $root output hls_geometry project solution1 impl]
if {[file exists $implementation]} {file rename $implementation ${implementation}_cache_[clock seconds]}
csynth_design
export_design -format ip_catalog -rtl verilog -output [file join $root output hls_geometry marker_geometry.zip]
exit
