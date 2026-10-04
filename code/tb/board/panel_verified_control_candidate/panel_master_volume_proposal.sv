// PROPOSED K1 math for M1 review, NOT approved/production integrated.
// Q1.16 unity=65536. Input CC7 expansion is bit replication, raw7=upper7bits.
// target=round(raw7*65536/127), constant LUT; each sample slews by <=128.
// Full-scale transition <=512 accepted sample ticks (10.667ms@48kHz).
// Negative PCM product uses arithmetic floor>>16; gain never exceeds unity.
module panel_master_volume_proposal #(
 parameter logic[3:0]PANEL_SOURCE=0,PANEL_CHANNEL=0,
 parameter integer SLEW_Q16=128)(
 input logic clk,rst_n,sample_tick,accepted_valid,input logic[63:0]accepted_data,
 output logic[16:0]gain_q16,target_q16);
 import audio_defs_pkg::*;wire performance_event_t ev=accepted_data;
 function automatic logic[16:0]gain_map(input logic[6:0]raw);
 case(raw)
7'd0:gain_map=17'd0;
7'd1:gain_map=17'd516;
7'd2:gain_map=17'd1032;
7'd3:gain_map=17'd1548;
7'd4:gain_map=17'd2064;
7'd5:gain_map=17'd2580;
7'd6:gain_map=17'd3096;
7'd7:gain_map=17'd3612;
7'd8:gain_map=17'd4128;
7'd9:gain_map=17'd4644;
7'd10:gain_map=17'd5160;
7'd11:gain_map=17'd5676;
7'd12:gain_map=17'd6192;
7'd13:gain_map=17'd6708;
7'd14:gain_map=17'd7224;
7'd15:gain_map=17'd7740;
7'd16:gain_map=17'd8257;
7'd17:gain_map=17'd8773;
7'd18:gain_map=17'd9289;
7'd19:gain_map=17'd9805;
7'd20:gain_map=17'd10321;
7'd21:gain_map=17'd10837;
7'd22:gain_map=17'd11353;
7'd23:gain_map=17'd11869;
7'd24:gain_map=17'd12385;
7'd25:gain_map=17'd12901;
7'd26:gain_map=17'd13417;
7'd27:gain_map=17'd13933;
7'd28:gain_map=17'd14449;
7'd29:gain_map=17'd14965;
7'd30:gain_map=17'd15481;
7'd31:gain_map=17'd15997;
7'd32:gain_map=17'd16513;
7'd33:gain_map=17'd17029;
7'd34:gain_map=17'd17545;
7'd35:gain_map=17'd18061;
7'd36:gain_map=17'd18577;
7'd37:gain_map=17'd19093;
7'd38:gain_map=17'd19609;
7'd39:gain_map=17'd20125;
7'd40:gain_map=17'd20641;
7'd41:gain_map=17'd21157;
7'd42:gain_map=17'd21673;
7'd43:gain_map=17'd22189;
7'd44:gain_map=17'd22705;
7'd45:gain_map=17'd23221;
7'd46:gain_map=17'd23737;
7'd47:gain_map=17'd24253;
7'd48:gain_map=17'd24770;
7'd49:gain_map=17'd25286;
7'd50:gain_map=17'd25802;
7'd51:gain_map=17'd26318;
7'd52:gain_map=17'd26834;
7'd53:gain_map=17'd27350;
7'd54:gain_map=17'd27866;
7'd55:gain_map=17'd28382;
7'd56:gain_map=17'd28898;
7'd57:gain_map=17'd29414;
7'd58:gain_map=17'd29930;
7'd59:gain_map=17'd30446;
7'd60:gain_map=17'd30962;
7'd61:gain_map=17'd31478;
7'd62:gain_map=17'd31994;
7'd63:gain_map=17'd32510;
7'd64:gain_map=17'd33026;
7'd65:gain_map=17'd33542;
7'd66:gain_map=17'd34058;
7'd67:gain_map=17'd34574;
7'd68:gain_map=17'd35090;
7'd69:gain_map=17'd35606;
7'd70:gain_map=17'd36122;
7'd71:gain_map=17'd36638;
7'd72:gain_map=17'd37154;
7'd73:gain_map=17'd37670;
7'd74:gain_map=17'd38186;
7'd75:gain_map=17'd38702;
7'd76:gain_map=17'd39218;
7'd77:gain_map=17'd39734;
7'd78:gain_map=17'd40250;
7'd79:gain_map=17'd40766;
7'd80:gain_map=17'd41283;
7'd81:gain_map=17'd41799;
7'd82:gain_map=17'd42315;
7'd83:gain_map=17'd42831;
7'd84:gain_map=17'd43347;
7'd85:gain_map=17'd43863;
7'd86:gain_map=17'd44379;
7'd87:gain_map=17'd44895;
7'd88:gain_map=17'd45411;
7'd89:gain_map=17'd45927;
7'd90:gain_map=17'd46443;
7'd91:gain_map=17'd46959;
7'd92:gain_map=17'd47475;
7'd93:gain_map=17'd47991;
7'd94:gain_map=17'd48507;
7'd95:gain_map=17'd49023;
7'd96:gain_map=17'd49539;
7'd97:gain_map=17'd50055;
7'd98:gain_map=17'd50571;
7'd99:gain_map=17'd51087;
7'd100:gain_map=17'd51603;
7'd101:gain_map=17'd52119;
7'd102:gain_map=17'd52635;
7'd103:gain_map=17'd53151;
7'd104:gain_map=17'd53667;
7'd105:gain_map=17'd54183;
7'd106:gain_map=17'd54699;
7'd107:gain_map=17'd55215;
7'd108:gain_map=17'd55731;
7'd109:gain_map=17'd56247;
7'd110:gain_map=17'd56763;
7'd111:gain_map=17'd57279;
7'd112:gain_map=17'd57796;
7'd113:gain_map=17'd58312;
7'd114:gain_map=17'd58828;
7'd115:gain_map=17'd59344;
7'd116:gain_map=17'd59860;
7'd117:gain_map=17'd60376;
7'd118:gain_map=17'd60892;
7'd119:gain_map=17'd61408;
7'd120:gain_map=17'd61924;
7'd121:gain_map=17'd62440;
7'd122:gain_map=17'd62956;
7'd123:gain_map=17'd63472;
7'd124:gain_map=17'd63988;
7'd125:gain_map=17'd64504;
7'd126:gain_map=17'd65020;
7'd127:gain_map=17'd65536;
 default:gain_map=17'd65536;
 endcase
 endfunction
 wire is_volume=accepted_valid&&ev.event_type==EVENT_CONTROL_CHANGE&&ev.control_id==CTRL_VOLUME&&ev.source_id==PANEL_SOURCE&&ev.channel==PANEL_CHANNEL;
 wire[16:0]desired=is_volume?gain_map(ev.control_value[11:5]):target_q16;
 logic[16:0]next_gain;
 always_comb begin
 next_gain=gain_q16;
 if(desired>gain_q16)next_gain=desired-gain_q16<=SLEW_Q16?desired:gain_q16+17'(SLEW_Q16);
 else if(desired<gain_q16)next_gain=gain_q16-desired<=SLEW_Q16?desired:gain_q16-17'(SLEW_Q16);
 end
 always_ff @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin gain_q16<=65536;target_q16<=65536;end
 else begin
 if(is_volume)target_q16<=desired;
 if(sample_tick)gain_q16<=next_gain;
 end
 end
 `ifndef SYNTHESIS
 initial if(SLEW_Q16<1||SLEW_Q16>65536)$fatal(1,"invalid volume proposal slew");
 `endif
endmodule

// Generic one-token gain stage: math isolation candidate only. Input gain
// freezes with id/samples, external changes never rewrite a held result.
module panel_pcm_gain_stage(
 input logic clk,rst_n,cancel,request_valid,output wire request_ready,
 input logic[31:0]request_id,input logic signed[23:0]request_left,request_right,
 input logic[16:0]request_gain,
 output wire result_valid,input logic result_ready,
 output logic[31:0]result_id,output logic signed[23:0]result_left,result_right);
 logic[1:0]state;logic signed[41:0]left_product,right_product;
 assign request_ready=rst_n&&!cancel&&state==0;
 assign result_valid=rst_n&&!cancel&&state==2;
 always_ff @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin state<=0;result_id<=0;result_left<=0;result_right<=0;left_product<=0;right_product<=0;end
 else if(cancel)state<=0;
 else case(state)
 0:if(request_valid)begin
 result_id<=request_id;
 left_product<=$signed(request_left)*$signed({1'b0,request_gain});
 right_product<=$signed(request_right)*$signed({1'b0,request_gain});state<=1;
 end
 1:begin result_left<=24'(left_product>>>16);result_right<=24'(right_product>>>16);state<=2;end
 2:if(result_ready)state<=0;
 default:state<=0;
 endcase
 end
 `ifndef SYNTHESIS
 always @(posedge clk)if(rst_n&&request_valid&&request_ready&&request_gain>65536)$fatal(1,"volume gain exceeds approved no-amplification envelope");
 `endif
endmodule
