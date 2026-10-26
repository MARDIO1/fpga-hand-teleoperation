`timescale 1ns/1ps
module mpu6050_acquisition #(
    parameter integer CLK_HZ = 100000000,
    parameter integer I2C_HZ = 400000,
    parameter [6:0] DEVICE_ADDRESS = 7'h68,
    parameter integer STARTUP_US = 100000,
    parameter integer POLL_US = 250
)(
    input wire clk, input wire resetn,
    inout wire scl, inout wire sda,
    output reg [111:0] sample,
    output reg [63:0] timestamp_us,
    output reg [31:0] sequence_number,
    output reg initialized, output reg sample_valid,
    output reg [31:0] error_count,
    output wire [63:0] live_timestamp_us,
    input wire diagnostic_request, input wire [7:0] diagnostic_register,
    input wire diagnostic_write, input wire [7:0] diagnostic_value,
    output wire diagnostic_busy, output reg [7:0] diagnostic_result,
    output reg [31:0] diagnostic_count
);
    localparam WAIT_POWER=0, LAUNCH=1, WAIT_TRANSFER=2, POLL_WAIT=3;
    reg [1:0] state;
    reg [3:0] operation;
    reg [31:0] wait_us, us_divider;
    reg [63:0] clock_us, pending_timestamp;
    assign live_timestamp_us = clock_us;
    reg start;
    reg [7:0] register_address, write_data;
    reg [4:0] read_count;
    wire busy, done, error;
    wire [111:0] read_data;
    reg diagnostic_pending, diagnostic_is_write;
    reg [7:0] diagnostic_address, diagnostic_data;
    assign diagnostic_busy = diagnostic_pending || operation == 12;
    i2c_register_master #(.CLK_HZ(CLK_HZ), .I2C_HZ(I2C_HZ)) bus (
        .clk(clk), .resetn(resetn), .start(start), .address(DEVICE_ADDRESS),
        .register_address(register_address), .write_data(write_data),
        .read_count(read_count), .busy(busy), .done(done), .error(error),
        .read_data(read_data), .scl(scl), .sda(sda));
    always @* begin
        register_address = 0; write_data = 0; read_count = 0;
        case (operation)
            0: begin register_address=8'h6b; write_data=8'h80; end // reset
            1: begin register_address=8'h75; read_count=1; end // WHO_AM_I
            2: begin register_address=8'h6b; write_data=8'h01; end // PLL X gyro
            3: begin register_address=8'h6c; write_data=0; end
            4: begin register_address=8'h1a; write_data=2; end // DLPF ~98 Hz
            5: begin register_address=8'h19; write_data=1; end // 500 Hz
            6: begin register_address=8'h1b; write_data=8'h08; end // +/-500 dps
            7: begin register_address=8'h1c; write_data=8'h08; end // +/-4 g
            8: begin register_address=8'h37; write_data=0; end // clear only INT_STATUS
            9: begin register_address=8'h38; write_data=1; end // data ready
            10: begin register_address=8'h3a; read_count=1; end
            11: begin register_address=8'h3b; read_count=14; end
            12: begin register_address=diagnostic_address; write_data=diagnostic_data;
                      read_count=diagnostic_is_write ? 0 : 1; end
            13: begin register_address=8'h6b; write_data=8'h01; end
            14: begin register_address=8'h6b; read_count=1; end
        endcase
    end
    always @(posedge clk) begin
        if (!resetn) begin
            state <= WAIT_POWER; operation <= 0; wait_us <= 0;
            us_divider <= 0; clock_us <= 0; pending_timestamp <= 0;
            start <= 0; sample <= 0; timestamp_us <= 0; sequence_number <= 0;
            initialized <= 0; sample_valid <= 0; error_count <= 0;
            diagnostic_pending <= 0; diagnostic_is_write <= 0;
            diagnostic_address <= 0; diagnostic_data <= 0;
            diagnostic_result <= 0; diagnostic_count <= 0;
        end else begin
            start <= 0;
            if (diagnostic_request && !diagnostic_busy) begin
                diagnostic_pending <= 1; diagnostic_address <= diagnostic_register;
                diagnostic_is_write <= diagnostic_write; diagnostic_data <= diagnostic_value;
            end
            if (us_divider == CLK_HZ/1000000-1) begin
                us_divider <= 0; clock_us <= clock_us+1;
                if (wait_us != 32'hffffffff) wait_us <= wait_us+1;
            end else us_divider <= us_divider+1;
            case (state)
                WAIT_POWER: if (wait_us >= STARTUP_US) begin
                    wait_us <= 0; state <= LAUNCH;
                end
                LAUNCH: if (!busy) begin
                    start <= 1; state <= WAIT_TRANSFER;
                    if (operation == 11) pending_timestamp <= clock_us;
                end
                WAIT_TRANSFER: if (done) begin
                    if (operation == 12) begin
                        diagnostic_result <= read_data[7:0];
                        diagnostic_count <= diagnostic_count+1;
                    end
                    if (error || (operation == 1 && read_data[7:0] != 8'h68)
                              || (operation == 14 && read_data[7:0] != 8'h01)) begin
                        initialized <= 0; sample_valid <= 0;
                        error_count <= error_count+1;
                        operation <= 0; wait_us <= 0; state <= WAIT_POWER;
                    end else if (operation == 0) begin
                        operation <= 1; wait_us <= 0; state <= WAIT_POWER;
                    end else if (operation == 2) begin
                        // Real module retained SLEEP on the first PLL write after reset.
                        operation <= 13; wait_us <= 0; state <= WAIT_POWER;
                    end else if (operation == 13) begin
                        operation <= 14; state <= LAUNCH;
                    end else if (operation == 14) begin
                        operation <= 3; state <= LAUNCH;
                    end else if (operation < 9) begin
                        operation <= operation+1; state <= LAUNCH;
                    end else if (operation == 9) begin
                        initialized <= 1; operation <= 10;
                        wait_us <= 0; state <= POLL_WAIT;
                    end else if (operation == 10) begin
                        if (read_data[0]) begin operation <= 11; state <= LAUNCH; end
                        else begin wait_us <= 0; state <= POLL_WAIT; end
                    end else if (operation == 12) begin
                        operation <= 10; wait_us <= 0; state <= POLL_WAIT;
                    end else begin
                        sample <= read_data; timestamp_us <= pending_timestamp;
                        sequence_number <= sequence_number+1; sample_valid <= 1;
                        operation <= 10; wait_us <= 0; state <= POLL_WAIT;
                    end
                end
                POLL_WAIT: if (diagnostic_pending) begin
                    diagnostic_pending <= 0; operation <= 12; state <= LAUNCH;
                end else if (wait_us >= POLL_US) state <= LAUNCH;
            endcase
        end
    end
endmodule
