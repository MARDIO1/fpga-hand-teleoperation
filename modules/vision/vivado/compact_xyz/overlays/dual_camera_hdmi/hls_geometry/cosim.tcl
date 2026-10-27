set here [file normalize [file dirname [info script]]]
set root [file normalize [file join $here .. .. ..]]
open_project [file join $root output hls_geometry project]
open_solution solution1
cosim_design -rtl verilog -argv [list [file join $root output hls_geometry smoke.txt]]
exit
