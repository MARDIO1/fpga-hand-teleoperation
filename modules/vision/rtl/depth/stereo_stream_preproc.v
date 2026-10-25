`timescale 1ns / 1ps

// Pass the 1280x720 camera stream to DDR while extracting one 160x180
// grayscale pair per four source pixels/lines. The right image is delayed
// one sampled row, matching the existing approximately 4-pixel alignment.
module stereo_stream_preproc (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK",
       X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF S_AXIS:M_AXIS:PAIR, ASSOCIATED_RESET resetn" *)
    input wire clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST",
       X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input wire resetn,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TDATA" *)
    input wire [15:0] s_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TVALID" *)
    input wire s_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TREADY" *)
    output wire s_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TUSER" *)
    input wire s_axis_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TLAST" *)
    input wire s_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TDATA" *)
    output wire [15:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TVALID" *)
    output wire m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *)
    input wire m_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TUSER" *)
    output wire m_axis_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *)
    output wire m_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 PAIR TDATA" *)
    output wire [15:0] pair_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 PAIR TVALID" *)
    output wire pair_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 PAIR TREADY" *)
    input wire pair_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 PAIR TUSER" *)
    output wire pair_tuser,
    output wire [31:0] dropped_pairs
);
    assign m_axis_tdata = s_axis_tdata;
    assign m_axis_tvalid = s_axis_tvalid;
    assign s_axis_tready = m_axis_tready;
    assign m_axis_tuser = s_axis_tuser;
    assign m_axis_tlast = s_axis_tlast;

    function automatic [7:0] gray565(input [15:0] rgb);
        reg [7:0] red, green, blue;
        reg [15:0] weighted;
        begin
            red = {rgb[15:11], rgb[15:13]};
            green = {rgb[10:5], rgb[10:9]};
            blue = {rgb[4:0], rgb[4:2]};
            weighted = 77*red + 150*green + 29*blue + 128;
            gray565 = weighted[15:8];
        end
    endfunction

    reg [10:0] x;
    reg [9:0] y;
    wire [10:0] px = s_axis_tuser ? 11'd0 : x;
    wire [9:0] py = s_axis_tuser ? 10'd0 : y;
    wire accepted = s_axis_tvalid && s_axis_tready;
    wire sampled = accepted && py[1:0] == 0 && px[1:0] == 0;
    wire [7:0] gray = gray565(s_axis_tdata);
    wire [8:0] sampled_column = px[10:2];
    wire [7:0] sample_x = px >= 640 ? sampled_column - 9'd160 : sampled_column[7:0];

    (* ram_style = "block" *) reg [7:0] right_even [0:159];
    (* ram_style = "block" *) reg [7:0] right_odd [0:159];
    wire [7:0] older_right = py[2] ? right_even[sample_x] : right_odd[sample_x];
    reg [7:0] pair_left_q, pair_right_q, pair_x_q;
    reg [9:0] pair_y_q;
    reg pair_input_valid;
    wire [15:0] current_pair = {pair_left_q, pair_right_q};
    (* ram_style = "distributed" *) reg [15:0] row1 [0:159];
    (* ram_style = "distributed" *) reg [15:0] row2 [0:159];
    reg [15:0] cur1, cur2, prev1, prev2, old1, old2;
    wire [15:0] previous_pair = pair_y_q < 4 ? 16'd0 : row1[pair_x_q];
    wire [15:0] oldest_pair = pair_y_q < 8 ? 16'd0 : row2[pair_x_q];
    wire [15:0] a1 = pair_x_q == 0 ? 16'd0 : cur1;
    wire [15:0] a2 = pair_x_q < 2 ? 16'd0 : cur2;
    wire [15:0] b1 = pair_x_q == 0 ? 16'd0 : prev1;
    wire [15:0] b2 = pair_x_q < 2 ? 16'd0 : prev2;
    wire [15:0] c1 = pair_x_q == 0 ? 16'd0 : old1;
    wire [15:0] c2 = pair_x_q < 2 ? 16'd0 : old2;

    reg [11:0] left_sum, right_sum;
    wire [7:0] left_mean = left_sum / 12'd9;
    wire [7:0] right_mean = right_sum / 12'd9;
    reg pending, pending_sof;
    reg [16:0] fifo_input;
    reg fifo_write;
    wire [16:0] fifo_output;
    wire fifo_full, fifo_empty;
    reg [23:0] sent_pairs;
    reg [7:0] lost_pairs;
    assign dropped_pairs = {lost_pairs, sent_pairs};
    xpm_fifo_sync #(
        .FIFO_MEMORY_TYPE("block"), .FIFO_WRITE_DEPTH(512),
        .WRITE_DATA_WIDTH(17), .READ_DATA_WIDTH(17),
        .READ_MODE("fwft"), .FIFO_READ_LATENCY(0),
        .FULL_RESET_VALUE(0), .USE_ADV_FEATURES("0000"),
        .DOUT_RESET_VALUE("0"), .WAKEUP_TIME(0)
    ) pair_fifo (
        .rst(!resetn), .wr_clk(clk), .din(fifo_input),
        .wr_en(fifo_write && !fifo_full), .full(fifo_full),
        .dout(fifo_output), .rd_en(pair_tready && !fifo_empty),
        .empty(fifo_empty), .sleep(1'b0),
        .injectsbiterr(1'b0), .injectdbiterr(1'b0)
    );
    assign pair_tvalid = !fifo_empty;
    assign pair_tdata = fifo_output[15:0];
    assign pair_tuser = fifo_output[16];

    always @(posedge clk) begin
        if (!resetn) begin
            x <= 0;
            y <= 0;
            cur1 <= 0;
            cur2 <= 0;
            prev1 <= 0;
            prev2 <= 0;
            old1 <= 0;
            old2 <= 0;
            left_sum <= 0;
            right_sum <= 0;
            pending <= 0;
            pending_sof <= 0;
            fifo_input <= 0;
            fifo_write <= 0;
            sent_pairs <= 0;
            lost_pairs <= 0;
            pair_left_q <= 0;
            pair_right_q <= 0;
            pair_x_q <= 0;
            pair_y_q <= 0;
            pair_input_valid <= 0;
        end else begin
            fifo_write <= pending;
            pending <= 0;
            pair_input_valid <= 0;
            if (pending) begin
                fifo_input <= {pending_sof, left_mean, right_mean};
            end
            if (pair_tvalid && pair_tready)
                sent_pairs <= sent_pairs + 1'b1;
            if (fifo_write && fifo_full)
                lost_pairs <= lost_pairs + 1'b1;
            if (accepted) begin
                if (s_axis_tlast) begin
                    x <= 0;
                    // Recover a frame boundary after 720 lines if the
                    // camera FIFO loses its SOF marker during a short frame.
                    y <= py == 10'd719 ? 10'd0 : py + 1'b1;
                end else begin
                    x <= px + 1'b1;
                    y <= py;
                end
                if (sampled && px < 640) begin
                    if (py[2]) right_odd[sample_x] <= gray;
                    else right_even[sample_x] <= gray;
                end
                if (sampled && px >= 640) begin
                    pair_left_q <= gray;
                    pair_right_q <= py == 0 ? 8'd0 : older_right;
                    pair_x_q <= sample_x;
                    pair_y_q <= py;
                    pair_input_valid <= 1;
                end
            end
            if (pair_input_valid) begin
                    row2[pair_x_q] <= previous_pair;
                    row1[pair_x_q] <= current_pair;
                    cur2 <= a1;
                    cur1 <= current_pair;
                    prev2 <= b1;
                    prev1 <= previous_pair;
                    old2 <= c1;
                    old1 <= oldest_pair;
                    left_sum <= current_pair[15:8] + a1[15:8] + a2[15:8]
                              + previous_pair[15:8] + b1[15:8] + b2[15:8]
                              + oldest_pair[15:8] + c1[15:8] + c2[15:8];
                    right_sum <= current_pair[7:0] + a1[7:0] + a2[7:0]
                               + previous_pair[7:0] + b1[7:0] + b2[7:0]
                               + oldest_pair[7:0] + c1[7:0] + c2[7:0];
                    pending <= 1;
                    pending_sof <= pair_y_q == 0 && pair_x_q == 0;
            end
        end
    end
endmodule
