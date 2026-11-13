// M3 integration candidate R02: screen 596.7 mm, octave 165 mm.
// User selected comparison version; physical key alignment NOT verified.
// White/black cap widths 22/11 mm and black centers are provisional.
// Fixed 640 source columns. Raw endpoints, exclusive right endpoint.
// Include inside each consuming module; intentionally no global guard.
// Gate all slider body/core/glow terms with physical_slider_visible.

function automatic [9:0] physical_key_left(input [6:0] note);
    begin
        case (note)
            7'd36: physical_key_left = 10'd0;
            7'd37: physical_key_left = 10'd16;
            7'd38: physical_key_left = 10'd25;
            7'd39: physical_key_left = 10'd46;
            7'd40: physical_key_left = 10'd51;
            7'd41: physical_key_left = 10'd76;
            7'd42: physical_key_left = 10'd91;
            7'd43: physical_key_left = 10'd101;
            7'd44: physical_key_left = 10'd120;
            7'd45: physical_key_left = 10'd126;
            7'd46: physical_key_left = 10'd149;
            7'd47: physical_key_left = 10'd152;
            7'd48: physical_key_left = 10'd177;
            7'd49: physical_key_left = 10'd193;
            7'd50: physical_key_left = 10'd202;
            7'd51: physical_key_left = 10'd223;
            7'd52: physical_key_left = 10'd228;
            7'd53: physical_key_left = 10'd253;
            7'd54: physical_key_left = 10'd268;
            7'd55: physical_key_left = 10'd278;
            7'd56: physical_key_left = 10'd297;
            7'd57: physical_key_left = 10'd303;
            7'd58: physical_key_left = 10'd326;
            7'd59: physical_key_left = 10'd329;
            7'd60: physical_key_left = 10'd354;
            7'd61: physical_key_left = 10'd370;
            7'd62: physical_key_left = 10'd379;
            7'd63: physical_key_left = 10'd400;
            7'd64: physical_key_left = 10'd405;
            7'd65: physical_key_left = 10'd430;
            7'd66: physical_key_left = 10'd445;
            7'd67: physical_key_left = 10'd455;
            7'd68: physical_key_left = 10'd474;
            7'd69: physical_key_left = 10'd480;
            7'd70: physical_key_left = 10'd503;
            7'd71: physical_key_left = 10'd506;
            7'd72: physical_key_left = 10'd531;
            7'd73: physical_key_left = 10'd547;
            7'd74: physical_key_left = 10'd556;
            7'd75: physical_key_left = 10'd577;
            7'd76: physical_key_left = 10'd581;
            7'd77: physical_key_left = 10'd607;
            7'd78: physical_key_left = 10'd622;
            7'd79: physical_key_left = 10'd632;
            7'd80: physical_key_left = 10'd651;
            7'd81: physical_key_left = 10'd657;
            7'd82: physical_key_left = 10'd680;
            7'd83: physical_key_left = 10'd683;
            7'd84: physical_key_left = 10'd708;
            default: physical_key_left = 10'd0;
        endcase
    end
endfunction

function automatic [9:0] physical_key_right(input [6:0] note);
    begin
        case (note)
            7'd36: physical_key_right = 10'd24;
            7'd37: physical_key_right = 10'd28;
            7'd38: physical_key_right = 10'd49;
            7'd39: physical_key_right = 10'd58;
            7'd40: physical_key_right = 10'd74;
            7'd41: physical_key_right = 10'd99;
            7'd42: physical_key_right = 10'd102;
            7'd43: physical_key_right = 10'd125;
            7'd44: physical_key_right = 10'd131;
            7'd45: physical_key_right = 10'd150;
            7'd46: physical_key_right = 10'd161;
            7'd47: physical_key_right = 10'd175;
            7'd48: physical_key_right = 10'd201;
            7'd49: physical_key_right = 10'd205;
            7'd50: physical_key_right = 10'd226;
            7'd51: physical_key_right = 10'd235;
            7'd52: physical_key_right = 10'd251;
            7'd53: physical_key_right = 10'd276;
            7'd54: physical_key_right = 10'd279;
            7'd55: physical_key_right = 10'd302;
            7'd56: physical_key_right = 10'd308;
            7'd57: physical_key_right = 10'd327;
            7'd58: physical_key_right = 10'd338;
            7'd59: physical_key_right = 10'd352;
            7'd60: physical_key_right = 10'd378;
            7'd61: physical_key_right = 10'd382;
            7'd62: physical_key_right = 10'd403;
            7'd63: physical_key_right = 10'd412;
            7'd64: physical_key_right = 10'd428;
            7'd65: physical_key_right = 10'd453;
            7'd66: physical_key_right = 10'd456;
            7'd67: physical_key_right = 10'd479;
            7'd68: physical_key_right = 10'd485;
            7'd69: physical_key_right = 10'd504;
            7'd70: physical_key_right = 10'd514;
            7'd71: physical_key_right = 10'd529;
            7'd72: physical_key_right = 10'd555;
            7'd73: physical_key_right = 10'd559;
            7'd74: physical_key_right = 10'd580;
            7'd75: physical_key_right = 10'd589;
            7'd76: physical_key_right = 10'd605;
            7'd77: physical_key_right = 10'd630;
            7'd78: physical_key_right = 10'd633;
            7'd79: physical_key_right = 10'd656;
            7'd80: physical_key_right = 10'd662;
            7'd81: physical_key_right = 10'd681;
            7'd82: physical_key_right = 10'd691;
            7'd83: physical_key_right = 10'd706;
            7'd84: physical_key_right = 10'd731;
            default: physical_key_right = 10'd0;
        endcase
    end
endfunction

function automatic physical_slider_visible(input [6:0] note);
    begin
        case (note)
            7'd36: physical_slider_visible = 1'd1;
            7'd37: physical_slider_visible = 1'd1;
            7'd38: physical_slider_visible = 1'd1;
            7'd39: physical_slider_visible = 1'd1;
            7'd40: physical_slider_visible = 1'd1;
            7'd41: physical_slider_visible = 1'd1;
            7'd42: physical_slider_visible = 1'd1;
            7'd43: physical_slider_visible = 1'd1;
            7'd44: physical_slider_visible = 1'd1;
            7'd45: physical_slider_visible = 1'd1;
            7'd46: physical_slider_visible = 1'd1;
            7'd47: physical_slider_visible = 1'd1;
            7'd48: physical_slider_visible = 1'd1;
            7'd49: physical_slider_visible = 1'd1;
            7'd50: physical_slider_visible = 1'd1;
            7'd51: physical_slider_visible = 1'd1;
            7'd52: physical_slider_visible = 1'd1;
            7'd53: physical_slider_visible = 1'd1;
            7'd54: physical_slider_visible = 1'd1;
            7'd55: physical_slider_visible = 1'd1;
            7'd56: physical_slider_visible = 1'd1;
            7'd57: physical_slider_visible = 1'd1;
            7'd58: physical_slider_visible = 1'd1;
            7'd59: physical_slider_visible = 1'd1;
            7'd60: physical_slider_visible = 1'd1;
            7'd61: physical_slider_visible = 1'd1;
            7'd62: physical_slider_visible = 1'd1;
            7'd63: physical_slider_visible = 1'd1;
            7'd64: physical_slider_visible = 1'd1;
            7'd65: physical_slider_visible = 1'd1;
            7'd66: physical_slider_visible = 1'd1;
            7'd67: physical_slider_visible = 1'd1;
            7'd68: physical_slider_visible = 1'd1;
            7'd69: physical_slider_visible = 1'd1;
            7'd70: physical_slider_visible = 1'd1;
            7'd71: physical_slider_visible = 1'd1;
            7'd72: physical_slider_visible = 1'd1;
            7'd73: physical_slider_visible = 1'd1;
            7'd74: physical_slider_visible = 1'd1;
            7'd75: physical_slider_visible = 1'd1;
            7'd76: physical_slider_visible = 1'd1;
            7'd77: physical_slider_visible = 1'd1;
            7'd78: physical_slider_visible = 1'd1;
            7'd79: physical_slider_visible = 1'd1;
            7'd80: physical_slider_visible = 1'd0;
            7'd81: physical_slider_visible = 1'd0;
            7'd82: physical_slider_visible = 1'd0;
            7'd83: physical_slider_visible = 1'd0;
            7'd84: physical_slider_visible = 1'd0;
            default: physical_slider_visible = 1'd0;
        endcase
    end
endfunction

function automatic physical_key_is_black(input [6:0] note);
    begin
        case (note)
            7'd36: physical_key_is_black = 1'd0;
            7'd37: physical_key_is_black = 1'd1;
            7'd38: physical_key_is_black = 1'd0;
            7'd39: physical_key_is_black = 1'd1;
            7'd40: physical_key_is_black = 1'd0;
            7'd41: physical_key_is_black = 1'd0;
            7'd42: physical_key_is_black = 1'd1;
            7'd43: physical_key_is_black = 1'd0;
            7'd44: physical_key_is_black = 1'd1;
            7'd45: physical_key_is_black = 1'd0;
            7'd46: physical_key_is_black = 1'd1;
            7'd47: physical_key_is_black = 1'd0;
            7'd48: physical_key_is_black = 1'd0;
            7'd49: physical_key_is_black = 1'd1;
            7'd50: physical_key_is_black = 1'd0;
            7'd51: physical_key_is_black = 1'd1;
            7'd52: physical_key_is_black = 1'd0;
            7'd53: physical_key_is_black = 1'd0;
            7'd54: physical_key_is_black = 1'd1;
            7'd55: physical_key_is_black = 1'd0;
            7'd56: physical_key_is_black = 1'd1;
            7'd57: physical_key_is_black = 1'd0;
            7'd58: physical_key_is_black = 1'd1;
            7'd59: physical_key_is_black = 1'd0;
            7'd60: physical_key_is_black = 1'd0;
            7'd61: physical_key_is_black = 1'd1;
            7'd62: physical_key_is_black = 1'd0;
            7'd63: physical_key_is_black = 1'd1;
            7'd64: physical_key_is_black = 1'd0;
            7'd65: physical_key_is_black = 1'd0;
            7'd66: physical_key_is_black = 1'd1;
            7'd67: physical_key_is_black = 1'd0;
            7'd68: physical_key_is_black = 1'd1;
            7'd69: physical_key_is_black = 1'd0;
            7'd70: physical_key_is_black = 1'd1;
            7'd71: physical_key_is_black = 1'd0;
            7'd72: physical_key_is_black = 1'd0;
            7'd73: physical_key_is_black = 1'd1;
            7'd74: physical_key_is_black = 1'd0;
            7'd75: physical_key_is_black = 1'd1;
            7'd76: physical_key_is_black = 1'd0;
            7'd77: physical_key_is_black = 1'd0;
            7'd78: physical_key_is_black = 1'd1;
            7'd79: physical_key_is_black = 1'd0;
            7'd80: physical_key_is_black = 1'd1;
            7'd81: physical_key_is_black = 1'd0;
            7'd82: physical_key_is_black = 1'd1;
            7'd83: physical_key_is_black = 1'd0;
            7'd84: physical_key_is_black = 1'd0;
            default: physical_key_is_black = 1'd0;
        endcase
    end
endfunction
