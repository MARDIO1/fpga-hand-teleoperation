`timescale 1ns / 1ps

// Two small PL frame banks hold disparity; HDMI reads the last completed bank.
// The 160x180 map is expanded to 1280x720 by nearest-neighbor sampling.
module depth_video_overlay (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK",
       X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF S_AXIS:M_AXIS:DISPARITY, ASSOCIATED_RESET resetn" *)
    input wire clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST",
       X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input wire resetn,
    input wire mode_depth,
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
    output reg m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *)
    input wire m_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TUSER" *)
    output reg m_axis_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *)
    output reg m_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 DISPARITY TDATA" *)
    input wire [7:0] disparity_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 DISPARITY TVALID" *)
    input wire disparity_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 DISPARITY TREADY" *)
    output wire disparity_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 DISPARITY TUSER" *)
    input wire disparity_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 DISPARITY TLAST" *)
    input wire disparity_tlast,
    output wire [31:0] completed_frames
);
    `include "depth_palette.vh"
    localparam integer PIXELS = 160*180;
    localparam integer MIN_FRAME_PIXELS = PIXELS*9/10;
    (* ram_style = "block" *) reg [7:0] depth_memory [0:2*PIXELS-1];
    reg [15:0] write_index;
    reg write_bank;
    reg frame_active;
    reg [15:0] bank0_valid, bank1_valid;
    reg display_bank;
    reg pending_bank;
    reg pending;
    reg [10:0] x;
    reg [9:0] y;
    reg [15:0] raw_q;
    reg [7:0] disparity_q;
    reg mode_q;
    reg [11:0] frame_count;
    reg [19:0] disparity_count;
    assign completed_frames = {frame_count, disparity_count};

    wire advance = !m_axis_tvalid || m_axis_tready;
    assign s_axis_tready = advance;
    assign disparity_tready = 1'b1;
    assign m_axis_tdata = mode_q ? depth_color(disparity_q) : raw_q;
    wire [10:0] px = s_axis_tuser ? 11'd0 : x;
    wire [9:0] py = s_axis_tuser ? 10'd0 : y;
    wire next_bank = s_axis_tuser && pending ? pending_bank : display_bank;
    wire [15:0] read_index = (py >> 2)*160 + (px >> 3);
    wire unfinished_frame = disparity_tvalid && disparity_tuser && frame_active;
    wire usable_partial = unfinished_frame && write_index >= MIN_FRAME_PIXELS;
    wire completed_frame = disparity_tvalid && (disparity_tlast || usable_partial);
    wire current_write_bank = usable_partial ? !write_bank : write_bank;

    always @(posedge clk) begin
        if (!resetn) begin
            write_index <= 0;
            write_bank <= 0;
            frame_active <= 0;
            bank0_valid <= 0;
            bank1_valid <= 0;
            display_bank <= 1;
            pending_bank <= 0;
            pending <= 0;
            frame_count <= 0;
            disparity_count <= 0;
            x <= 0;
            y <= 0;
            raw_q <= 0;
            disparity_q <= 0;
            mode_q <= 0;
            m_axis_tvalid <= 0;
            m_axis_tuser <= 0;
            m_axis_tlast <= 0;
        end else begin
            if (disparity_tvalid) begin
                disparity_count <= disparity_count + 1'b1;
                depth_memory[(current_write_bank ? PIXELS : 0) +
                             (disparity_tuser ? 16'd0 : write_index)] <= disparity_tdata;
                if (usable_partial) begin
                    pending_bank <= write_bank;
                    pending <= 1;
                    frame_count <= frame_count + 1'b1;
                    if (write_bank) bank1_valid <= write_index;
                    else bank0_valid <= write_index;
                    write_bank <= !write_bank;
                end
                if (disparity_tuser)
                    frame_active <= 1;
                if (disparity_tlast) begin
                    write_index <= 0;
                    pending_bank <= current_write_bank;
                    pending <= 1;
                    write_bank <= !current_write_bank;
                    frame_count <= frame_count + 1'b1;
                    frame_active <= 0;
                    if (current_write_bank)
                        bank1_valid <= (disparity_tuser ? 16'd0 : write_index) + 1'b1;
                    else
                        bank0_valid <= (disparity_tuser ? 16'd0 : write_index) + 1'b1;
                end else begin
                    write_index <= (disparity_tuser ? 16'd0 : write_index) + 1'b1;
                end
            end
            if (advance) begin
                m_axis_tvalid <= s_axis_tvalid;
                if (s_axis_tvalid) begin
                    raw_q <= s_axis_tdata;
                    mode_q <= mode_depth;
                    m_axis_tuser <= s_axis_tuser;
                    m_axis_tlast <= s_axis_tlast;
                    disparity_q <= read_index < (next_bank ? bank1_valid : bank0_valid)
                        ? depth_memory[(next_bank ? PIXELS : 0) + read_index] : 8'd0;
                    if (s_axis_tuser && pending) begin
                        display_bank <= pending_bank;
                        if (!completed_frame) pending <= 0;
                    end
                    if (s_axis_tlast) begin
                        x <= 0;
                        y <= py + 1'b1;
                    end else begin
                        x <= px + 1'b1;
                        y <= py;
                    end
                end
            end
        end
    end
endmodule
