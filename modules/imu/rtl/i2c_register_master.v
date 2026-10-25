`timescale 1ns/1ps
// Single-master, open-drain register write / repeated-START burst read.
module i2c_register_master #(
    parameter integer CLK_HZ = 100000000,
    parameter integer I2C_HZ = 400000,
    parameter integer TIMEOUT_US = 5000
)(
    input wire clk, input wire resetn,
    input wire start, input wire [6:0] address,
    input wire [7:0] register_address, input wire [7:0] write_data,
    input wire [4:0] read_count, // 0 = write, 1..14 = read
    output reg busy, output reg done, output reg error,
    output reg [111:0] read_data,
    inout wire scl, inout wire sda
);
    localparam integer DIV_RATE = (CLK_HZ + I2C_HZ*5-1) / (I2C_HZ * 5);
    // Meet fast-mode tLOW >=1.3 us and START hold >=0.6 us.
    // Standard-mode START hold needs >=4 us per controller tick.
    localparam integer DIV_MIN = ((CLK_HZ/1000000) * (I2C_HZ <= 100000 ? 80 : 13) + 19) / 20;
    localparam integer DIV = DIV_RATE > DIV_MIN ? DIV_RATE : DIV_MIN;
    localparam integer TIMEOUT_CYCLES = (CLK_HZ / 1000000) * TIMEOUT_US;
    localparam IDLE=0, START_WAIT=1, START_LOW=2, TX_SETUP=3,
        TX_RISE=4, TX_HIGH=5, TX_FALL=6, ACK_SETUP=7,
        ACK_RISE=8, ACK_HIGH=9, ACK_FALL=10, RESTART_LOW=11,
        RESTART_RISE=12, RESTART_HIGH=13, RX_SETUP=14,
        RX_RISE=15, RX_HIGH=16, RX_FALL=17, MACK_SETUP=18,
        MACK_RISE=19, MACK_HIGH=20, MACK_FALL=21,
        STOP_LOW=22, STOP_RISE=23, STOP_HIGH=24, STOP_DONE=25;
    reg [4:0] state;
    reg scl_low, sda_low;
    (* ASYNC_REG = "TRUE" *) reg [1:0] scl_sync, sda_sync;
    reg [31:0] divider, watchdog;
    reg [7:0] tx, reg_addr, wr_data;
    reg [6:0] dev_addr;
    reg [4:0] count, rx_index;
    reg [2:0] bit_index;
    reg [1:0] stage;
    wire scl_in, sda_in;
    // Explicit buffers survive Vivado's out-of-context module-reference synthesis.
    IOBUF scl_buffer (.I(1'b0), .T(!scl_low), .O(scl_in), .IO(scl));
    IOBUF sda_buffer (.I(1'b0), .T(!sda_low), .O(sda_in), .IO(sda));
    always @(posedge clk) begin
        if (!resetn) begin
            scl_sync <= 2'b11; sda_sync <= 2'b11;
        end else begin
            scl_sync <= {scl_sync[0], scl_in};
            sda_sync <= {sda_sync[0], sda_in};
        end
    end
    always @(posedge clk) begin
        if (!resetn) begin
            state <= IDLE; scl_low <= 0; sda_low <= 0;
            divider <= 0; watchdog <= 0;
            busy <= 0; done <= 0; error <= 0; read_data <= 0;
            tx <= 0; reg_addr <= 0; wr_data <= 0; dev_addr <= 0;
            count <= 0; rx_index <= 0; bit_index <= 0; stage <= 0;
        end else begin
            done <= 0;
            if (!busy) begin
                divider <= 0; watchdog <= 0;
                if (start) begin
                    busy <= 1; error <= 0; read_data <= 0;
                    dev_addr <= address; reg_addr <= register_address;
                    wr_data <= write_data; count <= read_count;
                    rx_index <= 0; stage <= 0; bit_index <= 7;
                    tx <= {address, 1'b0}; state <= START_WAIT;
                end
            end else if (watchdog == TIMEOUT_CYCLES-1) begin
                // Release a stuck bus; the acquisition controller retries after reset.
                scl_low <= 0; sda_low <= 0;
                busy <= 0; done <= 1; error <= 1; state <= IDLE;
            end else begin
                watchdog <= watchdog + 1;
                if (divider == DIV-1) begin
                    divider <= 0;
                    case (state)
                        START_WAIT: if (scl_sync[1] && sda_sync[1]) begin
                            sda_low <= 1; state <= START_LOW;
                        end
                        START_LOW: begin scl_low <= 1; state <= TX_SETUP; end
                        TX_SETUP: begin sda_low <= !tx[bit_index]; state <= TX_RISE; end
                        TX_RISE: begin scl_low <= 0; if (scl_sync[1]) state <= TX_HIGH; end
                        TX_HIGH: state <= TX_FALL;
                        TX_FALL: begin
                            scl_low <= 1;
                            if (bit_index == 0) state <= ACK_SETUP;
                            else begin bit_index <= bit_index-1; state <= TX_SETUP; end
                        end
                        ACK_SETUP: begin sda_low <= 0; state <= ACK_RISE; end
                        ACK_RISE: begin scl_low <= 0; if (scl_sync[1]) state <= ACK_HIGH; end
                        ACK_HIGH: begin
                            if (sda_sync[1]) error <= 1;
                            state <= ACK_FALL;
                        end
                        ACK_FALL: begin
                            scl_low <= 1; bit_index <= 7;
                            if (error) state <= STOP_LOW;
                            else case (stage)
                                0: begin tx <= reg_addr; stage <= 1; state <= TX_SETUP; end
                                1: if (count != 0) state <= RESTART_LOW;
                                   else begin tx <= wr_data; stage <= 2; state <= TX_SETUP; end
                                2: state <= STOP_LOW;
                                3: state <= RX_SETUP;
                            endcase
                        end
                        RESTART_LOW: begin sda_low <= 0; state <= RESTART_RISE; end
                        RESTART_RISE: begin scl_low <= 0; if (scl_sync[1]) state <= RESTART_HIGH; end
                        RESTART_HIGH: begin
                            sda_low <= 1; tx <= {dev_addr, 1'b1};
                            stage <= 3; state <= START_LOW;
                        end
                        RX_SETUP: begin sda_low <= 0; state <= RX_RISE; end
                        RX_RISE: begin scl_low <= 0; if (scl_sync[1]) state <= RX_HIGH; end
                        RX_HIGH: begin
                            read_data <= {read_data[110:0], sda_sync[1]};
                            state <= RX_FALL;
                        end
                        RX_FALL: begin
                            scl_low <= 1;
                            if (bit_index == 0) state <= MACK_SETUP;
                            else begin bit_index <= bit_index-1; state <= RX_SETUP; end
                        end
                        MACK_SETUP: begin sda_low <= (rx_index+1 < count); state <= MACK_RISE; end
                        MACK_RISE: begin scl_low <= 0; if (scl_sync[1]) state <= MACK_HIGH; end
                        MACK_HIGH: state <= MACK_FALL;
                        MACK_FALL: begin
                            scl_low <= 1; bit_index <= 7;
                            if (rx_index+1 == count) state <= STOP_LOW;
                            else begin rx_index <= rx_index+1; state <= RX_SETUP; end
                        end
                        STOP_LOW: begin sda_low <= 1; state <= STOP_RISE; end
                        STOP_RISE: begin scl_low <= 0; if (scl_sync[1]) state <= STOP_HIGH; end
                        STOP_HIGH: begin sda_low <= 0; state <= STOP_DONE; end
                        STOP_DONE: begin busy <= 0; done <= 1; state <= IDLE; end
                        default: begin state <= IDLE; busy <= 0; error <= 1; done <= 1; end
                    endcase
                end else divider <= divider + 1;
            end
        end
    end
endmodule
