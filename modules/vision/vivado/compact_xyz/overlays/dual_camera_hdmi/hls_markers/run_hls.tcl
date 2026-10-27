set here [file normalize [file dirname [info script]]]
set root [file normalize [file join $here .. .. ..]]
set project [file join $root output hls_markers project]
set fixtures [file join $root output hls_markers fixtures]
set stage [expr {[info exists ::env(GLOVE_HLS_STAGE)] ? $::env(GLOVE_HLS_STAGE) : "csim"}]
if {$stage ni {csim synth cosim}} { error "GLOVE_HLS_STAGE must be csim, synth, or cosim" }
open_project $project
set_top glove_markers
add_files [file join $here glove_markers.cpp] -cflags "-std=c++17"
add_files -tb [file join $here test_glove_markers.cpp] -cflags "-std=c++17"
open_solution solution1 -flow_target vivado
set_part xc7z015clg485-2
create_clock -period 10 -name default
if {$stage eq "csim"} {
    csim_design -argv [list [file join $fixtures manifest.txt]]
} elseif {$stage eq "synth"} {
    csynth_design
} else {
    if {![file exists [file join $project solution1 syn report glove_markers_csynth.rpt]]} {
        error "Run GLOVE_HLS_STAGE=synth before cosim"
    }
    cosim_design -rtl verilog -argv [list [file join $fixtures smoke.txt]]
}
exit
