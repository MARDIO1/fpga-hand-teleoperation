`timescale 1ns / 1ps

module xpm_fifo_sync #(
    parameter FIFO_MEMORY_TYPE = "block", FIFO_WRITE_DEPTH = 512,
    parameter WRITE_DATA_WIDTH = 17, READ_DATA_WIDTH = 17,
    parameter READ_MODE = "fwft", FIFO_READ_LATENCY = 0,
    parameter FULL_RESET_VALUE = 0, USE_ADV_FEATURES = "0000",
    parameter DOUT_RESET_VALUE = "0", WAKEUP_TIME = 0
) (
    input rst, wr_clk, wr_en, rd_en, sleep, injectsbiterr, injectdbiterr,
    input [WRITE_DATA_WIDTH-1:0] din,
    output wire [READ_DATA_WIDTH-1:0] dout,
    output wire full, empty
);
    reg [READ_DATA_WIDTH-1:0] data [0:FIFO_WRITE_DEPTH-1];
    integer wr = 0, rd = 0, count = 0;
    assign dout = data[rd];
    assign full = count == FIFO_WRITE_DEPTH;
    assign empty = count == 0;
    always @(posedge wr_clk) begin
        if (rst) begin
            wr <= 0;
            rd <= 0;
            count <= 0;
        end else begin
            if (wr_en && !full) begin
                data[wr] <= din;
                wr <= (wr + 1) % FIFO_WRITE_DEPTH;
            end
            if (rd_en && !empty)
                rd <= (rd + 1) % FIFO_WRITE_DEPTH;
            case ({wr_en && !full, rd_en && !empty})
                2'b10: count <= count + 1;
                2'b01: count <= count - 1;
            endcase
        end
    end
endmodule

module tb_stream_preproc;
    reg clk = 0;
    always #5 clk = !clk;
    reg resetn = 0;
    reg [15:0] s_axis_tdata = 0;
    reg s_axis_tvalid = 0, s_axis_tuser = 0, s_axis_tlast = 0;
    wire s_axis_tready;
    wire [15:0] m_axis_tdata, pair_tdata;
    wire m_axis_tvalid, m_axis_tuser, m_axis_tlast;
    wire pair_tvalid, pair_tuser;
    wire [31:0] dropped_pairs;
    integer pairs = 0;
    integer x, y;
    stereo_stream_preproc dut (
        .clk(clk), .resetn(resetn),
        .s_axis_tdata(s_axis_tdata), .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready), .s_axis_tuser(s_axis_tuser),
        .s_axis_tlast(s_axis_tlast),
        .m_axis_tdata(m_axis_tdata), .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(1'b1), .m_axis_tuser(m_axis_tuser),
        .m_axis_tlast(m_axis_tlast),
        .pair_tdata(pair_tdata), .pair_tvalid(pair_tvalid),
        .pair_tready(1'b1), .pair_tuser(pair_tuser),
        .dropped_pairs(dropped_pairs)
    );
    always @(posedge clk) if (resetn && pair_tvalid) begin
        if (pair_tuser !== (pairs == 0)) $fatal(1, "wrong SOF at pair %0d", pairs);
        if (pairs == 482 && pair_tdata !== {8'd29, 8'd77})
            $fatal(1, "mean-gray sample %h, expected 1d4d", pair_tdata);
        if (pairs == 600 && pair_tdata !== {8'd149, 8'd255})
            $fatal(1, "far-column sample %h, expected 95ff", pair_tdata);
        pairs = pairs + 1;
    end
    initial begin
        repeat (5) @(negedge clk);
        resetn = 1;
        for (y = 0; y < 16; y = y + 1)
            for (x = 0; x < 1280; x = x + 1) begin
                @(negedge clk);
                s_axis_tvalid = 1;
                s_axis_tdata = x < 320 ? 16'hf800 :
                               x < 640 ? 16'hffff :
                               x < 1024 ? 16'h001f : 16'h07e0;
                s_axis_tuser = x == 0 && y == 0;
                s_axis_tlast = x == 1279;
                if (!s_axis_tready) $fatal(1, "video stalled");
            end
        @(negedge clk);
        s_axis_tvalid = 0;
        repeat (1000) @(negedge clk);
        if (pairs != 640 || dropped_pairs[23:0] != 640 || dropped_pairs[31:24] != 0)
            $fatal(1, "pairs=%0d dropped=%0d", pairs, dropped_pairs);
        $display("PASS: %0d pairs, gray+3x3 mean, no drops", pairs);
        $finish;
    end
endmodule
