`timescale 1ns/1ps
// Single-shot capture and lease control. PS must verify VDMA IOC before lease commit.
module marker_ingress_control_v2(
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF S_AXI:M_AXI:CAM_IN:CAP_OUT:VIDEO_OUT, ASSOCIATED_RESET resetn" *) input wire clk,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 resetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire resetn,
output wire branch_resetn,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR" *) input wire [7:0] s_awaddr,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input wire  s_awvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output wire  s_awready,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input wire [31:0] s_wdata,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input wire [3:0] s_wstrb,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input wire  s_wvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output wire  s_wready,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output wire [1:0] s_bresp,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output wire  s_bvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input wire  s_bready,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input wire [7:0] s_araddr,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input wire  s_arvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output wire  s_arready,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output wire [31:0] s_rdata,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output wire [1:0] s_rresp,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID" *) output wire  s_rvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input wire  s_rready,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI ARADDR" *) output wire [31:0] m_araddr,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI ARLEN" *) output wire [7:0] m_arlen,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI ARSIZE" *) output wire [2:0] m_arsize,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI ARBURST" *) output wire [1:0] m_arburst,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI ARVALID" *) output wire  m_arvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI ARREADY" *) input wire  m_arready,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI RDATA" *) input wire [63:0] m_rdata,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI RRESP" *) input wire [1:0] m_rresp,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI RLAST" *) input wire  m_rlast,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI RVALID" *) input wire  m_rvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 M_AXI RREADY" *) output wire  m_rready,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAM_IN TDATA" *) input wire [15:0] c_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAM_IN TVALID" *) input wire  c_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAM_IN TREADY" *) output wire  c_tready,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAM_IN TUSER" *) input wire  c_tuser,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAM_IN TLAST" *) input wire  c_tlast,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAP_OUT TDATA" *) output wire [15:0] q_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAP_OUT TVALID" *) output wire  q_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAP_OUT TREADY" *) input wire  q_tready,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAP_OUT TUSER" *) output wire  q_tuser,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 CAP_OUT TLAST" *) output wire  q_tlast,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TDATA" *) output wire [15:0] v_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TVALID" *) output wire  v_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TREADY" *) input wire  v_tready,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TUSER" *) output wire  v_tuser,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TLAST" *) output wire  v_tlast,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TKEEP" *) output wire [1:0] v_tkeep,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TSTRB" *) output wire [1:0] v_tstrb,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TID" *) output wire  v_tid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 VIDEO_OUT TDEST" *) output wire  v_tdest
);

reg [31:0] debug_araddr;
reg [7:0] debug_arlen;
reg [31:0] debug_response;
reg [31:0] debug_beats;
reg aw_pending,w_pending,b_valid,r_valid;
reg [7:0] aw_addr;
reg [31:0] w_data,r_data;
reg [3:0] w_strobe;
assign s_awready=!aw_pending && !b_valid;
assign s_wready=!w_pending && !b_valid;
assign s_bvalid=b_valid; assign s_bresp=0;
assign s_arready=!r_valid; assign s_rvalid=r_valid;
assign s_rdata=r_data; assign s_rresp=0;
reg [31:0] capture_base,leased_base;
reg armed,active,capture_done,leased,command_error,gate_error,branch_enable;
reg [19:0] cap_pixels;
reg [10:0] cap_x;
reg [31:0] capture_id,source_id,lease_id;
reg [63:0] capture_stamp,lease_stamp,clock_us;
reg [6:0] divider;
reg eye_left,start_reader,abort_reader;
wire reader_busy,reader_done;
wire [3:0] reader_error;
wire [31:0] pixels_sent,result_id;
wire [63:0] result_stamp;
assign branch_resetn=resetn && branch_enable;
function allowed;
 input [31:0] address;
 begin allowed=(address==32'h1e000000 || address==32'h1e200000 || address==32'h1e600000);end
endfunction
wire gate_open=active || (armed && c_tuser);
assign q_tdata=c_tdata;assign q_tuser=c_tuser;assign q_tlast=c_tlast;
assign q_tvalid=c_tvalid && gate_open;
assign c_tready=gate_open ? q_tready : 1'b1;
assign v_tid=0;assign v_tdest=0;
marker_ddr_eye_reader_fifo reader(
 .clk(clk),.resetn(resetn),.start(start_reader),.abort_request(abort_reader),
 .frame_base(leased_base),.eye_left(eye_left),.frame_id(lease_id),.timestamp_us(lease_stamp),
 .busy(reader_busy),.done(reader_done),.error_flags(reader_error),.pixels_sent(pixels_sent),
 .result_frame_id(result_id),.result_timestamp_us(result_stamp),
 .m_axi_araddr(m_araddr),.m_axi_arlen(m_arlen),.m_axi_arsize(m_arsize),.m_axi_arburst(m_arburst),
 .m_axi_arvalid(m_arvalid),.m_axi_arready(m_arready),.m_axi_rdata(m_rdata),.m_axi_rresp(m_rresp),
 .m_axi_rlast(m_rlast),.m_axi_rvalid(m_rvalid),.m_axi_rready(m_rready),
 .video_tdata(v_tdata),.video_tkeep(v_tkeep),.video_tstrb(v_tstrb),.video_tuser(v_tuser),
 .video_tlast(v_tlast),.video_tvalid(v_tvalid),.video_tready(v_tready));
wire write_commit=aw_pending && w_pending && !b_valid;
wire [31:0] status_word={19'b0,gate_error,leased,capture_done,active,armed,5'b0,
                         (command_error || |reader_error),reader_done,reader_busy};
always @(posedge clk) begin
 if(!resetn) begin
  debug_araddr<=0;debug_arlen<=0;debug_response<=0;debug_beats<=0;
  aw_pending<=0;w_pending<=0;b_valid<=0;r_valid<=0;aw_addr<=0;w_data<=0;w_strobe<=0;r_data<=0;
  capture_base<=32'h1e000000;leased_base<=0;armed<=0;active<=0;capture_done<=0;leased<=0;
  command_error<=0;gate_error<=0;branch_enable<=0;cap_pixels<=0;cap_x<=0;
  capture_id<=0;source_id<=0;lease_id<=0;capture_stamp<=0;lease_stamp<=0;
  clock_us<=0;divider<=0;eye_left<=0;start_reader<=0;abort_reader<=0;
 end else begin
  start_reader<=0;abort_reader<=0;
  if(start_reader) begin debug_response<=0;debug_beats<=0;end
  if(m_arvalid && m_arready) begin debug_araddr<=m_araddr;debug_arlen<=m_arlen;end
  if(m_rvalid && m_rready) begin debug_response<={21'b0,m_rlast,6'b0,m_rresp};debug_beats<=debug_beats+1'b1;end
  if(divider==99) begin divider<=0;clock_us<=clock_us+1'b1;end else divider<=divider+1'b1;
  if(c_tvalid && c_tready && c_tuser) source_id<=source_id+1'b1;
  if(q_tvalid && q_tready) begin
   if(!active) begin
    armed<=0;active<=1;cap_pixels<=1;cap_x<=1;capture_stamp<=clock_us;capture_id<=source_id+1'b1;
    if(q_tlast) gate_error<=1;
   end else begin
    if(q_tuser || (q_tlast != (cap_x==1279))) gate_error<=1;
    cap_x<=cap_x==1279 ? 0 : cap_x+1'b1;
    cap_pixels<=cap_pixels+1'b1;
    if(cap_pixels==921599) begin active<=0;capture_done<=1;end
   end
  end
  if(s_awvalid && s_awready) begin aw_addr<=s_awaddr;aw_pending<=1;end
  if(s_wvalid && s_wready) begin w_data<=s_wdata;w_strobe<=s_wstrb;w_pending<=1;end
  if(s_bvalid && s_bready) b_valid<=0;
  if(write_commit) begin
   aw_pending<=0;w_pending<=0;b_valid<=1;
   // Control writes are full words; partial writes have no side effects.
   if(w_strobe!=4'hf) command_error<=1;
   else case(aw_addr)
    8'h08: begin
     if(w_data[2] && !reader_busy) command_error<=0;
     if(w_data[1]) abort_reader<=1;
     if(w_data[3]) begin
      if(!reader_busy && !start_reader) leased<=0;else command_error<=1;
     end
     // Software commits only after the VDMA IOC (final DDR write response).
     if(w_data[4]) begin
      if(capture_done && !gate_error && !leased && !reader_busy) begin
       leased<=1;leased_base<=capture_base;lease_id<=capture_id;lease_stamp<=capture_stamp;capture_done<=0;
      end else command_error<=1;
     end
     if(w_data[0]) begin
      if(leased && !reader_busy && !start_reader && branch_enable && !command_error) start_reader<=1;
      else command_error<=1;
     end
    end
    8'h10: if(!active && !armed && !capture_done && allowed(w_data)) capture_base<=w_data;else command_error<=1;
    8'h18: if(!reader_busy && !start_reader && w_data<2) eye_left<=w_data[0];else command_error<=1;
    8'h34: if(w_data==1 && !armed && !active && !capture_done && allowed(capture_base) &&
                (!leased || capture_base!=leased_base)) begin armed<=1;gate_error<=0;end else command_error<=1;
    8'h38: if(!reader_busy && !start_reader) branch_enable<=w_data[0];else command_error<=1;
    default: command_error<=1;
   endcase
  end
  if(s_rvalid && s_rready) r_valid<=0;
  if(s_arvalid && s_arready) begin
   r_valid<=1;
   case(s_araddr)
    8'h00:r_data<=32'h4d495632;
    8'h04:r_data<=32'h0000020b; // v2.0: direct, leased capture, one-shot gate; no display
    8'h0c:r_data<=status_word;
    8'h10:r_data<=capture_base;
    8'h14:r_data<=2560;
    8'h18:r_data<={31'b0,eye_left};
    8'h1c:r_data<=lease_id;
    8'h20:r_data<=lease_stamp[31:0];
    8'h24:r_data<=lease_stamp[63:32];
    8'h28:r_data<=leased_base;
    8'h2c:r_data<={26'b0,gate_error,command_error,reader_error};
    8'h30:r_data<=pixels_sent;
    8'h34:r_data<=capture_id;
    8'h38:r_data<={31'b0,branch_enable};
    8'h3c:r_data<={12'b0,cap_pixels};
    8'h40:r_data<=debug_araddr;
    8'h44:r_data<={24'b0,debug_arlen};
    8'h48:r_data<=debug_response;
    8'h4c:r_data<=debug_beats;
    default:r_data<=0;
   endcase
  end
 end
end
endmodule
