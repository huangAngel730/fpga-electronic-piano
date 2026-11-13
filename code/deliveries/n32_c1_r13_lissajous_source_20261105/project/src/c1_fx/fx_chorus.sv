`timescale 1ns/1ps
// Stereo chorus. Address, RAM, interpolation, mix and rounding are pipelined.
// clk nominal40MHz; rst_n async low; clear sync high, aborts all ownership.
module fx_chorus #(
  parameter integer DEPTH=2048,
  parameter integer BASE_DELAY=720,
  parameter integer DEPTH_SAMPLES=240,
  parameter logic [31:0] PHASE_STEP=32'd44739,
  parameter integer DRY_GAIN=32768,
  parameter integer WET_GAIN=16384
)(
  input wire clk,rst_n,clear,
  input wire in_valid,output wire in_ready,
  input wire signed [23:0] in_left,in_right,
  input wire bypass,
  output wire out_valid,input wire out_ready,
  output logic signed [23:0] out_left,out_right,
  output logic out_clip
);
  initial begin
    if(DEPTH<4 || DEPTH>1048576 || DEPTH_SAMPLES<0 ||
       BASE_DELAY-DEPTH_SAMPLES<1 || BASE_DELAY+DEPTH_SAMPLES+1>=DEPTH ||
       DRY_GAIN<0 || WET_GAIN<0 || DRY_GAIN>32768 || WET_GAIN>32768)
      $fatal(1,"fx_chorus invalid elaboration parameters");
  end
  typedef enum logic [4:0] {
    IDLE,LFO_FOLD,LFO_SCALE,LFO_OFFSET,ADDR_SUB,ADDR_WRAP,ADDR_FAR,READ_NEAR,READ_FAR,
    TAP_DELTA,TAP_MULT,TAP_ADD,MIX_MULT,MIX_ADD,ROUND_PCM,LIMIT_PCM,HOLD
  } state_t;
  localparam integer AW=$clog2(DEPTH);
  localparam logic [15:0] DRY_Q=DRY_GAIN,WET_Q=WET_GAIN;
  state_t state;
  logic signed [23:0] mem_l[0:DEPTH-1] /* synthesis syn_ramstyle = "block_ram" */,mem_r[0:DEPTH-1] /* synthesis syn_ramstyle = "block_ram" */;
  logic [AW-1:0] ptr,write_slot,ln,lf,rn,rf;
  logic [AW:0] fill;
  logic [31:0] phase,phase_l,phase_r;
  logic signed [16:0] lfo_l,lfo_r;
  logic signed [39:0] offset_l,offset_r;
  logic [39:0] delay_l,delay_r;
  logic signed [AW+1:0] addr_ln,addr_rn;
  logic [15:0] frac_l,frac_r;
  logic ln_ok,lf_ok,rn_ok,rf_ok,bypass_q;
  logic signed [23:0] x_l,x_r,near_l,near_r,read_l,read_r;
  logic signed [24:0] delta_l,delta_r;
  logic signed [41:0] tap_product_l,tap_product_r;
  logic signed [23:0] interp_l,interp_r;
  logic signed [40:0] dry_l,dry_r,wet_l,wet_r;
  logic signed [41:0] mix_l,mix_r;
  logic signed [26:0] rounded_l,rounded_r;
  function automatic signed [16:0] folded(input logic [31:0] p);
    logic [15:0] triangle;
    begin
      triangle=p[31] ? ~{1'b0,p[30:15]} : {1'b0,p[30:15]};
      // Subtracting 32768 flips the top bit of the signed 16-bit result.
      folded=17'($signed({~triangle[15],triangle[14:0]}));
    end
  endfunction
  function automatic [AW-1:0] wrap_addr(input logic signed [AW+1:0] diff);
    wrap_addr=diff[AW+1] ? AW'(diff+(AW+2)'(DEPTH)) : diff[AW-1:0];
  endfunction
  function automatic signed [26:0] round_q15(input logic signed [41:0] x);
    logic increment;
    begin
      increment=x[14] && (!x[41] || |x[13:0]);
      round_q15=$signed(x[41:15]) + $signed({26'd0,increment});
    end
  endfunction
  function automatic signed [23:0] sat24(input logic signed [26:0] x);
    if(x>27'sd8388607)sat24=24'sh7fffff;
    else if(x< -27'sd8388608)sat24=24'sh800000;
    else sat24=x[23:0];
  endfunction
  wire [AW:0] kl=(AW+1)'(delay_l>>16),kr=(AW+1)'(delay_r>>16);
  assign in_ready=rst_n && !clear && state==IDLE;
  assign out_valid=rst_n && !clear && state==HOLD;
  // One read port per channel. Tap reads and writes occupy separate cycles.
  always @(posedge clk) begin
    if(state==READ_NEAR || state==READ_FAR) begin
      read_l<=mem_l[state==READ_NEAR ? ln : lf];
      read_r<=mem_r[state==READ_NEAR ? rn : rf];
    end
    if(state==LIMIT_PCM && rst_n && !clear)begin
      mem_l[write_slot]<=x_l;
      mem_r[write_slot]<=x_r;
    end
  end
  always @(posedge clk or negedge rst_n)begin
    if(!rst_n)begin
      state<=IDLE;ptr<=0;fill<=0;phase<=0;write_slot<=0;
      ln<=0;lf<=0;rn<=0;rf<=0;frac_l<=0;frac_r<=0;
      ln_ok<=0;lf_ok<=0;rn_ok<=0;rf_ok<=0;bypass_q<=0;
      x_l<=0;x_r<=0;near_l<=0;near_r<=0;
      phase_l<=0;phase_r<=0;lfo_l<=0;lfo_r<=0;offset_l<=0;offset_r<=0;
      delay_l<=0;delay_r<=0;addr_ln<=0;addr_rn<=0;
      delta_l<=0;delta_r<=0;tap_product_l<=0;tap_product_r<=0;
      interp_l<=0;interp_r<=0;dry_l<=0;dry_r<=0;wet_l<=0;wet_r<=0;
      mix_l<=0;mix_r<=0;rounded_l<=0;rounded_r<=0;
      out_left<=0;out_right<=0;out_clip<=0;
    end else if(clear)begin
      state<=IDLE;ptr<=0;fill<=0;phase<=0;write_slot<=0;
      ln<=0;lf<=0;rn<=0;rf<=0;frac_l<=0;frac_r<=0;
      ln_ok<=0;lf_ok<=0;rn_ok<=0;rf_ok<=0;bypass_q<=0;
      x_l<=0;x_r<=0;near_l<=0;near_r<=0;
      phase_l<=0;phase_r<=0;lfo_l<=0;lfo_r<=0;offset_l<=0;offset_r<=0;
      delay_l<=0;delay_r<=0;addr_ln<=0;addr_rn<=0;
      delta_l<=0;delta_r<=0;tap_product_l<=0;tap_product_r<=0;
      interp_l<=0;interp_r<=0;dry_l<=0;dry_r<=0;wet_l<=0;wet_r<=0;
      mix_l<=0;mix_r<=0;rounded_l<=0;rounded_r<=0;
      out_left<=0;out_right<=0;out_clip<=0;
    end else case(state)
      IDLE:if(in_valid)begin
        x_l<=in_left;x_r<=in_right;bypass_q<=bypass;write_slot<=ptr;
        phase_l<=phase;phase_r<=phase+32'h40000000;
        phase<=phase+PHASE_STEP;state<=LFO_FOLD;
      end
      LFO_FOLD:begin
        lfo_l<=folded(phase_l);lfo_r<=folded(phase_r);
        state<=LFO_SCALE;
      end
      LFO_SCALE:begin
        offset_l<=lfo_l*$signed(24'(2*DEPTH_SAMPLES));
        offset_r<=lfo_r*$signed(24'(2*DEPTH_SAMPLES));
        state<=LFO_OFFSET;
      end
      LFO_OFFSET:begin
        delay_l<=(40'(BASE_DELAY)<<16)+offset_l;
        delay_r<=(40'(BASE_DELAY)<<16)+offset_r;
        state<=ADDR_SUB;
      end
      ADDR_SUB:begin
        addr_ln<=$signed({2'b0,ptr})-$signed({1'b0,kl});
        addr_rn<=$signed({2'b0,ptr})-$signed({1'b0,kr});
        frac_l<=delay_l[15:0];frac_r<=delay_r[15:0];
        ln_ok<=fill>=kl;lf_ok<=fill>kl;
        rn_ok<=fill>=kr;rf_ok<=fill>kr;
        ptr<=ptr==DEPTH-1 ? 0 : ptr+1'b1;
        if(fill<DEPTH)fill<=fill+1'b1;
        state<=ADDR_WRAP;
      end
      ADDR_WRAP:begin
        ln<=wrap_addr(addr_ln);rn<=wrap_addr(addr_rn);
        state<=ADDR_FAR;
      end
      ADDR_FAR:begin
        lf<=ln==0 ? AW'(DEPTH-1) : ln-1'b1;
        rf<=rn==0 ? AW'(DEPTH-1) : rn-1'b1;
        state<=READ_NEAR;
      end
      READ_NEAR:state<=READ_FAR;
      READ_FAR:begin
        near_l<=ln_ok ? read_l : 24'sd0;
        near_r<=rn_ok ? read_r : 24'sd0;
        state<=TAP_DELTA;
      end
      TAP_DELTA:begin
        delta_l<=(lf_ok ? 25'($signed(read_l)) : 25'sd0)-25'($signed(near_l));
        delta_r<=(rf_ok ? 25'($signed(read_r)) : 25'sd0)-25'($signed(near_r));
        state<=TAP_MULT;
      end
      TAP_MULT:begin
        tap_product_l<=delta_l*$signed({1'b0,frac_l});
        tap_product_r<=delta_r*$signed({1'b0,frac_r});
        state<=TAP_ADD;
      end
      TAP_ADD:begin
        interp_l<=near_l+24'(tap_product_l>>>16);
        interp_r<=near_r+24'(tap_product_r>>>16);
        state<=MIX_MULT;
      end
      MIX_MULT:begin
        dry_l<=x_l*$signed({1'b0,DRY_Q}); dry_r<=x_r*$signed({1'b0,DRY_Q});
        wet_l<=interp_l*$signed({1'b0,WET_Q}); wet_r<=interp_r*$signed({1'b0,WET_Q});
        state<=MIX_ADD;
      end
      MIX_ADD:begin
        mix_l<=dry_l+wet_l;mix_r<=dry_r+wet_r;
        state<=ROUND_PCM;
      end
      ROUND_PCM:begin
        rounded_l<=round_q15(mix_l);rounded_r<=round_q15(mix_r);
        state<=LIMIT_PCM;
      end
      LIMIT_PCM:begin
        out_left<=bypass_q ? x_l : sat24(rounded_l);
        out_right<=bypass_q ? x_r : sat24(rounded_r);
        out_clip<=!bypass_q && (rounded_l>8388607 || rounded_l< -8388608 ||
                               rounded_r>8388607 || rounded_r< -8388608);
        state<=HOLD;
      end
      HOLD:if(out_ready)state<=IDLE;
      default:state<=IDLE;
    endcase
  end
endmodule
