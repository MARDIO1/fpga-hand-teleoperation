`timescale 1ns/1ps
module tb_mpu6050;
    reg clk=0, resetn=0;
    always #5 clk=~clk; // production 100 MHz clock / fast-mode bus
    tri1 scl, sda;
    reg slave_low=0, hold_scl=0, connected=1;
    assign sda=slave_low ? 1'b0 : 1'bz;
    assign scl=hold_scl ? 1'b0 : 1'bz;
    reg [7:0] araddr=0, awaddr=0;
    reg arvalid=0, rready=0, awvalid=0, wvalid=0, bready=0;
    reg [31:0] wdata=0;
    reg stream_ready=0;
    wire [31:0] stream_data;
    wire stream_valid, stream_last;
    wire arready, rvalid, awready, wready, bvalid;
    wire [31:0] rdata;
    wire [1:0] rresp, bresp;
    mpu6050_axi #(.CLK_HZ(100000000), .I2C_HZ(400000), .STARTUP_US(50), .POLL_US(20)) dut (
        .s_axi_aclk(clk), .s_axi_aresetn(resetn),
        .s_axi_awaddr(awaddr), .s_axi_awprot(3'b0), .s_axi_awvalid(awvalid), .s_axi_awready(awready),
        .s_axi_wdata(wdata), .s_axi_wstrb(4'hf), .s_axi_wvalid(wvalid), .s_axi_wready(wready),
        .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(bready),
        .s_axi_araddr(araddr), .s_axi_arprot(3'b0), .s_axi_arvalid(arvalid), .s_axi_arready(arready),
        .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid), .s_axi_rready(rready),
        .mpu_scl(scl), .mpu_sda(sda), .m_axis_tdata(stream_data),
        .m_axis_tvalid(stream_valid), .m_axis_tlast(stream_last), .m_axis_tready(stream_ready));
    reg [7:0] regs [0:127];
    realtime scl_fall_time=0, scl_rise_time=0;
    always @(negedge scl) begin
        if(resetn && !hold_scl && scl_rise_time>0 && $realtime-scl_rise_time<600)
            $fatal(1,"I2C high time below 0.6 us");
        scl_fall_time=$realtime;
    end
    always @(posedge scl) begin
        if(resetn && !hold_scl && scl_fall_time>0 && $realtime-scl_fall_time<1300)
            $fatal(1,"I2C low time below 1.3 us");
        scl_rise_time=$realtime;
    end
    reg [7:0] addr, reg_addr, value;
    reg master_ack;
    integer i, reads=0;
    integer wake_writes=0;
    task receive_byte(output reg [7:0] data);
        integer b;
        begin
            for(b=7;b>=0;b=b-1) begin @(posedge scl); #100; data[b]=sda; end
            @(negedge scl);
        end
    endtask
    task write_reg(input [7:0] address, input [31:0] data, input [1:0] response);
        begin
            @(negedge clk); awaddr=address; awvalid=1;
            do @(posedge clk); while(!awready);
            @(negedge clk); awvalid=0; wdata=data; wvalid=1;
            do @(posedge clk); while(!wready);
            @(negedge clk); wvalid=0;
            wait(bvalid);
            if(bresp !== response) $fatal(1,"Write response %h expected %h at %h",bresp,response,address);
            @(negedge clk); bready=1;
            @(negedge clk); bready=0;
        end
    endtask
    reg [31:0] expected_packet [0:15];
    integer word_index;
    task ack;
        begin
            slave_low=connected;
            @(posedge scl); @(negedge scl); slave_low=0;
        end
    endtask
    task send_byte(input reg [7:0] data);
        integer b;
        begin
            for(b=7;b>=0;b=b-1) begin
                slave_low=!data[b]; @(posedge scl); @(negedge scl);
            end
            slave_low=0; @(posedge scl); #100; master_ack=!sda; @(negedge scl);
        end
    endtask
    initial begin
        for(i=0;i<128;i=i+1) regs[i]=0;
        regs['h75]='h68; regs['h3a]=1;
        regs['h3b]='h12; regs['h3c]='h34;
        regs['h3d]='hfe; regs['h3e]='hdc;
        regs['h3f]='h20; regs['h40]='h00;
        regs['h41]='h01; regs['h42]='h02;
        regs['h43]='hff; regs['h44]='h80;
        regs['h45]='h00; regs['h46]='h40;
        regs['h47]='h7f; regs['h48]='hff;
        forever begin
            @(negedge sda);
            if(scl && connected) begin
                receive_byte(addr);
                if(addr !== 8'hd0) $fatal(1,"Incorrect write address %h",addr);
                ack(); receive_byte(reg_addr); ack();
                if(reg_addr=='h75 || reg_addr=='h3a || reg_addr=='h3b || (reg_addr=='h6b && dut.imu.operation==14)) begin
                    @(negedge sda);
                    if(!scl) $fatal(1,"Missing repeated START");
                    receive_byte(addr);
                    if(addr !== 8'hd1) $fatal(1,"Incorrect read address");
                    ack();
                    for(i=0;i<(reg_addr=='h3b ? 14:1);i=i+1) begin
                        send_byte(regs[reg_addr+i]);
                        if(master_ack !== (i<(reg_addr=='h3b ? 13:0)))
                            $fatal(1,"Incorrect master ACK/NACK at byte %d",i);
                    end
                    if(reg_addr=='h3b) reads=reads+1;
                end else begin
                    receive_byte(value); ack();
                    if(reg_addr=='h6b && value==8'h80) begin regs[reg_addr]=8'h40; wake_writes=0; end
                    else if(reg_addr=='h6b && value==8'h01) begin
                        wake_writes=wake_writes+1;
                        regs[reg_addr]=(wake_writes==1) ? 8'h41 : 8'h01;
                    end else regs[reg_addr]=value;
                end
                do @(posedge sda); while(!scl);
            end
        end
    end
    task read_reg(input [7:0] address, input [31:0] expected, input [1:0] response);
        reg [31:0] held;
        begin
            @(negedge clk); araddr=address; arvalid=1;
            do @(posedge clk); while(!arready);
            @(negedge clk); arvalid=0;
            wait(rvalid); held=rdata;
            if(rdata !== expected || rresp !== response)
                $fatal(1,"Register %h got %h/%h expected %h/%h", address,rdata,rresp,expected,response);
            repeat(3) begin @(posedge clk); #100;
                if(!rvalid || rdata !== held) $fatal(1,"AXI read changed under backpressure");
            end
            @(negedge clk); rready=1;
            @(negedge clk); rready=0;
        end
    endtask
    initial begin
        #10000; resetn=1;
        wait(dut.sample_valid);
        if(wake_writes<2 || regs['h6b]!=1) $fatal(1,"Sensor woke without verified SLEEP clear");
        if(dut.sample !== 112'h1234fedc20000102ff8000407fff) $fatal(1,"Burst byte order");
        if(regs['h19] != 1 || regs['h1b] != 8 || regs['h1c] != 8 || regs['h1a] != 2)
            $fatal(1,"Incorrect initialization");
        read_reg('h00,32'h4d505531,0);
        read_reg('h14,32'h1234,0); read_reg('h18,32'hfffffedc,0);
        read_reg('h20,32'hffffff80,0); read_reg('h2c,32'h0102,0);
        read_reg('hb0,0,2); read_reg('h01,0,2);
        // AW and W arrive independently; response must wait for both.
        @(negedge clk); wvalid=1;
        @(negedge clk); wvalid=0;
        repeat(4) @(negedge clk);
        if(bvalid) $fatal(1,"Write responded before AW");
        awvalid=1; @(negedge clk); awvalid=0;
        wait(bvalid);
        repeat(3) @(negedge clk);
        if(!bvalid || bresp!=2) $fatal(1,"Write rejection unstable");
        bready=1; @(negedge clk); bready=0;
        for(word_index=0;word_index<16;word_index=word_index+1)
            expected_packet[word_index]=32'h11000000+word_index;
        expected_packet[0]=32'h494d5531; expected_packet[1]=32'h00010003;
        expected_packet[5]=32'hfedc1234; expected_packet[9]=32'h3fc00000;
        write_reg('h80,1,2); // reject uninitialized packet
        for(word_index=0;word_index<16;word_index=word_index+1)
            write_reg('h40+word_index*4,expected_packet[word_index],0);
        write_reg('h80,1,0);
        write_reg('h80,1,2); // busy must never overwrite the frame
        write_reg('h64,32'hdeadbeef,0); // editing shadow cannot change active packet
        read_reg('he4,32'h3fc00000,0);
        repeat(4) begin
            @(posedge clk); #100;
            if(!stream_valid || stream_data !== expected_packet[0]) $fatal(1,"Stream backpressure corrupted frame");
        end
        @(negedge clk); stream_ready=1;
        for(word_index=0;word_index<16;word_index=word_index+1) begin
            @(posedge clk);
            if(!stream_valid || stream_data !== expected_packet[word_index] || stream_last !== (word_index==15))
                $fatal(1,"Packet mismatch at word %d",word_index);
        end
        @(negedge clk); stream_ready=0;
        if(stream_valid) $fatal(1,"Packet did not end");
        read_reg('h84,1,0);
        write_reg('h90,32'h00007501,0);
        wait(dut.diagnostic_count==1);
        read_reg('h94,32'h68,0);
        write_reg('h90,32'h00021903,0);
        wait(dut.diagnostic_count==2);
        if(regs['h19] != 2) $fatal(1,"Diagnostic register write failed");
        wait(dut.sequence_number >= 2);
        if(dut.timestamp_us == 0 || dut.error_count != 0) $fatal(1,"Timestamp/error");
        // Force a stuck clock, then ensure timeout invalidates data and recovers.
        wait(dut.imu.state==3 && !dut.imu.bus.busy);
        hold_scl=1;
        wait(dut.error_count != 0);
        if(dut.sample_valid || dut.initialized) $fatal(1,"Stale data remained valid");
        hold_scl=0;
        wait(dut.sample_valid);
        if(dut.error_count != 1) $fatal(1,"Clock-stuck recovery failed");
        wait(dut.imu.state==3 && !dut.imu.bus.busy);
        connected=0;
        wait(dut.error_count == 2);
        if(dut.sample_valid) $fatal(1,"NACK kept stale sample valid");
        connected=1;
        wait(dut.sample_valid);
        if(dut.timestamp_us == 0) $fatal(1,"Recovery lost timestamp");
        $display("PASS: I2C burst, initialization, signed AXI reads, AXIS raw/pose/timestamp packet, backpressure, timeout/NACK recovery");
        $finish;
    end
    initial begin #100000000; $fatal(1,"Simulation watchdog"); end
endmodule
