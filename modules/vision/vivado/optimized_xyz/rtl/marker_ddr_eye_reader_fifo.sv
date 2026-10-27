`timescale 1ns/1ps
// Optional reader experiment: identical V2 ports; no changes to the active integration.
module marker_ddr_eye_reader_fifo #(
 parameter integer WIDTH=640, HEIGHT=720, STRIDE_BYTES=2560,
 parameter integer FIFO_WORDS=64
)(
 input wire clk,resetn,start,abort_request,
 input wire [31:0] frame_base,
 input wire eye_left,
 input wire [31:0] frame_id,
 input wire [63:0] timestamp_us,
 output reg busy,done,
 output reg [3:0] error_flags,
 output reg [31:0] result_frame_id,
 output reg [63:0] result_timestamp_us,
 output reg [31:0] pixels_sent,
 output reg [31:0] m_axi_araddr,
 output reg [7:0] m_axi_arlen,
 output wire [2:0] m_axi_arsize,
 output wire [1:0] m_axi_arburst,
 output reg m_axi_arvalid,
 input wire m_axi_arready,
 input wire [63:0] m_axi_rdata,
 input wire [1:0] m_axi_rresp,
 input wire m_axi_rlast,m_axi_rvalid,
 output wire m_axi_rready,
 output wire [15:0] video_tdata,
 output wire [1:0] video_tkeep,video_tstrb,
 output wire video_tuser,video_tlast,video_tvalid,
 input wire video_tready
);
 localparam integer PTR_BITS=$clog2(FIFO_WORDS);
 localparam IDLE=0,ISSUE=1,ADDRESS=2,READ=3,DRAIN=4;
 reg [2:0] state;
 reg [63:0] fifo [0:FIFO_WORDS-1];
 reg [PTR_BITS-1:0] read_ptr,write_ptr;
 reg [PTR_BITS:0] word_count;
 reg [1:0] lane;
 reg [31:0] row_base,read_address;
 reg [15:0] row_bytes_left,read_row,x,y;
 reg [4:0] beats_left;
 reg cancelled,output_locked;
 wire cancel_now=cancelled||abort_request;
 wire [31:0] boundary_bytes=4096-(read_address&32'hfff);
 wire [31:0] row_limit=row_bytes_left<128?row_bytes_left:128;
 wire [31:0] burst_bytes=row_limit<boundary_bytes?row_limit:boundary_bytes;
 wire [4:0] next_beats=burst_bytes>>3;
 wire response_bad=m_axi_rresp!=0 || m_axi_rlast!=(beats_left==1);
 wire receive=m_axi_rvalid&&m_axi_rready;
 wire push=receive&&!cancel_now&&!response_bad;
 wire pop=video_tvalid&&video_tready&&lane==3;
 assign m_axi_arsize=3;
 assign m_axi_arburst=1;
 // Reserve a complete burst before AR, so errors/abort can always drain it.
 assign m_axi_rready=busy&&state==READ&&(cancel_now||word_count<FIFO_WORDS);
 assign video_tdata=fifo[read_ptr]>>(lane*16);
 assign video_tkeep=3;
 assign video_tstrb=3;
 assign video_tvalid=busy&&word_count!=0&&(!cancel_now||(output_locked&&!abort_request));
 assign video_tuser=x==0&&y==0;
 assign video_tlast=x==WIDTH-1;
 initial begin
  if(FIFO_WORDS<16 || (FIFO_WORDS&(FIFO_WORDS-1))!=0)
   $fatal(1,"FIFO_WORDS must be a power of two and at least 16");
 end
 always @(posedge clk) begin
  if(!resetn) begin
   state<=IDLE;busy<=0;done<=0;error_flags<=0;
   m_axi_araddr<=0;m_axi_arlen<=0;m_axi_arvalid<=0;
   read_ptr<=0;write_ptr<=0;word_count<=0;lane<=0;
   row_base<=0;read_address<=0;row_bytes_left<=0;read_row<=0;
   x<=0;y<=0;beats_left<=0;cancelled<=0;pixels_sent<=0;
   result_frame_id<=0;result_timestamp_us<=0;output_locked<=0;
  end else begin
   output_locked<=video_tvalid&&!video_tready;
   if(push) begin fifo[write_ptr]<=m_axi_rdata;write_ptr<=write_ptr+1'b1;end
   if(video_tvalid&&video_tready) begin
    pixels_sent<=pixels_sent+1;
    if(lane==3) begin lane<=0;read_ptr<=read_ptr+1'b1;end
    else lane<=lane+1'b1;
    if(x==WIDTH-1) begin x<=0;y<=y+1'b1;end
    else x<=x+1'b1;
   end
   case({push,pop})
    2'b10:word_count<=word_count+1'b1;
    2'b01:word_count<=word_count-1'b1;
    default:;
   endcase
   if(busy&&abort_request) begin cancelled<=1;error_flags[3]<=1;end
   // Preserve a stalled output pixel until accepted, even when an AXI error cancels the frame.
   if(busy&&cancel_now&&(!output_locked||abort_request)) begin word_count<=0;read_ptr<=0;write_ptr<=0;lane<=0;end
   case(state)
    IDLE:if(start) begin
     done<=0;error_flags<=0;pixels_sent<=0;cancelled<=0;
     read_ptr<=0;write_ptr<=0;word_count<=0;lane<=0;
     x<=0;y<=0;read_row<=0;
     result_frame_id<=frame_id;result_timestamp_us<=timestamp_us;
     if(frame_base[2:0]!=0 || WIDTH%4!=0 || STRIDE_BYTES<WIDTH*4 ||
        {1'b0,frame_base}+HEIGHT*STRIDE_BYTES>33'h100000000) begin
      error_flags<=1;done<=1;
     end else begin
      row_base<=frame_base+(eye_left?WIDTH*2:0);
      read_address<=frame_base+(eye_left?WIDTH*2:0);
      row_bytes_left<=WIDTH*2;busy<=1;state<=ISSUE;
     end
    end
    ISSUE:begin
     if(cancel_now) state<=DRAIN;
     else if(FIFO_WORDS-word_count>=next_beats) begin
      m_axi_araddr<=read_address;m_axi_arlen<=next_beats-1'b1;
      beats_left<=next_beats;m_axi_arvalid<=1;state<=ADDRESS;
     end
    end
    // Even on abort an already asserted AR must remain valid until accepted.
    ADDRESS:if(m_axi_arvalid&&m_axi_arready) begin m_axi_arvalid<=0;state<=READ;end
    READ:if(receive) begin
     beats_left<=beats_left-1'b1;
     read_address<=read_address+8;row_bytes_left<=row_bytes_left-8;
     if(m_axi_rresp!=0) begin error_flags[1]<=1;cancelled<=1;end
     if(m_axi_rlast!=(beats_left==1)) begin error_flags[2]<=1;cancelled<=1;end
     // Missing RLAST drains until the actual last beat, or an external watchdog.
     if(m_axi_rlast) begin
      if(cancel_now||response_bad) state<=DRAIN;
      else if(row_bytes_left==8) begin
       if(read_row==HEIGHT-1) state<=DRAIN;
       else begin
        row_base<=row_base+STRIDE_BYTES;read_address<=row_base+STRIDE_BYTES;
        row_bytes_left<=WIDTH*2;read_row<=read_row+1'b1;state<=ISSUE;
       end
      end else state<=ISSUE;
     end
    end
    DRAIN:if((word_count==0||cancel_now)&&(!output_locked||abort_request)) begin busy<=0;done<=1;state<=IDLE;word_count<=0;end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
