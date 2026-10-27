`timescale 1ns / 1ps

module tb_stream_chain;
    reg clk = 0;
    always #5 clk = !clk;
    reg resetn = 0;
    reg [15:0] camera_data = 0;
    reg camera_valid = 0, camera_user = 0, camera_last = 0;
    wire camera_ready;
    wire [15:0] video_data, pair_data;
    wire video_valid, video_user, video_last;
    wire pair_valid, pair_ready, pair_user;
    wire [7:0] depth_data;
    wire depth_valid, depth_user, depth_last;
    wire [31:0] drops;
    integer x, y, pair_count = 0, depth_count = 0, last_count = 0;
    stereo_stream_preproc preproc (
        .clk(clk), .resetn(resetn),
        .s_axis_tdata(camera_data), .s_axis_tvalid(camera_valid),
        .s_axis_tready(camera_ready), .s_axis_tuser(camera_user),
        .s_axis_tlast(camera_last), .m_axis_tdata(video_data),
        .m_axis_tvalid(video_valid), .m_axis_tready(1'b1),
        .m_axis_tuser(video_user), .m_axis_tlast(video_last),
        .pair_tdata(pair_data), .pair_tvalid(pair_valid),
        .pair_tready(pair_ready), .pair_tuser(pair_user),
        .dropped_pairs(drops)
    );
    stereo_sad #(.LANES(8)) sad (
        .clk(clk), .resetn(resetn), .s_tdata(pair_data),
        .s_tvalid(pair_valid), .s_tready(pair_ready), .s_tuser(pair_user),
        .m_tdata(depth_data), .m_tvalid(depth_valid),
        .m_tready(1'b1), .m_tuser(depth_user), .m_tlast(depth_last)
    );
    always @(posedge clk) if (resetn) begin
        if (pair_valid && pair_ready) pair_count = pair_count + 1;
        if (depth_valid) begin
            depth_count = depth_count + 1;
            if (depth_last) last_count = last_count + 1;
        end
    end
    initial begin
        repeat (5) @(negedge clk);
        resetn = 1;
        // The second frame deliberately omits TUSER to exercise line-count
        // recovery after a dropped camera SOF marker.
        for (y = 0; y < 1440; y = y + 1)
            for (x = 0; x < 1280; x = x + 1) begin
                @(negedge clk);
                camera_valid = 1;
                camera_data = x < 640 ? 16'hf800 : 16'h001f;
                camera_user = x == 0 && y == 0;
                camera_last = x == 1279;
            end
        @(negedge clk);
        camera_valid = 0;
        repeat (10000) @(negedge clk);
        $display("pairs=%0d disparity=%0d frames=%0d drops=%0d",
                 pair_count, depth_count, last_count, drops);
        if (pair_count != 57600 || depth_count != 57600 ||
            last_count != 2 || drops[23:0] != 57600 || drops[31:24] != 0)
            $fatal(1, "incomplete stream frame");
        $display("PASS: two camera frames, second SOF recovered from line count");
        $finish;
    end
endmodule
