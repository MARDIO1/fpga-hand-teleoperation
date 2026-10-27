`timescale 1ns / 1ps

// Transparent RGB565 AXI4-Stream probe for the live HDMI pipeline.
module axis_video_probe (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK",
       X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF S_AXIS:M_AXIS, ASSOCIATED_RESET aresetn" *)
    input  wire        aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST",
       X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire        aresetn,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TDATA" *)
    input  wire [15:0] s_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TUSER" *)
    input  wire [0:0]  s_axis_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TLAST" *)
    input  wire        s_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TVALID" *)
    input  wire        s_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TREADY" *)
    output wire        s_axis_tready,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TDATA" *)
    output wire [15:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TUSER" *)
    output wire [0:0]  m_axis_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *)
    output wire        m_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TVALID" *)
    output wire        m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *)
    input  wire        m_axis_tready,

    output reg  [31:0] last_line_pixels,
    output reg  [31:0] last_frame_lines
);

    reg [31:0] line_pixels;
    reg [31:0] frame_lines;
    wire transfer = s_axis_tvalid && m_axis_tready;

    assign s_axis_tready = m_axis_tready;
    assign m_axis_tdata = s_axis_tdata;
    assign m_axis_tuser = s_axis_tuser;
    assign m_axis_tlast = s_axis_tlast;
    assign m_axis_tvalid = s_axis_tvalid;

    always @(posedge aclk) begin
        if (!aresetn) begin
            line_pixels <= 0;
            frame_lines <= 0;
            last_line_pixels <= 0;
            last_frame_lines <= 0;
        end else if (transfer) begin
            if (s_axis_tuser[0])
                frame_lines <= 0;
            if (s_axis_tlast) begin
                last_line_pixels <= line_pixels + 1;
                line_pixels <= 0;
                last_frame_lines <= s_axis_tuser[0] ? 1 : frame_lines + 1;
                frame_lines <= s_axis_tuser[0] ? 1 : frame_lines + 1;
            end else begin
                line_pixels <= line_pixels + 1;
            end
        end
    end
endmodule
