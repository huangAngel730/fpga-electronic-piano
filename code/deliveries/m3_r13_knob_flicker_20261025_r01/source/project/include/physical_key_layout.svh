// Generated from measured geometry; exclusive right endpoint.
// Off-screen notes use an empty interval. No runtime division.
function automatic [9:0] physical_key_left(input [6:0] note);
    begin
        case (note)
            7'd36: physical_key_left = 10'd0;
            7'd37: physical_key_left = 10'd18;
            7'd38: physical_key_left = 10'd24;
            7'd39: physical_key_left = 10'd41;
            7'd40: physical_key_left = 10'd47;
            7'd41: physical_key_left = 10'd71;
            7'd42: physical_key_left = 10'd88;
            7'd43: physical_key_left = 10'd94;
            7'd44: physical_key_left = 10'd112;
            7'd45: physical_key_left = 10'd118;
            7'd46: physical_key_left = 10'd136;
            7'd47: physical_key_left = 10'd142;
            7'd48: physical_key_left = 10'd165;
            7'd49: physical_key_left = 10'd183;
            7'd50: physical_key_left = 10'd189;
            7'd51: physical_key_left = 10'd206;
            7'd52: physical_key_left = 10'd212;
            7'd53: physical_key_left = 10'd236;
            7'd54: physical_key_left = 10'd254;
            7'd55: physical_key_left = 10'd260;
            7'd56: physical_key_left = 10'd277;
            7'd57: physical_key_left = 10'd283;
            7'd58: physical_key_left = 10'd301;
            7'd59: physical_key_left = 10'd307;
            7'd60: physical_key_left = 10'd330;
            7'd61: physical_key_left = 10'd348;
            7'd62: physical_key_left = 10'd354;
            7'd63: physical_key_left = 10'd372;
            7'd64: physical_key_left = 10'd378;
            7'd65: physical_key_left = 10'd401;
            7'd66: physical_key_left = 10'd419;
            7'd67: physical_key_left = 10'd425;
            7'd68: physical_key_left = 10'd442;
            7'd69: physical_key_left = 10'd448;
            7'd70: physical_key_left = 10'd466;
            7'd71: physical_key_left = 10'd472;
            7'd72: physical_key_left = 10'd496;
            7'd73: physical_key_left = 10'd513;
            7'd74: physical_key_left = 10'd519;
            7'd75: physical_key_left = 10'd537;
            7'd76: physical_key_left = 10'd543;
            7'd77: physical_key_left = 10'd566;
            7'd78: physical_key_left = 10'd584;
            7'd79: physical_key_left = 10'd590;
            7'd80: physical_key_left = 10'd608;
            7'd81: physical_key_left = 10'd614;
            default: physical_key_left = 10'd0;
        endcase
    end
endfunction
function automatic [9:0] physical_key_right(input [6:0] note);
    begin
        case (note)
            7'd36: physical_key_right = 10'd24;
            7'd37: physical_key_right = 10'd29;
            7'd38: physical_key_right = 10'd47;
            7'd39: physical_key_right = 10'd53;
            7'd40: physical_key_right = 10'd71;
            7'd41: physical_key_right = 10'd94;
            7'd42: physical_key_right = 10'd100;
            7'd43: physical_key_right = 10'd118;
            7'd44: physical_key_right = 10'd124;
            7'd45: physical_key_right = 10'd142;
            7'd46: physical_key_right = 10'd147;
            7'd47: physical_key_right = 10'd165;
            7'd48: physical_key_right = 10'd189;
            7'd49: physical_key_right = 10'd195;
            7'd50: physical_key_right = 10'd212;
            7'd51: physical_key_right = 10'd218;
            7'd52: physical_key_right = 10'd236;
            7'd53: physical_key_right = 10'd260;
            7'd54: physical_key_right = 10'd265;
            7'd55: physical_key_right = 10'd283;
            7'd56: physical_key_right = 10'd289;
            7'd57: physical_key_right = 10'd307;
            7'd58: physical_key_right = 10'd313;
            7'd59: physical_key_right = 10'd330;
            7'd60: physical_key_right = 10'd354;
            7'd61: physical_key_right = 10'd360;
            7'd62: physical_key_right = 10'd378;
            7'd63: physical_key_right = 10'd383;
            7'd64: physical_key_right = 10'd401;
            7'd65: physical_key_right = 10'd425;
            7'd66: physical_key_right = 10'd431;
            7'd67: physical_key_right = 10'd448;
            7'd68: physical_key_right = 10'd454;
            7'd69: physical_key_right = 10'd472;
            7'd70: physical_key_right = 10'd478;
            7'd71: physical_key_right = 10'd496;
            7'd72: physical_key_right = 10'd519;
            7'd73: physical_key_right = 10'd525;
            7'd74: physical_key_right = 10'd543;
            7'd75: physical_key_right = 10'd549;
            7'd76: physical_key_right = 10'd566;
            7'd77: physical_key_right = 10'd590;
            7'd78: physical_key_right = 10'd596;
            7'd79: physical_key_right = 10'd614;
            7'd80: physical_key_right = 10'd619;
            7'd81: physical_key_right = 10'd637;
            default: physical_key_right = 10'd0;
        endcase
    end
endfunction
