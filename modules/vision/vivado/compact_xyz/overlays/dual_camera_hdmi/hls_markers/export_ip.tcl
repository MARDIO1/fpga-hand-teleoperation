set here [file normalize [file dirname [info script]]]
set root [file normalize [file join $here .. .. ..]]
open_project [file join $root output hls_markers project]
open_solution solution1
export_design -format ip_catalog -rtl verilog -output [file join $root output hls_markers glove_markers.zip]
exit
