`timescale 1ns / 1ps

// Observe the board-vendor RGB565 output without changing data or sync timing.
module hdmi_timing_monitor (
    input wire pixel_clk,
    input wire resetn,
    input wire de,
    input wire hs,
    input wire vs,
    input wire [15:0] rgb,
    output reg [31:0] line_geometry,
    output reg [31:0] frame_geometry,
    output reg [31:0] border_positions,
    output reg [31:0] active_start
);
    reg de_q, hs_q, vs_q;
    reg [15:0] hcount, line_count, active_lines, pixels;
    reg [15:0] red_x, yellow_x;
    reg red_seen, yellow_seen, first_line;
    wire [15:0] x = de_q ? pixels : 16'd0;

    always @(posedge pixel_clk) begin
        if (!resetn) begin
            de_q <= 0; hs_q <= 0; vs_q <= 0;
            hcount <= 0; line_count <= 0; active_lines <= 0;
            pixels <= 0; red_x <= 16'hffff; yellow_x <= 16'hffff;
            red_seen <= 0; yellow_seen <= 0; first_line <= 1;
            line_geometry <= 0; frame_geometry <= 0;
            border_positions <= 32'hffffffff; active_start <= 0;
        end else begin
            de_q <= de; hs_q <= hs; vs_q <= vs;
            hcount <= hcount + 1'b1;
            if (hs && !hs_q) begin
                line_geometry[31:16] <= hcount + 1'b1;
                hcount <= 0;
                line_count <= line_count + 1'b1;
            end
            if (vs && !vs_q) begin
                frame_geometry <= {line_count + (hs && !hs_q ? 16'd1 : 16'd0), active_lines};
                line_count <= 0;
                active_lines <= 0;
                first_line <= 1;
            end
            if (de) begin
                pixels <= x + 1'b1;
                if (!de_q) begin
                    active_lines <= active_lines + 1'b1;
                    active_start[15:0] <= hcount + 1'b1;
                    if (first_line) begin
                        active_start[31:16] <= line_count;
                        first_line <= 0;
                    end
                    red_seen <= 0; yellow_seen <= 0;
                    red_x <= 16'hffff; yellow_x <= 16'hffff;
                end
                if (rgb == 16'hf800 && (!de_q || !red_seen)) begin
                    red_x <= x;
                    red_seen <= 1;
                end
                if (rgb == 16'hffe0 && (!de_q || !yellow_seen)) begin
                    yellow_x <= x;
                    yellow_seen <= 1;
                end
            end else if (de_q) begin
                line_geometry[15:0] <= pixels;
                border_positions <= {yellow_x, red_x};
                pixels <= 0;
            end
        end
    end
endmodule
