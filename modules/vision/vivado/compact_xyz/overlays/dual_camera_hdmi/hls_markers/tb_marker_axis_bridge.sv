`timescale 1ns/1ps
module tb_marker_axis_bridge;
reg clk=0; always #5 clk=~clk;
reg resetn=0;
reg [15:0] s_tdata=0;reg s_tvalid=0;wire s_tready;
wire [15:0] v_tdata;wire v_tvalid;reg v_tready=0;wire v_tuser,v_tlast;
reg [319:0] r_tdata=0;reg r_tvalid=0;wire r_tready;reg r_tlast=0;
wire [63:0] m_tdata;wire m_tvalid;reg m_tready=0;wire [7:0] m_tkeep;wire m_tlast;
marker_axis_bridge dut(.clk(clk),.resetn(resetn),.s_tdata(s_tdata),.s_tvalid(s_tvalid),.s_tready(s_tready),.s_tkeep(2'b11),.s_tlast(1'b0),.v_tdata(v_tdata),.v_tvalid(v_tvalid),.v_tready(v_tready),.v_tuser(v_tuser),.v_tlast(v_tlast),.r_tdata(r_tdata),.r_tvalid(r_tvalid),.r_tready(r_tready),.r_tkeep(40'hffffffffff),.r_tlast(r_tlast),.m_tdata(m_tdata),.m_tvalid(m_tvalid),.m_tready(m_tready),.m_tkeep(m_tkeep),.m_tlast(m_tlast));
integer sent=0,received=0,packets=0,chunks=0,cycles=0,j;
reg [63:0] held;reg stalled=0;
always @(posedge clk) if(resetn) begin
 cycles=cycles+1;
 if(v_tvalid&&v_tready) begin
  if(v_tdata !== (received&16'hffff) || v_tuser !== (received%(640*720)==0) || v_tlast !== (received%640==639)) $fatal(1,"video mismatch %d",received);
  received=received+1;
 end
 if(stalled && (m_tdata!==held || !m_tvalid)) $fatal(1,"backpressure changed data");
 stalled=m_tvalid&&!m_tready;held=m_tdata;
 if(m_tvalid&&m_tready) begin
  if(m_tdata !== chunks || m_tkeep!==8'hff || m_tlast !== (chunks==14)) $fatal(1,"result mismatch %d data=%d",chunks,m_tdata);
  chunks=chunks+1;
 end
 if(cycles>2000000) $fatal(1,"timeout");
end
initial begin
 repeat(4) @(negedge clk);resetn=1;
 fork
 begin
  while(sent<640*720+5) begin
   @(negedge clk);s_tvalid=1;s_tdata=sent;
   @(posedge clk);if(s_tready)sent=sent+1;
  end
  @(negedge clk);s_tvalid=0;
 end
 begin
  forever begin @(negedge clk);v_tready=($random&3)!=0;m_tready=($random&3)!=0; end
 end
 begin
  for(packets=0;packets<3;packets=packets+1) begin
   @(negedge clk);
   for(j=0;j<5;j=j+1)r_tdata[j*64+:64]=packets*5+j;
   r_tlast=packets==2;r_tvalid=1;
   @(posedge clk);while(!r_tready)@(posedge clk);
   @(negedge clk);r_tvalid=0;
  end
 end
 begin
  wait(received==640*720+5 && chunks==15);
  $display("BRIDGE PASS frame wrap SOF EOL serialization backpressure");$finish;
 end
 join
end
endmodule
