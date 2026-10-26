`timescale 1ns/1ps
// Sensor snapshot + ARM pose writeback + atomic 16-word AXI4-Stream packet.
module mpu6050_axi #(
    parameter integer CLK_HZ = 100000000,
    parameter integer I2C_HZ = 400000,
    parameter [6:0] DEVICE_ADDRESS = 7'h68,
    parameter integer STARTUP_US = 100000,
    parameter integer POLL_US = 250
)(
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi:m_axis, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 100000000" *)
    input wire s_axi_aclk,
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *) input wire s_axi_aresetn,
    input wire [7:0] s_axi_awaddr, input wire [2:0] s_axi_awprot,
    input wire s_axi_awvalid, output wire s_axi_awready,
    input wire [31:0] s_axi_wdata, input wire [3:0] s_axi_wstrb,
    input wire s_axi_wvalid, output wire s_axi_wready,
    output reg [1:0] s_axi_bresp, output reg s_axi_bvalid, input wire s_axi_bready,
    input wire [7:0] s_axi_araddr, input wire [2:0] s_axi_arprot,
    input wire s_axi_arvalid, output wire s_axi_arready,
    output reg [31:0] s_axi_rdata, output reg [1:0] s_axi_rresp,
    output reg s_axi_rvalid, input wire s_axi_rready,
    inout wire mpu_scl, inout wire mpu_sda,
    output wire [31:0] m_axis_tdata, output wire m_axis_tvalid,
    output wire m_axis_tlast, input wire m_axis_tready
);
    wire [111:0] sample;
    wire [63:0] timestamp_us;
    wire [63:0] live_timestamp_us;
    wire [31:0] sequence_number, error_count;
    wire initialized, sample_valid;
    reg aw_seen, w_seen;
    reg [7:0] write_address;
    reg [31:0] write_value;
    reg [3:0] write_strobe;
    reg [31:0] shadow [0:15];
    reg [31:0] packet [0:15];
    reg packet_busy;
    reg [3:0] packet_index;
    reg [31:0] packets_sent;
    reg diagnostic_request;
    reg [7:0] diagnostic_register, diagnostic_value;
    reg diagnostic_write;
    wire diagnostic_busy;
    wire [7:0] diagnostic_result;
    wire [31:0] diagnostic_count;
    integer i, byte_index;
    mpu6050_acquisition #(.CLK_HZ(CLK_HZ), .I2C_HZ(I2C_HZ),
        .DEVICE_ADDRESS(DEVICE_ADDRESS), .STARTUP_US(STARTUP_US), .POLL_US(POLL_US)) imu (
        .clk(s_axi_aclk), .resetn(s_axi_aresetn), .scl(mpu_scl), .sda(mpu_sda),
        .sample(sample), .timestamp_us(timestamp_us), .sequence_number(sequence_number),
        .initialized(initialized), .sample_valid(sample_valid), .error_count(error_count),
        .live_timestamp_us(live_timestamp_us),
        .diagnostic_request(diagnostic_request), .diagnostic_register(diagnostic_register),
        .diagnostic_write(diagnostic_write), .diagnostic_value(diagnostic_value),
        .diagnostic_busy(diagnostic_busy), .diagnostic_result(diagnostic_result),
        .diagnostic_count(diagnostic_count));
    assign s_axi_arready = !s_axi_rvalid;
    assign s_axi_awready = !aw_seen && !s_axi_bvalid;
    assign s_axi_wready = !w_seen && !s_axi_bvalid;
    assign m_axis_tdata = packet[packet_index];
    assign m_axis_tvalid = packet_busy;
    assign m_axis_tlast = packet_busy && packet_index == 15;
    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            s_axi_rvalid <= 0; s_axi_rdata <= 0; s_axi_rresp <= 0;
            s_axi_bvalid <= 0; s_axi_bresp <= 0; aw_seen <= 0; w_seen <= 0;
            write_address <= 0; write_value <= 0; write_strobe <= 0;
            packet_busy <= 0; packet_index <= 0; packets_sent <= 0;
            diagnostic_request <= 0; diagnostic_register <= 0;
            diagnostic_value <= 0; diagnostic_write <= 0;
            for (i=0; i<16; i=i+1) begin shadow[i] <= 0; packet[i] <= 0; end
        end else begin
            diagnostic_request <= 0;
            if (s_axi_rvalid && s_axi_rready) s_axi_rvalid <= 0;
            if (s_axi_arvalid && s_axi_arready) begin
                s_axi_rvalid <= 1; s_axi_rresp <= 0;
                if (s_axi_araddr[1:0] != 0) begin
                    s_axi_rdata <= 0; s_axi_rresp <= 2'b10;
                end else case (s_axi_araddr)
                    8'h00: s_axi_rdata <= 32'h4d505531; // MPU1 ABI
                    8'h04: s_axi_rdata <= {30'b0, initialized, sample_valid};
                    8'h08: s_axi_rdata <= sequence_number;
                    8'h0c: s_axi_rdata <= timestamp_us[31:0];
                    8'h10: s_axi_rdata <= timestamp_us[63:32];
                    8'h14: s_axi_rdata <= {{16{sample[111]}}, sample[111:96]};
                    8'h18: s_axi_rdata <= {{16{sample[95]}}, sample[95:80]};
                    8'h1c: s_axi_rdata <= {{16{sample[79]}}, sample[79:64]};
                    8'h20: s_axi_rdata <= {{16{sample[47]}}, sample[47:32]};
                    8'h24: s_axi_rdata <= {{16{sample[31]}}, sample[31:16]};
                    8'h28: s_axi_rdata <= {{16{sample[15]}}, sample[15:0]};
                    8'h2c: s_axi_rdata <= {{16{sample[63]}}, sample[63:48]};
                    8'h30: s_axi_rdata <= error_count;
                    8'h34: s_axi_rdata <= 500;
                    8'h38: s_axi_rdata <= live_timestamp_us[31:0];
                    8'h3c: s_axi_rdata <= live_timestamp_us[63:32];
                    8'h80: s_axi_rdata <= {31'b0, packet_busy};
                    8'h84: s_axi_rdata <= packets_sent;
                    8'h90: s_axi_rdata <= {31'b0, diagnostic_busy};
                    8'h94: s_axi_rdata <= {24'b0, diagnostic_result};
                    8'h98: s_axi_rdata <= diagnostic_count;
                    default: if (s_axi_araddr >= 8'hc0) s_axi_rdata <= packet[s_axi_araddr[5:2]];
                             else begin s_axi_rdata <= 0; s_axi_rresp <= 2'b10; end
                endcase
            end
            if (s_axi_awvalid && s_axi_awready) begin aw_seen <= 1; write_address <= s_axi_awaddr; end
            if (s_axi_wvalid && s_axi_wready) begin
                w_seen <= 1; write_value <= s_axi_wdata; write_strobe <= s_axi_wstrb;
            end
            if (aw_seen && w_seen && !s_axi_bvalid) begin
                s_axi_bvalid <= 1; aw_seen <= 0; w_seen <= 0;
                s_axi_bresp <= 0;
                if (write_address[1:0] != 0) s_axi_bresp <= 2'b10;
                else if (write_address >= 8'h40 && write_address < 8'h80) begin
                    for (byte_index=0; byte_index<4; byte_index=byte_index+1)
                        if (write_strobe[byte_index])
                            shadow[write_address[5:2]][8*byte_index+:8] <= write_value[8*byte_index+:8];
                end else if (write_address == 8'h90 && write_strobe == 4'hf
                             && write_value[0] && !diagnostic_busy && !diagnostic_request) begin
                    diagnostic_register <= write_value[15:8]; diagnostic_value <= write_value[23:16];
                    diagnostic_write <= write_value[1]; diagnostic_request <= 1;
                end else if (write_address == 8'h80 && write_strobe == 4'hf && write_value == 1
                             && !packet_busy && shadow[0] == 32'h494d5531
                             && shadow[1][31:16] == 1 && shadow[1][0]) begin
                    for (i=0; i<16; i=i+1) packet[i] <= shadow[i];
                    packet_busy <= 1; packet_index <= 0;
                end else s_axi_bresp <= 2'b10;
            end
            if (s_axi_bvalid && s_axi_bready) s_axi_bvalid <= 0;
            if (packet_busy && m_axis_tready) begin
                if (packet_index == 15) begin
                    packet_busy <= 0; packet_index <= 0; packets_sent <= packets_sent+1;
                end else packet_index <= packet_index+1;
            end
        end
    end
endmodule
