`timescale 1ns / 1ps

module tb_depth_video_overlay;
    reg clk = 0;
    always #5 clk = !clk;
    reg resetn = 0, mode_depth = 1;
    reg [15:0] s_axis_tdata = 16'h1234;
    reg s_axis_tvalid = 0, s_axis_tuser = 0, s_axis_tlast = 0;
    wire s_axis_tready;
    wire [15:0] m_axis_tdata;
    wire m_axis_tvalid, m_axis_tuser, m_axis_tlast;
    reg [7:0] disparity_tdata = 20;
    reg disparity_tvalid = 0, disparity_tuser = 0, disparity_tlast = 0;
    wire disparity_tready;
    wire [31:0] completed_frames;
    integer i, shown = 0;
    depth_video_overlay dut (
        .clk(clk), .resetn(resetn), .mode_depth(mode_depth),
        .s_axis_tdata(s_axis_tdata), .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready), .s_axis_tuser(s_axis_tuser),
        .s_axis_tlast(s_axis_tlast),
        .m_axis_tdata(m_axis_tdata), .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(1'b1), .m_axis_tuser(m_axis_tuser),
        .m_axis_tlast(m_axis_tlast),
        .disparity_tdata(disparity_tdata), .disparity_tvalid(disparity_tvalid),
        .disparity_tready(disparity_tready), .disparity_tuser(disparity_tuser),
        .disparity_tlast(disparity_tlast), .completed_frames(completed_frames)
    );
    always @(posedge clk) if (resetn && m_axis_tvalid) begin
        if (m_axis_tdata !== 16'hd180)
            $fatal(1, "depth color %h expected d180", m_axis_tdata);
        if (m_axis_tuser !== (shown == 0))
            $fatal(1, "wrong display SOF");
        shown = shown + 1;
    end
    initial begin
        repeat (5) @(negedge clk);
        resetn = 1;
        for (i = 0; i < 28800; i = i + 1) begin
            @(negedge clk);
            disparity_tvalid = 1;
            disparity_tuser = i == 0;
            disparity_tlast = i == 28799;
        end
        @(negedge clk);
        disparity_tvalid = 0;
        if (completed_frames[31:20] != 1 || completed_frames[19:0] != 28800)
            $fatal(1, "frame/pixel counts %h", completed_frames);
        for (i = 0; i < 10; i = i + 1) begin
            @(negedge clk);
            s_axis_tvalid = 1;
            s_axis_tuser = i == 0;
        end
        @(negedge clk);
        s_axis_tvalid = 0;
        repeat (4) @(negedge clk);
        if (shown != 10) $fatal(1, "shown %d", shown);
        // Drop a severely short camera frame without publishing its torn map.
        for (i = 0; i < 1000; i = i + 1) begin
            @(negedge clk);
            disparity_tvalid = 1;
            disparity_tuser = i == 0;
            disparity_tlast = 0;
        end
        @(negedge clk);
        disparity_tuser = 1;
        @(negedge clk);
        disparity_tvalid = 0;
        if (completed_frames[31:20] != 1 || dut.bank1_valid != 0)
            $fatal(1, "short frame published: count=%h valid=%d",
                   completed_frames, dut.bank1_valid);
        // A nearly complete frame can be displayed with its missing tail black.
        for (i = 0; i < 27000; i = i + 1) begin
            @(negedge clk);
            disparity_tvalid = 1;
            disparity_tuser = i == 0;
        end
        @(negedge clk);
        disparity_tuser = 1;
        @(negedge clk);
        disparity_tvalid = 0;
        if (completed_frames[31:20] != 2 || dut.bank1_valid != 27000)
            $fatal(1, "usable frame lost: count=%h valid=%d",
                   completed_frames, dut.bank1_valid);
        $display("PASS: full/short/usable partial frames, bank switch, palette");
        $finish;
    end
endmodule
