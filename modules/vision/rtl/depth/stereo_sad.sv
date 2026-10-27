`timescale 1ns / 1ps

// Streaming stereo SAD prototype. Each accepted input contains one aligned
// left/right 8-bit grayscale pixel pair at the reduced image resolution.
// Searches disparities 0..DISPARITIES-1 with a 5x5 window. Output disparity
// is zero for borders and for matches at/below MIN_VALID_DISPARITY.
module stereo_sad #(
    parameter integer WIDTH = 160,
    parameter integer HEIGHT = 180,
    parameter integer DISPARITIES = 48,
    parameter integer LANES = 8,
    parameter integer MIN_VALID_DISPARITY = 3
) (
    input  wire        clk,
    input  wire        resetn,
    input  wire [15:0] s_tdata, // {left_gray, right_gray}
    input  wire        s_tvalid,
    output wire        s_tready,
    input  wire        s_tuser, // start of frame
    output reg  [7:0]  m_tdata,
    output reg         m_tvalid,
    input  wire        m_tready,
    output reg         m_tuser,
    output reg         m_tlast
);
    localparam integer WINDOW = DISPARITIES + 4;
    localparam integer GROUPS = DISPARITIES / LANES;
    localparam [2:0] IDLE = 0, LOAD = 1, ROWS = 2, COSTS = 3,
                     REDUCE = 4, COMMIT = 5, OUTPUT = 6;
    reg [2:0] state;
    // Four older rows packed at each x. A synchronous read followed by a
    // write in LOAD lets Vivado infer one block RAM per camera.
    (* ram_style = "block" *) reg [31:0] left_lines [0:WIDTH-1];
    (* ram_style = "block" *) reg [31:0] right_lines [0:WIDTH-1];
    reg [31:0] left_taps, right_taps;
    reg [7:0] left_window [0:4][0:4];
    reg [7:0] right_history [0:4][0:WINDOW-1];
    reg [7:0] right_work [0:4][0:WINDOW-1];
    reg [7:0] input_left, input_right;
    reg [15:0] x, y, input_x, input_y;
    reg [7:0] group;
    reg [12:0] best_cost;
    reg [7:0] best_disparity;
    wire [15:0] write_x = s_tuser ? 16'd0 : x;
    wire [15:0] write_y = s_tuser ? 16'd0 : y;
    wire [10:0] row_sum [0:LANES-1][0:4];
    reg [10:0] row_sum_q [0:LANES-1][0:4];
    reg [12:0] lane_cost_q [0:LANES-1];
    wire [12:0] min_cost [1:2*LANES-1];
    wire [7:0] min_disparity [1:2*LANES-1];
    reg [12:0] group_cost_q;
    reg [7:0] group_disparity_q;
    integer r, c;

    assign s_tready = (state == IDLE);

    // All right-image taps use compile-time positions. Increasing LANES adds
    // arithmetic units; the right window shifts by LANES between groups.
    genvar g, gr;
    generate
        for (g = 0; g < LANES; g = g + 1) begin : GEN_LANE
            for (gr = 0; gr < 5; gr = gr + 1) begin : GEN_ROW
                wire [8:0] diff [0:4];
                genvar gc;
                for (gc = 0; gc < 5; gc = gc + 1) begin : GEN_COL
                    wire [7:0] a = left_window[gr][gc];
                    wire [7:0] b = right_work[gr][WINDOW-5-g+gc];
                    assign diff[gc] = (a >= b) ? {1'b0, a} - {1'b0, b}
                                                : {1'b0, b} - {1'b0, a};
                end
                assign row_sum[g][gr] = diff[0] + diff[1] + diff[2]
                                        + diff[3] + diff[4];
            end
        end
        for (g = 0; g < LANES; g = g + 1) begin : GEN_LEAF
            assign min_cost[LANES+g] = lane_cost_q[g];
            assign min_disparity[LANES+g] = group * LANES + g;
        end
        for (g = 1; g < LANES; g = g + 1) begin : GEN_TREE
            wire choose_left = min_cost[2*g] <= min_cost[2*g+1];
            assign min_cost[g] = choose_left ? min_cost[2*g] : min_cost[2*g+1];
            assign min_disparity[g] = choose_left ? min_disparity[2*g]
                                                  : min_disparity[2*g+1];
        end
    endgenerate

    always @(posedge clk) begin
        if (!resetn) begin
            state <= IDLE;
            x <= 0;
            y <= 0;
            input_x <= 0;
            input_y <= 0;
            input_left <= 0;
            input_right <= 0;
            group <= 0;
            best_cost <= 13'h1fff;
            best_disparity <= 0;
            group_cost_q <= 13'h1fff;
            group_disparity_q <= 0;
            m_tdata <= 0;
            m_tvalid <= 0;
            m_tuser <= 0;
            m_tlast <= 0;
        end else begin
            case (state)
                IDLE: if (s_tvalid) begin
                    input_x <= write_x;
                    input_y <= write_y;
                    input_left <= s_tdata[15:8];
                    input_right <= s_tdata[7:0];
                    left_taps <= left_lines[write_x];
                    right_taps <= right_lines[write_x];
                    state <= LOAD;
                end
                LOAD: begin
                    left_lines[input_x] <= {left_taps[23:0], input_left};
                    right_lines[input_x] <= {right_taps[23:0], input_right};
                    for (r = 0; r < 5; r = r + 1) begin
                        for (c = 0; c < 4; c = c + 1)
                            left_window[r][c] <= left_window[r][c+1];
                        for (c = 0; c < WINDOW-1; c = c + 1) begin
                            right_history[r][c] <= right_history[r][c+1];
                            right_work[r][c] <= right_history[r][c+1];
                        end
                        if (r == 4) begin
                            left_window[r][4] <= input_left;
                            right_history[r][WINDOW-1] <= input_right;
                            right_work[r][WINDOW-1] <= input_right;
                        end else begin
                            left_window[r][4] <= left_taps[31-8*r -: 8];
                            right_history[r][WINDOW-1] <= right_taps[31-8*r -: 8];
                            right_work[r][WINDOW-1] <= right_taps[31-8*r -: 8];
                        end
                    end
                    group <= 0;
                    best_cost <= 13'h1fff;
                    best_disparity <= 0;
                    state <= ROWS;
                end
                ROWS: begin
                    for (integer i = 0; i < LANES; i = i + 1)
                        for (r = 0; r < 5; r = r + 1)
                            row_sum_q[i][r] <= row_sum[i][r];
                    state <= COSTS;
                end
                COSTS: begin
                    for (integer i = 0; i < LANES; i = i + 1)
                        lane_cost_q[i] <= row_sum_q[i][0] + row_sum_q[i][1]
                                        + row_sum_q[i][2] + row_sum_q[i][3]
                                        + row_sum_q[i][4];
                    state <= REDUCE;
                end
                REDUCE: begin
                    group_cost_q <= min_cost[1];
                    group_disparity_q <= min_disparity[1];
                    state <= COMMIT;
                end
                COMMIT: begin
                    if (group_cost_q < best_cost) begin
                        best_cost <= group_cost_q;
                        best_disparity <= group_disparity_q;
                    end
                    if (group == GROUPS-1) begin
                        m_tdata <= (input_x < DISPARITIES+3 || input_y < 4 ||
                                    (group_cost_q < best_cost ? group_disparity_q : best_disparity)
                                    <= MIN_VALID_DISPARITY) ? 8'd0 :
                                   (group_cost_q < best_cost ? group_disparity_q : best_disparity);
                        m_tuser <= (input_x == 0 && input_y == 0);
                        // AXI DMA S2MM treats TLAST as the end of its whole
                        // transfer, not the end of a video line.
                        m_tlast <= (input_x == WIDTH-1 && input_y == HEIGHT-1);
                        m_tvalid <= 1;
                        state <= OUTPUT;
                    end else begin
                        for (r = 0; r < 5; r = r + 1)
                            for (c = 0; c < WINDOW; c = c + 1)
                                right_work[r][c] <= (c >= LANES)
                                    ? right_work[r][c-LANES] : 8'd0;
                        group <= group + 1'b1;
                        state <= ROWS;
                    end
                end
                OUTPUT: if (m_tready) begin
                    m_tvalid <= 0;
                    if (input_x == WIDTH-1) begin
                        x <= 0;
                        y <= (input_y == HEIGHT-1) ? 0 : input_y + 1'b1;
                    end else begin
                        x <= input_x + 1'b1;
                        y <= input_y;
                    end
                    state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
