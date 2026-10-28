`timescale 1ns / 1ps

// Integration diagnostic: count raw VSYNC rising edges from each camera.
module camera_frame_probe (
    input  wire        resetn,
    input  wire        camera1_pclk,
    input  wire        camera1_vsync,
    input  wire        camera2_pclk,
    input  wire        camera2_vsync,
    output reg  [31:0] camera1_frames,
    output reg  [31:0] camera2_frames
);
    reg camera1_vsync_d;
    reg camera2_vsync_d;

    always @(posedge camera1_pclk or negedge resetn) begin
        if (!resetn) begin
            camera1_vsync_d <= 1'b0;
            camera1_frames <= 32'd0;
        end else begin
            camera1_vsync_d <= camera1_vsync;
            if (camera1_vsync && !camera1_vsync_d)
                camera1_frames <= camera1_frames + 1'b1;
        end
    end

    always @(posedge camera2_pclk or negedge resetn) begin
        if (!resetn) begin
            camera2_vsync_d <= 1'b0;
            camera2_frames <= 32'd0;
        end else begin
            camera2_vsync_d <= camera2_vsync;
            if (camera2_vsync && !camera2_vsync_d)
                camera2_frames <= camera2_frames + 1'b1;
        end
    end
endmodule
