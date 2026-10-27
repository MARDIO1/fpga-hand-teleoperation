`timescale 1ns/1ps
// Fixed 640x720 DMA frame to video markers; 40-byte results to 64-bit DMA.
module marker_axis_bridge(
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF DMA_IN:VIDEO_OUT:REGIONS_IN:DMA_OUT, ASSOCIATED_RESET resetn" *) input wire clk,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 resetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire resetn,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_IN TDATA" *) input wire [15:0] s_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_IN TVALID" *) input wire s_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_IN TREADY" *) output wire s_tready,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_IN TKEEP" *) input wire [1:0] s_tkeep,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_IN TLAST" *) input wire s_tlast,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TDATA" *) output wire [15:0] v_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TVALID" *) output wire v_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TREADY" *) input wire v_tready,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TKEEP" *) output wire [1:0] v_tkeep,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TSTRB" *) output wire [1:0] v_tstrb,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TUSER" *) output wire v_tuser,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TLAST" *) output wire v_tlast,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TID" *) output wire v_tid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TDEST" *) output wire v_tdest,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 REGIONS_IN TDATA" *) input wire [319:0] r_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 REGIONS_IN TVALID" *) input wire r_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 REGIONS_IN TREADY" *) output wire r_tready,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 REGIONS_IN TKEEP" *) input wire [39:0] r_tkeep,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 REGIONS_IN TLAST" *) input wire r_tlast,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_OUT TDATA" *) output wire [63:0] m_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_OUT TVALID" *) output wire m_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_OUT TREADY" *) input wire m_tready,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_OUT TKEEP" *) output wire [7:0] m_tkeep,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 DMA_OUT TLAST" *) output wire m_tlast);
reg [9:0] x=0,y=0;
assign v_tdata=s_tdata;
assign v_tvalid=s_tvalid;
assign s_tready=v_tready;
assign v_tkeep=s_tkeep;
assign v_tstrb=s_tkeep;
assign v_tuser=(x==0 && y==0);
assign v_tlast=(x==639);
assign v_tid=0;
assign v_tdest=0;
always @(posedge clk) begin
 if (!resetn) begin x<=0;y<=0; end
 else if (s_tvalid && s_tready) begin
  if (x==639) begin x<=0; y<=y==719 ? 0 : y+1'b1; end
  else x<=x+1'b1;
 end
end
reg [319:0] payload=0;
reg [39:0] keep=0;
reg last=0,busy=0;
reg [2:0] index=0;
assign r_tready=!busy;
assign m_tvalid=busy;
assign m_tdata=payload[63:0];
assign m_tkeep=keep[7:0];
assign m_tlast=last && index==4;
always @(posedge clk) begin
 if (!resetn) begin busy<=0;index<=0; end
 else if (r_tvalid && r_tready) begin
  payload<=r_tdata;keep<=r_tkeep;last<=r_tlast;index<=0;busy<=1;
 end else if (m_tvalid && m_tready) begin
  payload<=payload>>64;keep<=keep>>8;
  if (index==4) busy<=0;
  else index<=index+1'b1;
 end
end
endmodule
