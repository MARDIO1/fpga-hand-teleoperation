`timescale 1ns / 1ps
module tb_hdmi_timing_monitor;
    reg clk = 0;
    always #5 clk = !clk;
    reg resetn = 0, de = 0, hs = 0, vs = 0;
    reg [15:0] rgb = 0;
    wire [31:0] line_geometry, frame_geometry, border_positions, active_start;
    integer f, y, x;
    hdmi_timing_monitor dut (
        .pixel_clk(clk), .resetn(resetn), .de(de), .hs(hs), .vs(vs), .rgb(rgb),
        .line_geometry(line_geometry), .frame_geometry(frame_geometry),
        .border_positions(border_positions), .active_start(active_start)
    );
    initial begin
        repeat (4) @(negedge clk);
        resetn = 1;
        for (f = 0; f < 4; f = f + 1)
            for (y = 0; y < 10; y = y + 1)
                for (x = 0; x < 21; x = x + 1) begin
                    @(negedge clk);
                    hs = x < 2;
                    vs = y < 1;
                    de = x >= 5 && x < 17 && y >= 3 && y < 8;
                    rgb = x < 7 ? 16'hf800 : x >= 15 ? 16'hffe0 : 16'h07e0;
                end
        @(negedge clk);
        if (line_geometry !== {16'd21, 16'd12} ||
            frame_geometry !== {16'd10, 16'd5} ||
            border_positions !== {16'd10, 16'd0} ||
            active_start !== {16'd3, 16'd5})
            $fatal(1, "monitor mismatch: line=%h frame=%h borders=%h start=%h",
                   line_geometry, frame_geometry, border_positions, active_start);
        $display("PASS native geometry, sync offsets and color border coordinates");
        $finish;
    end
endmodule
