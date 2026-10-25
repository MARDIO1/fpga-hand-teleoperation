`timescale 1ns / 1ps
module tb_stereo_line_controller;
    reg clk = 0;
    always #5 clk = !clk;
    reg resetn = 0;
    reg [7:0] a[0:19], b[0:19], expected[0:35];
    integer pa = 0, pb = 0, supplied_a = 0, supplied_b = 0, received = 0;
    integer i, row, n;
    wire ra, rb, clear, valid;
    wire [7:0] data;
    wire [13:0] count_a = supplied_a-pa, count_b = supplied_b-pb;
    stereo_line_controller #(.IMG_WIDTH(4)) dut (
        .clk(clk), .rst_n(resetn), .rdreq1(ra), .rdreq2(rb),
        .rddata1(a[pa]), .rddata2(b[pb]),
        .rdusedw1(count_a), .rdusedw2(count_b),
        .fifo_aclr(clear), .fifo_wrreq(valid), .fifo_wrdata(data)
    );
    always @(posedge clk) if (resetn) begin
        if (valid) begin
            if (received >= 36 || data !== expected[received])
                $fatal(1, "bad row byte %0d: %h expected %h", received, data, expected[received]);
            received <= received+1;
        end
        if (ra) begin
            if (pa >= supplied_a) $fatal(1, "A underflow");
            pa <= pa+1;
        end
        if (rb) begin
            if (pb >= supplied_b) $fatal(1, "B underflow");
            pb <= pb+1;
        end
    end
    initial begin
        n = 0;
        for (row = 0; row < 2; row = row+1) begin
            for (i = 0; i < 10; i = i+1) begin
                a[row*10+i] = i < 2 ? (i == 0 ? row : 0) : 8'ha0 + row*10+i;
                b[row*10+i] = i < 2 ? (i == 0 ? row : 0) : 8'hb0 + row*10+i;
                expected[n] = a[row*10+i]; n = n+1;
            end
            for (i = 2; i < 10; i = i+1) begin
                expected[n] = b[row*10+i]; n = n+1;
            end
        end
        repeat (4) @(negedge clk);
        resetn = 1;
        supplied_b = 10;
        repeat (15) @(negedge clk);
        if (received != 0 || pb != 0) $fatal(1, "B must not start a combined row");
        supplied_a = 20;
        wait (received == 28);
        repeat (15) @(negedge clk);
        if (received != 28) $fatal(1, "must wait for missing B half-row");
        supplied_b = 20;
        wait (received == 36);
        repeat (5) @(negedge clk);
        if (pa != 20 || pb != 20) $fatal(1, "wrong FIFO byte counts");
        $display("PASS B-first startup and delayed B preserve two complete row packets");
        $finish;
    end
    initial begin
        #10000;
        $fatal(1, "timeout");
    end
endmodule
