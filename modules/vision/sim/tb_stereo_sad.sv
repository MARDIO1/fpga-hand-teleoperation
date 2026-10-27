`timescale 1ns / 1ps

module tb_stereo_sad #(
    parameter integer L = 4
);
    localparam integer W = 80, H = 12, D = 48, SHIFT = 7;
    reg clk = 0;
    always #5 clk = ~clk;
    reg resetn = 0;
    reg [15:0] s_tdata = 0;
    reg s_tvalid = 0, s_tuser = 0;
    wire s_tready;
    wire [7:0] m_tdata;
    wire m_tvalid, m_tuser, m_tlast;
    integer x, y, frame, checked = 0;

    stereo_sad #(.WIDTH(W), .HEIGHT(H), .DISPARITIES(D),
                 .LANES(L), .MIN_VALID_DISPARITY(0)) dut (
        .clk(clk), .resetn(resetn), .s_tdata(s_tdata),
        .s_tvalid(s_tvalid), .s_tready(s_tready), .s_tuser(s_tuser),
        .m_tdata(m_tdata), .m_tvalid(m_tvalid), .m_tready(1'b1),
        .m_tuser(m_tuser), .m_tlast(m_tlast)
    );

    function automatic [7:0] pattern(input integer px, input integer py);
        pattern = ((px * 73) ^ (py * 29) ^ (px * py * 11)) & 255;
    endfunction

    initial begin
        repeat (4) @(negedge clk);
        resetn = 1;
        for (frame = 0; frame < 2; frame = frame + 1) begin
        for (y = 0; y < H; y = y + 1) begin
            for (x = 0; x < W; x = x + 1) begin
                @(negedge clk);
                while (!s_tready) @(negedge clk);
                s_tdata = {pattern(x, y), pattern(x + SHIFT, y)};
                // AXI DMA MM2S does not send video SOF/TUSER. The core must
                // wrap its internal coordinates after the final pixel.
                s_tuser = 0;
                s_tvalid = 1;
                @(negedge clk);
                s_tvalid = 0;
                s_tuser = 0;
                while (!m_tvalid) @(negedge clk);
                if (m_tuser !== (x == 0 && y == 0))
                    $fatal(1, "bad tuser at %0d,%0d", x, y);
                if (m_tlast !== (x == W-1 && y == H-1))
                    $fatal(1, "bad tlast at %0d,%0d", x, y);
                if (x >= D+3 && y >= 4) begin
                    if (m_tdata !== SHIFT)
                        $fatal(1, "wrong disparity at %0d,%0d: got %0d expected %0d",
                               x, y, m_tdata, SHIFT);
                    checked = checked + 1;
                end else if (m_tdata !== 0) begin
                    $fatal(1, "nonzero border at %0d,%0d", x, y);
                end
            end
        end
        end
        $display("PASS: %0d interior pixels matched disparity %0d", checked, SHIFT);
        $finish;
    end
    initial begin
        #1000000;
        $fatal(1, "timeout");
    end
endmodule

module tb_sad_4;
    tb_stereo_sad #(.L(4)) test();
endmodule

module tb_sad_8;
    tb_stereo_sad #(.L(8)) test();
endmodule

module tb_sad_16;
    tb_stereo_sad #(.L(16)) test();
endmodule
