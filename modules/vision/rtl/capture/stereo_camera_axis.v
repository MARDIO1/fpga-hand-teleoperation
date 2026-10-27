`timescale 1ns / 1ps

// Vendor OV5640 acquisition, with its paired line stream converted to RGB565
// AXI4-Stream Video. The line number precedes each 1280-pixel pair of rows.
module stereo_camera_axis (
    input wire clk_50m,
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 axis_clk CLK",
       X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF M_AXIS, ASSOCIATED_RESET axis_resetn" *)
    input wire axis_clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 axis_resetn RST",
       X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input wire axis_resetn,
    output wire camera1_sclk, inout wire camera1_sdat,
    input wire camera1_vsync, input wire camera1_href,
    input wire camera1_pclk, output wire camera1_xclk,
    input wire [7:0] camera1_data,
    output wire camera1_rst_n, output wire camera1_pwdn,
    output wire camera2_sclk, inout wire camera2_sdat,
    input wire camera2_vsync, input wire camera2_href,
    input wire camera2_pclk, output wire camera2_xclk,
    input wire [7:0] camera2_data,
    output wire camera2_rst_n, output wire camera2_pwdn,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TDATA" *)
    output wire [15:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TUSER" *)
    output wire [0:0] m_axis_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *)
    output wire m_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TVALID" *)
    output wire m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *)
    input wire m_axis_tready,
    output reg [31:0] overflow_count,
    output reg [31:0] source_frame_count
);
    wire clk_125m_unused, clk_50m_internal, clk_24m, locked;
    pll clocks (
        .resetn(axis_resetn), .clk_in1(clk_50m),
        .clk_out1(clk_125m_unused), .clk_out2(clk_50m_internal),
        .clk_out3(clk_24m), .locked(locked)
    );
    assign camera1_xclk = clk_24m;
    assign camera2_xclk = clk_24m;
    assign camera1_pwdn = 1'b0;
    assign camera2_pwdn = 1'b0;

    // The vendor initializer leaves camera_rst_n permanently high. Pulse both
    // sensor resets on each PL reconfiguration, before its 21 ms I2C startup.
    reg [16:0] sensor_reset_count;
    always @(posedge clk_50m_internal or negedge locked) begin
        if (!locked)
            sensor_reset_count <= 0;
        else if (sensor_reset_count < 17'd100000)
            sensor_reset_count <= sensor_reset_count + 1'b1;
    end
    wire sensor_reset_released = sensor_reset_count == 17'd100000;
    assign camera1_rst_n = sensor_reset_released;
    assign camera2_rst_n = sensor_reset_released;

    wire init1, init2;
    wire initialized = init1 && init2;
    camera_init #(.CAMERA_TYPE("ov5640"), .IMAGE_TYPE(0),
        .IMAGE_WIDTH(640), .IMAGE_HEIGHT(720),
        .IMAGE_FLIP_EN(1), .IMAGE_MIRROR_EN(0)) camera_init1 (
        .Clk(clk_50m_internal), .Rst_n(locked), .Init_Done(init1),
        .camera_rst_n(), .i2c_sclk(camera1_sclk),
        .i2c_sdat(camera1_sdat)
    );
    camera_init #(.CAMERA_TYPE("ov5640"), .IMAGE_TYPE(0),
        .IMAGE_WIDTH(640), .IMAGE_HEIGHT(720),
        .IMAGE_FLIP_EN(1), .IMAGE_MIRROR_EN(0)) camera_init2 (
        .Clk(clk_50m_internal), .Rst_n(locked), .Init_Done(init2),
        .camera_rst_n(), .i2c_sclk(camera2_sclk),
        .i2c_sdat(camera2_sdat)
    );

    wire clear1, clear2, write1, write2;
    wire [7:0] data1, data2;
    Camera_ETH_Formator formator1 (
        .PCLK(camera1_pclk), .Rst_n(locked), .Init_Done(initialized),
        .HREF(camera1_href), .VSYNC(camera1_vsync), .DATA(camera1_data),
        .fifo_aclr(clear1), .wrdata(data1), .wrreq(write1)
    );
    Camera_ETH_Formator formator2 (
        .PCLK(camera2_pclk), .Rst_n(locked), .Init_Done(initialized),
        .HREF(camera2_href), .VSYNC(camera2_vsync), .DATA(camera2_data),
        .fifo_aclr(clear2), .wrdata(data2), .wrreq(write2)
    );

    wire line_write, line_clear;
    wire [7:0] line_byte;
    wire read1, read2;
    wire [7:0] cached1, cached2;
    wire [13:0] available1, available2;
    cache cache1 (
        .wrclk(camera1_pclk), .aclr(clear1), .wrreq(write1), .wrdata(data1),
        .rdclk(axis_clk), .rdreq(read1), .rddata(cached1), .rdusedw(available1)
    );
    cache cache2 (
        .wrclk(camera2_pclk), .aclr(clear2), .wrreq(write2), .wrdata(data2),
        .rdclk(axis_clk), .rdreq(read2), .rddata(cached2), .rdusedw(available2)
    );
    stereo_line_controller line_mux (
        .clk(axis_clk), .rst_n(axis_resetn && !clear1 && !clear2),
        .rdreq1(read1), .rddata1(cached1), .rdusedw1(available1),
        .rdreq2(read2), .rddata2(cached2), .rdusedw2(available2),
        .fifo_aclr(line_clear),
        .fifo_wrreq(line_write), .fifo_wrdata(line_byte)
    );

    reg [11:0] byte_pos;
    reg [7:0] line_lo, pixel_lo;
    reg [15:0] line_number;
    reg [15:0] expected_line;
    reg line_valid;
    reg [10:0] pixel_x;
    reg [17:0] fifo_input;
    reg fifo_write;
    wire [17:0] fifo_output;
    wire fifo_full, fifo_empty;
    wire fifo_reset = !axis_resetn || line_clear;

    // The vendor line mux can burst faster than S2MM accepts. One line-pair
    // buffer absorbs DDR stalls; overflow is exposed to the board driver.
    xpm_fifo_sync #(
        .FIFO_MEMORY_TYPE("block"), .FIFO_WRITE_DEPTH(8192),
        .WRITE_DATA_WIDTH(18), .READ_DATA_WIDTH(18),
        .READ_MODE("fwft"), .FIFO_READ_LATENCY(0),
        .FULL_RESET_VALUE(0), .USE_ADV_FEATURES("0000"),
        .DOUT_RESET_VALUE("0"), .WAKEUP_TIME(0)
    ) video_fifo (
        .rst(fifo_reset), .wr_clk(axis_clk),
        .din(fifo_input), .wr_en(fifo_write && !fifo_full),
        .full(fifo_full), .dout(fifo_output),
        .rd_en(m_axis_tready && !fifo_empty), .empty(fifo_empty),
        .sleep(1'b0), .injectsbiterr(1'b0), .injectdbiterr(1'b0)
    );
    assign m_axis_tvalid = !fifo_empty;
    assign m_axis_tdata = fifo_output[15:0];
    assign m_axis_tlast = fifo_output[16];
    assign m_axis_tuser = fifo_output[17];

    always @(posedge axis_clk) begin
        if (!axis_resetn || line_clear) begin
            byte_pos <= 0;
            line_lo <= 0;
            pixel_lo <= 0;
            line_number <= 0;
            expected_line <= 0;
            line_valid <= 0;
            pixel_x <= 0;
            fifo_input <= 0;
            fifo_write <= 0;
            overflow_count <= 0;
            source_frame_count <= 0;
        end else begin
            fifo_write <= 0;
            if (fifo_write && fifo_full)
                overflow_count <= overflow_count + 1'b1;
            if (line_write) begin
                if (byte_pos == 0) begin
                    line_lo <= line_byte;
                end else if (byte_pos == 1) begin
                    line_number <= {line_byte, line_lo};
                    line_valid <= ({line_byte, line_lo} < 720) &&
                        (({line_byte, line_lo} == expected_line) ||
                         ({line_byte, line_lo} == 0));
                    if ({line_byte, line_lo} == 0)
                        source_frame_count <= source_frame_count + 1'b1;
                    expected_line <= {line_byte, line_lo} + 1'b1;
                    pixel_x <= 0;
                end else if (!byte_pos[0]) begin
                    pixel_lo <= line_byte;
                end else if (line_valid) begin
                    fifo_input <= {(line_number == 0 && pixel_x == 0),
                                   (pixel_x == 1279), line_byte, pixel_lo};
                    fifo_write <= 1;
                    pixel_x <= pixel_x + 1'b1;
                end
                byte_pos <= (byte_pos == 2561) ? 0 : byte_pos + 1'b1;
            end
        end
    end
endmodule
