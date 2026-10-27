// Generated from dual_camera_udp/metric_scale.npz.
function automatic [15:0] depth_color(input [7:0] disparity);
    begin
        case (disparity)
            8'd7: depth_color = 16'h39b1;
            8'd8: depth_color = 16'h1e5b;
            8'd9: depth_color = 16'h5fed;
            8'd10: depth_color = 16'hb7c6;
            8'd11: depth_color = 16'he6c7;
            8'd12: depth_color = 16'hfde7;
            8'd13: depth_color = 16'hfd06;
            8'd14: depth_color = 16'hfc24;
            8'd15: depth_color = 16'hf363;
            8'd16: depth_color = 16'heac2;
            8'd17: depth_color = 16'hea41;
            8'd18: depth_color = 16'he201;
            8'd19: depth_color = 16'hd9a0;
            8'd20: depth_color = 16'hd180;
            8'd21: depth_color = 16'hc940;
            8'd22: depth_color = 16'hc120;
            8'd23: depth_color = 16'hb900;
            8'd24: depth_color = 16'hb0e0;
            8'd25: depth_color = 16'hb0c0;
            8'd26: depth_color = 16'ha8a0;
            8'd27: depth_color = 16'ha0a0;
            8'd28: depth_color = 16'ha080;
            8'd29: depth_color = 16'h9880;
            8'd30: depth_color = 16'h9860;
            8'd31: depth_color = 16'h9060;
            8'd32: depth_color = 16'h9040;
            8'd33: depth_color = 16'h8840;
            8'd34: depth_color = 16'h8840;
            8'd35: depth_color = 16'h8020;
            8'd36: depth_color = 16'h8020;
            8'd37: depth_color = 16'h8020;
            8'd38: depth_color = 16'h7820;
            default: depth_color = 16'h0000;
        endcase
    end
endfunction
