module cache(
	wrclk,
	aclr,
	wrreq,
	wrdata,
	rdclk,
	rdreq,
	rddata,
	rdusedw
);
	input wrclk;
	input aclr;
	input wrreq;
	input [7:0] wrdata;
	input rdclk;
	input rdreq;
	output [7:0] rddata;
	output [13:0] rdusedw;
	
	dc_fifo	dc_fifo_inst(
		.rst(aclr),	  //
		.din(wrdata),	  // input	[7:0]  data
		.rd_clk(rdclk),	  //
		.rd_en(rdreq),	  //
		.wr_clk(wrclk),	  //
		.wr_en(wrreq),	  // 
		.dout(rddata),		  //output	[7:0]  q
		.rd_data_count(rdusedw),// output	[12:0]  rdusedw
		.wr_data_count() 		  // output	[12:0]  wrusedw
	);

endmodule
