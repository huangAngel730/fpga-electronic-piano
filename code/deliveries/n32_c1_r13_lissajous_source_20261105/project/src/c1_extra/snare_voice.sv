`timescale 1ns/1ps
// Synthetic standalone fixed-pitch snare. Accepted tick E0 -> valid E8.
// Reset async low. No-tick kill synchronously clears/aborts, no valid result.
// Tick kill replaces inflight work with E8 zero (sticky overlap error).
module snare_voice(
 input wire clk,rst_n,sample_tick,note_on,note_off,kill,
 input wire [6:0] velocity,input wire [31:0] fcw,
 output reg signed [23:0] pcm,output reg pcm_valid,
 output wire busy,active,output reg protocol_error,invalid_pitch
);
 reg [3:0] stage;
 reg [95:0] x_state,v_state,sx,sv,nx,nv;
 reg [16:0] et,en,ea,st,sn,sa;
 reg [6:0] vel,vs;
 reg signed [31:0] fast,slow,old_white,sfast,sslow,sold_white,nfast,nslow,white;
 reg [22:0] rng,srng,next_rng;
 reg signed [47:0] px0,px1,px2,pv0,pv1,pv2;
 reg signed [31:0] px_gain0,px_gain1,px_gain2;
 reg signed [63:0] body_product,wire_product,strike_product,combined,final_product;
 wire accept=sample_tick && (!busy || kill);
 assign busy=(stage!=0);
 assign active=(et!=0 || en!=0 || ea!=0);
 wire unused_fcw=^fcw;
 function automatic signed [63:0] round_shift(input signed [63:0] value,input integer bits);
  begin
   if(value>=0)round_shift=(value+(64'sd1<<(bits-1)))>>>bits;
   else round_shift=-(((-value)+(64'sd1<<(bits-1)))>>>bits);
  end
 endfunction
 function automatic signed [31:0] sat32(input signed [63:0] v);
  begin
   if(v>64'sd2147483647)sat32=32'sh7fffffff;
   else if(v< -64'sd2147483648)sat32=32'sh80000000;
   else sat32=v[31:0];
  end
 endfunction
 function automatic signed [23:0] sat24(input signed [63:0] v);
  begin
   if(v>64'sd8388607)sat24=24'sh7fffff;
   else if(v< -64'sd8388608)sat24=24'sh800000;
   else sat24=v[23:0];
  end
 endfunction
 function automatic [16:0] decay(input [16:0] v,input integer shift);
  begin if(v==0)decay=0;else decay=v-(v>>shift)-1'b1;end
 endfunction
 function automatic signed [31:0] update_v(input signed [31:0] v,input signed [31:0] gain,input integer d);
  reg signed [63:0] a;
  begin a={{32{v[31]}},v};update_v=sat32(a-64'($signed(gain))-(a>>>d));end
 endfunction
 function automatic signed [31:0] update_x(input signed [31:0] x,input signed [47:0] p,input integer d);
  reg signed [63:0] a;
  begin a={{32{x[31]}},x};update_x=sat32(a+round_shift({{16{p[47]}},p},16)-(a>>>d));end
 endfunction
 wire signed [63:0] nx0={{32{nx[31]}},nx[31:0]};
 wire signed [63:0] nx1={{32{nx[63]}},nx[63:32]};
 wire signed [63:0] nx2={{32{nx[95]}},nx[95:64]};
 wire signed [63:0] tone=(nx0*64'sd2+nx1+nx2)>>>2;
 wire signed [63:0] band=$signed(nfast)-$signed(nslow);
 wire signed [63:0] attack=$signed(white)-$signed(sold_white);
 wire signed [63:0] noise_weight=(vs<48)?64'sd1:(vs<96)?64'sd2:64'sd3;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   stage<=0;pcm<=0;pcm_valid<=0;protocol_error<=0;invalid_pitch<=0;
   x_state<=0;v_state<=0;et<=0;en<=0;ea<=0;vel<=0;
   fast<=0;slow<=0;old_white<=0;rng<=23'h5a1234;
   sx<=0;sv<=0;nx<=0;nv<=0;st<=0;sn<=0;sa<=0;vs<=0;
   sfast<=0;sslow<=0;sold_white<=0;white<=0;nfast<=0;nslow<=0;srng<=0;next_rng<=0;
   px0<=0;px1<=0;px2<=0;pv0<=0;pv1<=0;pv2<=0;
   body_product<=0;wire_product<=0;strike_product<=0;combined<=0;final_product<=0;
  end else begin
   pcm_valid<=0;
   if(sample_tick && busy)protocol_error<=1;
   if(kill && !sample_tick)begin
    stage<=0;pcm<=0;pcm_valid<=0;
    x_state<=0;v_state<=0;et<=0;en<=0;ea<=0;
    fast<=0;slow<=0;old_white<=0;
    // RNG/velocity/sticky flags remain; no sample time elapsed.
   end else if(accept)begin
    srng<=rng;vs<=vel;
    if(kill)begin sx<=0;sv<=0;st<=0;sn<=0;sa<=0;sfast<=0;sslow<=0;sold_white<=0;end
    else if(note_on && velocity!=0 && !note_off)begin
     sx<=0;
     sv<={32'(4000+velocity*10),32'(6000+velocity*20),32'(10000+velocity*30)};
     st<=65536;sn<=65536;sa<=65536;vs<=velocity;
     sfast<=fast;sslow<=slow;sold_white<=old_white;
    end else begin
     sx<=x_state;sv<=v_state;st<=et;sn<=en;sa<=ea;
     sfast<=fast;sslow<=slow;sold_white<=old_white;
    end
    stage<=1;
   end else case(stage)
    1:begin
     px0<=$signed(sx[31:0])*16'sd1544;px1<=$signed(sx[63:32])*16'sd2831;px2<=$signed(sx[95:64])*16'sd4717;
     white<={{16{srng[22]}},srng[22:7]};
     nfast<=sfast+(($signed({{16{srng[22]}},srng[22:7]})-sfast)>>>((vs>=96)?1:2));
     nslow<=sslow+((sfast-sslow)>>>4);
     next_rng<={srng[21:0],srng[22]^srng[17]};stage<=2;
    end
    2:begin
     px_gain0<=32'(round_shift({{16{px0[47]}},px0},16));
     px_gain1<=32'(round_shift({{16{px1[47]}},px1},16));
     px_gain2<=32'(round_shift({{16{px2[47]}},px2},16));
     stage<=9;
    end
    9:begin
     nv<={update_v($signed(sv[95:64]),px_gain2,11),update_v($signed(sv[63:32]),px_gain1,12),update_v($signed(sv[31:0]),px_gain0,13)};
     stage<=3;
    end
    3:begin pv0<=$signed(nv[31:0])*16'sd1544;pv1<=$signed(nv[63:32])*16'sd2831;pv2<=$signed(nv[95:64])*16'sd4717;stage<=4;end
    4:begin nx<={update_x($signed(sx[95:64]),pv2,11),update_x($signed(sx[63:32]),pv1,12),update_x($signed(sx[31:0]),pv0,13)};stage<=5;end
    5:begin body_product<=tone*$signed({1'b0,st});wire_product<=band*$signed({1'b0,sn});strike_product<=attack*$signed({1'b0,sa});stage<=6;end
    6:begin combined<=round_shift(body_product,16)+((round_shift(wire_product,16)*noise_weight)>>>2)+(round_shift(strike_product,16)>>>2);stage<=7;end
    7:begin final_product<=combined*$signed({1'b0,vs,vs[6:4]});stage<=8;end
    8:begin
     pcm<=sat24(round_shift(final_product,3));pcm_valid<=1;stage<=0;
     x_state<=nx;v_state<=nv;fast<=nfast;slow<=nslow;old_white<=white;rng<=next_rng;
     et<=decay(st,12);en<=decay(sn,(vs<48)?9:(vs<96)?10:11);ea<=decay(sa,5);vel<=vs;
    end
    default:stage<=0;
   endcase
  end
 end
endmodule
