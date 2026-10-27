`timescale 1ns / 1ps

// Configurable RGB565 AXI4-Stream Video OSD.
// LABEL_LATENCY=0: "FPS:ddd RES:ddddXdddd"
// LABEL_LATENCY=1: "LAT:dddMS RES:ddddXdddd"
// LABEL_LATENCY=2: "PROC:ddd HDMI:ddd" (cfg_resolution[11:0] is HDMI Hz BCD)
module axis_osd_rgb565 #(
    parameter integer LABEL_LATENCY = 0
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 aclk CLK",
       X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF S_AXIS:M_AXIS, ASSOCIATED_RESET aresetn" *)
    input  wire        aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST",
       X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire        aresetn,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TDATA" *)
    input  wire [15:0] s_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TUSER" *)
    input  wire [0:0]  s_axis_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TLAST" *)
    input  wire        s_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TVALID" *)
    input  wire        s_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS TREADY" *)
    output wire        s_axis_tready,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TDATA" *)
    output wire [15:0] m_axis_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TUSER" *)
    output wire [0:0]  m_axis_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TLAST" *)
    output wire        m_axis_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TVALID" *)
    output wire        m_axis_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS TREADY" *)
    input  wire        m_axis_tready,

    // {height_bcd[15:0], width_bcd[15:0]}, four packed BCD digits each.
    input  wire [31:0] cfg_resolution,
    // bit 31: enable; bits 11:0: three packed BCD latency-ms digits.
    input  wire [31:0] cfg_control
);

    localparam [15:0] TEXT_X = 16;
    localparam [15:0] TEXT_Y = 16;
    localparam [15:0] TEXT_END_X = LABEL_LATENCY == 2 ? 152 :
                                  (LABEL_LATENCY ? 200 : 184);
    localparam [15:0] TEXT_END_Y = 24;
    localparam [15:0] BG_X = 8;
    localparam [15:0] BG_Y = 8;
    localparam [15:0] BG_END_X = LABEL_LATENCY == 2 ? 160 :
                                (LABEL_LATENCY ? 208 : 192);
    localparam [15:0] BG_END_Y = 32;

    reg [15:0] pixel_x;
    reg [15:0] pixel_y;
    reg [15:0] output_data;
    reg [0:0]  output_user;
    reg        output_last;
    reg        output_valid;
    wire transfer = s_axis_tvalid && s_axis_tready;
    wire [15:0] cur_x = s_axis_tuser[0] ? 16'd0 : pixel_x;
    wire [15:0] cur_y = s_axis_tuser[0] ? 16'd0 : pixel_y;
    wire osd_enable = cfg_control[31];
    wire [11:0] cfg_latency_bcd = cfg_control[11:0];
    wire [15:0] cfg_width_bcd = cfg_resolution[15:0];
    wire [15:0] cfg_height_bcd = cfg_resolution[31:16];

    wire in_background = osd_enable && cur_x >= BG_X && cur_x < BG_END_X &&
                         cur_y >= BG_Y && cur_y < BG_END_Y;
    wire in_text = osd_enable && cur_x >= TEXT_X && cur_x < TEXT_END_X &&
                   cur_y >= TEXT_Y && cur_y < TEXT_END_Y;
    wire [5:0] char_index = (cur_x - TEXT_X) >> 3;
    wire [2:0] glyph_column = (cur_x - TEXT_X) & 3'h7;
    wire [2:0] glyph_row_index = (cur_y - TEXT_Y) & 3'h7;
    wire [7:0] glyph_character = text_character(char_index, cfg_latency_bcd,
                                                cfg_width_bcd, cfg_height_bcd);
    wire [7:0] glyph_bits = font_row(glyph_character, glyph_row_index);
    wire glyph_pixel = in_text && glyph_bits[7 - glyph_column];
    wire [15:0] overlay_data = glyph_pixel ? 16'hffff :
                               (in_background ? 16'h0000 : s_axis_tdata);

    // One-deep elastic AXI4-Stream output register. This preserves full
    // throughput and backpressure while cutting the dynamic text/font path.
    assign s_axis_tready = !output_valid || m_axis_tready;
    assign m_axis_tvalid = output_valid;
    assign m_axis_tuser  = output_user;
    assign m_axis_tlast  = output_last;
    assign m_axis_tdata  = output_data;

    always @(posedge aclk) begin
        if (!aresetn) begin
            output_valid <= 1'b0;
            output_data  <= 16'd0;
            output_user  <= 1'b0;
            output_last  <= 1'b0;
        end else if (s_axis_tready) begin
            output_valid <= s_axis_tvalid;
            if (s_axis_tvalid) begin
                output_data <= overlay_data;
                output_user <= s_axis_tuser;
                output_last <= s_axis_tlast;
            end
        end
    end

    always @(posedge aclk) begin
        if (!aresetn) begin
            pixel_x <= 16'd0;
            pixel_y <= 16'd0;
        end else if (transfer) begin
            if (s_axis_tuser[0]) begin
                if (s_axis_tlast) begin
                    pixel_x <= 16'd0;
                    pixel_y <= 16'd1;
                end else begin
                    pixel_x <= 16'd1;
                    pixel_y <= 16'd0;
                end
            end else if (s_axis_tlast) begin
                pixel_x <= 16'd0;
                pixel_y <= pixel_y + 1'b1;
            end else begin
                pixel_x <= pixel_x + 1'b1;
            end
        end
    end

    function [7:0] text_character;
        input [5:0] index;
        input [11:0] latency_bcd;
        input [15:0] width_bcd;
        input [15:0] height_bcd;
        begin
            if (LABEL_LATENCY == 2) begin
                case (index)
                    0: text_character = "P";
                    1: text_character = "R";
                    2: text_character = "O";
                    3: text_character = "C";
                    4: text_character = ":";
                    5: text_character = 8'h30 + latency_bcd[11:8];
                    6: text_character = 8'h30 + latency_bcd[7:4];
                    7: text_character = 8'h30 + latency_bcd[3:0];
                    8: text_character = " ";
                    9: text_character = "H";
                    10: text_character = "D";
                    11: text_character = "M";
                    12: text_character = "I";
                    13: text_character = ":";
                    14: text_character = 8'h30 + width_bcd[11:8];
                    15: text_character = 8'h30 + width_bcd[7:4];
                    16: text_character = 8'h30 + width_bcd[3:0];
                    default: text_character = " ";
                endcase
            end else if (LABEL_LATENCY) begin
                case (index)
                    0: text_character = "L";
                    1: text_character = "A";
                    2: text_character = "T";
                    3: text_character = ":";
                    4: text_character = 8'h30 + latency_bcd[11:8];
                    5: text_character = 8'h30 + latency_bcd[7:4];
                    6: text_character = 8'h30 + latency_bcd[3:0];
                    7: text_character = "M";
                    8: text_character = "S";
                    9: text_character = " ";
                    10: text_character = "R";
                    11: text_character = "E";
                    12: text_character = "S";
                    13: text_character = ":";
                    14: text_character = 8'h30 + width_bcd[15:12];
                    15: text_character = 8'h30 + width_bcd[11:8];
                    16: text_character = 8'h30 + width_bcd[7:4];
                    17: text_character = 8'h30 + width_bcd[3:0];
                    18: text_character = "X";
                    19: text_character = 8'h30 + height_bcd[15:12];
                    20: text_character = 8'h30 + height_bcd[11:8];
                    21: text_character = 8'h30 + height_bcd[7:4];
                    22: text_character = 8'h30 + height_bcd[3:0];
                    default: text_character = " ";
                endcase
            end else begin
                case (index)
                    0: text_character = "F";
                    1: text_character = "P";
                    2: text_character = "S";
                    3: text_character = ":";
                    4: text_character = 8'h30 + latency_bcd[11:8];
                    5: text_character = 8'h30 + latency_bcd[7:4];
                    6: text_character = 8'h30 + latency_bcd[3:0];
                    7: text_character = " ";
                    8: text_character = "R";
                    9: text_character = "E";
                    10: text_character = "S";
                    11: text_character = ":";
                    12: text_character = 8'h30 + width_bcd[15:12];
                    13: text_character = 8'h30 + width_bcd[11:8];
                    14: text_character = 8'h30 + width_bcd[7:4];
                    15: text_character = 8'h30 + width_bcd[3:0];
                    16: text_character = "X";
                    17: text_character = 8'h30 + height_bcd[15:12];
                    18: text_character = 8'h30 + height_bcd[11:8];
                    19: text_character = 8'h30 + height_bcd[7:4];
                    20: text_character = 8'h30 + height_bcd[3:0];
                    default: text_character = " ";
                endcase
            end
        end
    endfunction

    function [7:0] font_row;
        input [7:0] character;
        input [2:0] row;
        begin
            font_row = 8'h00;
            case (character)
                "0": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h66; 2: font_row=8'h6e;
                    3: font_row=8'h76; 4: font_row=8'h66; 5: font_row=8'h66;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "1": case (row)
                    0: font_row=8'h18; 1: font_row=8'h38; 2: font_row=8'h18;
                    3: font_row=8'h18; 4: font_row=8'h18; 5: font_row=8'h18;
                    6: font_row=8'h7e; default: font_row=8'h00; endcase
                "2": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h66; 2: font_row=8'h06;
                    3: font_row=8'h0c; 4: font_row=8'h30; 5: font_row=8'h60;
                    6: font_row=8'h7e; default: font_row=8'h00; endcase
                "3": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h66; 2: font_row=8'h06;
                    3: font_row=8'h1c; 4: font_row=8'h06; 5: font_row=8'h66;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "4": case (row)
                    0: font_row=8'h0c; 1: font_row=8'h1c; 2: font_row=8'h3c;
                    3: font_row=8'h6c; 4: font_row=8'h7e; 5: font_row=8'h0c;
                    6: font_row=8'h0c; default: font_row=8'h00; endcase
                "5": case (row)
                    0: font_row=8'h7e; 1: font_row=8'h60; 2: font_row=8'h7c;
                    3: font_row=8'h06; 4: font_row=8'h06; 5: font_row=8'h66;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "6": case (row)
                    0: font_row=8'h1c; 1: font_row=8'h30; 2: font_row=8'h60;
                    3: font_row=8'h7c; 4: font_row=8'h66; 5: font_row=8'h66;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "7": case (row)
                    0: font_row=8'h7e; 1: font_row=8'h66; 2: font_row=8'h0c;
                    3: font_row=8'h18; 4: font_row=8'h18; 5: font_row=8'h18;
                    6: font_row=8'h18; default: font_row=8'h00; endcase
                "8": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h66; 2: font_row=8'h66;
                    3: font_row=8'h3c; 4: font_row=8'h66; 5: font_row=8'h66;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "9": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h66; 2: font_row=8'h66;
                    3: font_row=8'h3e; 4: font_row=8'h06; 5: font_row=8'h0c;
                    6: font_row=8'h38; default: font_row=8'h00; endcase
                "A": case (row)
                    0: font_row=8'h18; 1: font_row=8'h3c; 2: font_row=8'h66;
                    3: font_row=8'h66; 4: font_row=8'h7e; 5: font_row=8'h66;
                    6: font_row=8'h66; default: font_row=8'h00; endcase
                "C": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h66; 2: font_row=8'h60;
                    3: font_row=8'h60; 4: font_row=8'h60; 5: font_row=8'h66;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "D": case (row)
                    0: font_row=8'h78; 1: font_row=8'h6c; 2: font_row=8'h66;
                    3: font_row=8'h66; 4: font_row=8'h66; 5: font_row=8'h6c;
                    6: font_row=8'h78; default: font_row=8'h00; endcase
                "F": case (row)
                    0: font_row=8'h7e; 1: font_row=8'h60; 2: font_row=8'h60;
                    3: font_row=8'h7c; 4: font_row=8'h60; 5: font_row=8'h60;
                    6: font_row=8'h60; default: font_row=8'h00; endcase
                "H": case (row)
                    0: font_row=8'h66; 1: font_row=8'h66; 2: font_row=8'h66;
                    3: font_row=8'h7e; 4: font_row=8'h66; 5: font_row=8'h66;
                    6: font_row=8'h66; default: font_row=8'h00; endcase
                "I": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h18; 2: font_row=8'h18;
                    3: font_row=8'h18; 4: font_row=8'h18; 5: font_row=8'h18;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "L": case (row)
                    0: font_row=8'h60; 1: font_row=8'h60; 2: font_row=8'h60;
                    3: font_row=8'h60; 4: font_row=8'h60; 5: font_row=8'h60;
                    6: font_row=8'h7e; default: font_row=8'h00; endcase
                "M": case (row)
                    0: font_row=8'h63; 1: font_row=8'h77; 2: font_row=8'h7f;
                    3: font_row=8'h6b; 4: font_row=8'h63; 5: font_row=8'h63;
                    6: font_row=8'h63; default: font_row=8'h00; endcase
                "O": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h66; 2: font_row=8'h66;
                    3: font_row=8'h66; 4: font_row=8'h66; 5: font_row=8'h66;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "P": case (row)
                    0: font_row=8'h7c; 1: font_row=8'h66; 2: font_row=8'h66;
                    3: font_row=8'h7c; 4: font_row=8'h60; 5: font_row=8'h60;
                    6: font_row=8'h60; default: font_row=8'h00; endcase
                "S": case (row)
                    0: font_row=8'h3c; 1: font_row=8'h66; 2: font_row=8'h60;
                    3: font_row=8'h3c; 4: font_row=8'h06; 5: font_row=8'h66;
                    6: font_row=8'h3c; default: font_row=8'h00; endcase
                "T": case (row)
                    0: font_row=8'h7e; 1: font_row=8'h18; 2: font_row=8'h18;
                    3: font_row=8'h18; 4: font_row=8'h18; 5: font_row=8'h18;
                    6: font_row=8'h18; default: font_row=8'h00; endcase
                "R": case (row)
                    0: font_row=8'h7c; 1: font_row=8'h66; 2: font_row=8'h66;
                    3: font_row=8'h7c; 4: font_row=8'h6c; 5: font_row=8'h66;
                    6: font_row=8'h66; default: font_row=8'h00; endcase
                "E": case (row)
                    0: font_row=8'h7e; 1: font_row=8'h60; 2: font_row=8'h60;
                    3: font_row=8'h7c; 4: font_row=8'h60; 5: font_row=8'h60;
                    6: font_row=8'h7e; default: font_row=8'h00; endcase
                "X": case (row)
                    0: font_row=8'h66; 1: font_row=8'h66; 2: font_row=8'h3c;
                    3: font_row=8'h18; 4: font_row=8'h3c; 5: font_row=8'h66;
                    6: font_row=8'h66; default: font_row=8'h00; endcase
                ":": case (row)
                    1: font_row=8'h18; 2: font_row=8'h18;
                    4: font_row=8'h18; 5: font_row=8'h18;
                    default: font_row=8'h00; endcase
                default: font_row=8'h00;
            endcase
        end
    endfunction
endmodule
