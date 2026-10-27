`timescale 1ns / 1ps

// Vivado block design module reference wrapper for the SystemVerilog core.
module stereo_sad_bd #(
    parameter integer LANES = 8
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK",
       X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF S_AXIS:M_AXIS, ASSOCIATED_RESET resetn" *)
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
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TDATA" *)
    output wire [7:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TVALID" *)
    output wire m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *)
    input wire m_axis_tready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *)
    output wire m_axis_tlast
);
    wire unused_user;
    stereo_sad #(.LANES(LANES)) core (
        .clk(clk), .resetn(resetn),
        .s_tdata(s_axis_tdata), .s_tvalid(s_axis_tvalid),
        .s_tready(s_axis_tready), .s_tuser(1'b0),
        .m_tdata(m_axis_tdata), .m_tvalid(m_axis_tvalid),
        .m_tready(m_axis_tready), .m_tuser(unused_user),
        .m_tlast(m_axis_tlast)
    );
endmodule
