`timescale 1ns/1ps
// Standalone candidate only. Async active-low reset; synchronous clear wins.
module fx_reverb #(
    parameter integer COMB_DELAY_0 = 1499,
    parameter integer COMB_DELAY_1 = 1601,
    parameter integer COMB_DELAY_2 = 1747,
    parameter integer COMB_DELAY_3 = 1867,
    parameter integer AP_DELAY_0 = 223,
    parameter integer AP_DELAY_1 = 337,
    parameter integer FEEDBACK = 23593,
    parameter integer AP_GAIN = 16384,
    parameter integer DRY_GAIN = 32768,
    parameter integer WET_GAIN = 9830
) (
    input wire clk, rst_n, clear,
    input wire in_valid,
    output wire in_ready,
    input wire signed [23:0] in_left, in_right,
    input wire bypass,
    output reg out_valid,
    input wire out_ready,
    output reg signed [23:0] out_left, out_right,
    output reg out_clip
);
    typedef enum logic [4:0] {
        IDLE, COMB_MULT, COMB_ROUND, COMB_ADD, COMB_LIMIT, AVG_ROUND,
        AP_LOAD, AP_MULT, AP_ROUND, AP_ADD, AP_LIMIT,
        MIX_MULT, MIX_ADD, MIX_ROUND, COMMIT
    } state_t;
    state_t state;
    reg signed [23:0] x_l,x_r,avg_l,avg_r,ap_l,ap_r,late_l,late_r;
    reg bypass_q,clip_q;
    reg [1:0] ap_step;
    wire accept=in_valid && in_ready;
    assign in_ready=rst_n && !clear && state==IDLE && !out_valid;

    localparam logic signed [16:0] FB_Q=17'(FEEDBACK), AP_Q=17'(AP_GAIN);
    localparam logic signed [16:0] DRY_Q=17'(DRY_GAIN), WET_Q=17'(WET_GAIN);
    reg signed [23:0] delay_l[0:5],delay_r[0:5];
    reg signed [23:0] write_l[0:5],write_r[0:5];
    reg signed [40:0] comb_product_l[0:3],comb_product_r[0:3];
    reg signed [26:0] comb_gain_l[0:3],comb_gain_r[0:3];
    reg signed [26:0] comb_pcm_l[0:3],comb_pcm_r[0:3];
    reg signed [25:0] pair_a_l,pair_a_r,pair_b_l,pair_b_r,sum_l,sum_r;
    reg signed [23:0] ap_x_l,ap_x_r,ap_base_l,ap_base_r;
    reg signed [40:0] ap_product_l,ap_product_r;
    reg signed [26:0] ap_gain_l,ap_gain_r,ap_pcm_l,ap_pcm_r;
    reg signed [40:0] dry_l,dry_r,wet_l,wet_r;
    reg signed [41:0] mix_l,mix_r;
    reg signed [26:0] rounded_l,rounded_r;
    wire [3:0] comb_clip_l,comb_clip_r;

    function automatic signed [26:0] round_q15(input logic signed [41:0] x);
        logic increment;
        begin
            increment=x[14] && (!x[41] || |x[13:0]);
            round_q15=$signed(x[41:15])+$signed({26'd0,increment});
        end
    endfunction
    function automatic logic clipped(input logic signed [26:0] x);
        clipped=x>27'sd8388607 || x< -27'sd8388608;
    endfunction
    function automatic signed [23:0] sat(input logic signed [26:0] x);
        if(x>27'sd8388607) sat=24'sh7fffff;
        else if(x< -27'sd8388608) sat=24'sh800000;
        else sat=x[23:0];
    endfunction
    function automatic signed [23:0] average4(input logic signed [25:0] x);
        average4=$signed(x[25:2])+$signed({23'd0,x[1] && (!x[25] || x[0])});
    endfunction
    for(genvar c=0;c<4;c++) begin:g_clip
        assign comb_clip_l[c]=clipped(comb_pcm_l[c]);
        assign comb_clip_r[c]=clipped(comb_pcm_r[c]);
    end

    // Six independent exact-length stereo rings. No memory-array reset.
    // Fill masks all stale locations after reset/clear; write only at commit.
    genvar m;
    generate for (m=0;m<6;m=m+1) begin: rings
        localparam integer D = m==0 ? COMB_DELAY_0 : m==1 ? COMB_DELAY_1 :
            m==2 ? COMB_DELAY_2 : m==3 ? COMB_DELAY_3 :
            m==4 ? AP_DELAY_0 : AP_DELAY_1;
        localparam integer SAFE_D = D > 0 ? D : 1;
        localparam integer PW = SAFE_D<=1 ? 1 : $clog2(SAFE_D);
        localparam integer FW = $clog2(SAFE_D+1);
        reg signed [23:0] mem_l[0:SAFE_D-1] /* synthesis syn_ramstyle = "block_ram" */, mem_r[0:SAFE_D-1] /* synthesis syn_ramstyle = "block_ram" */;
        reg [PW-1:0] ptr;
        reg [FW-1:0] fill;
        reg signed [23:0] read_l,read_r;
        reg read_valid;
        assign delay_l[m]=read_valid ? read_l : 24'sd0;
        assign delay_r[m]=read_valid ? read_r : 24'sd0;
        always @(posedge clk) begin
            if(accept) begin
                read_l<=mem_l[ptr];
                read_r<=mem_r[ptr];
            end
            if(state==COMMIT && rst_n && !clear) begin
                mem_l[ptr]<=write_l[m];
                mem_r[ptr]<=write_r[m];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin
                ptr<=0; fill<=0; read_valid<=0;
            end else if (clear) begin
                ptr<=0; fill<=0; read_valid<=0;
            end else begin
                if(accept) read_valid<=fill==D;
                if(state==COMMIT) begin
                    ptr<=ptr==D-1 ? 0 : ptr+1'b1;
                    if(fill<D) fill<=fill+1'b1;
                end
            end
        end
    end endgenerate

    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; out_valid<=0; out_clip<=0; out_left<=0; out_right<=0;
            x_l<=0; x_r<=0; avg_l<=0; avg_r<=0; ap_l<=0; ap_r<=0;
            late_l<=0; late_r<=0; bypass_q<=0; clip_q<=0; ap_step<=0;
            for(i=0;i<6;i=i+1) begin write_l[i]<=0; write_r[i]<=0; end
        end else if (clear) begin
            state<=IDLE; out_valid<=0; out_clip<=0; out_left<=0; out_right<=0;
            x_l<=0; x_r<=0; avg_l<=0; avg_r<=0; ap_l<=0; ap_r<=0;
            late_l<=0; late_r<=0; bypass_q<=0; clip_q<=0; ap_step<=0;
            for(i=0;i<6;i=i+1) begin write_l[i]<=0; write_r[i]<=0; end
        end else begin
            if (out_valid && out_ready) out_valid<=0;
            case(state)
                IDLE: if(accept) begin
                    x_l<=in_left; x_r<=in_right; bypass_q<=bypass;
                    clip_q<=0; ap_step<=0; state<=COMB_MULT;
                end
                COMB_MULT: begin
                    for(i=0;i<4;i=i+1) begin
                        comb_product_l[i]<=delay_l[i]*FB_Q;
                        comb_product_r[i]<=delay_r[i]*FB_Q;
                    end
                    pair_a_l<=26'($signed(delay_l[0]))+26'($signed(delay_l[1]));
                    pair_b_l<=26'($signed(delay_l[2]))+26'($signed(delay_l[3]));
                    pair_a_r<=26'($signed(delay_r[0]))+26'($signed(delay_r[1]));
                    pair_b_r<=26'($signed(delay_r[2]))+26'($signed(delay_r[3]));
                    state<=COMB_ROUND;
                end
                COMB_ROUND: begin
                    for(i=0;i<4;i=i+1) begin
                        comb_gain_l[i]<=round_q15(42'($signed(comb_product_l[i])));
                        comb_gain_r[i]<=round_q15(42'($signed(comb_product_r[i])));
                    end
                    sum_l<=pair_a_l+pair_b_l;sum_r<=pair_a_r+pair_b_r;
                    state<=COMB_ADD;
                end
                COMB_ADD: begin
                    for(i=0;i<4;i=i+1) begin
                        comb_pcm_l[i]<=27'($signed(x_l))+comb_gain_l[i];
                        comb_pcm_r[i]<=27'($signed(x_r))+comb_gain_r[i];
                    end
                    state<=COMB_LIMIT;
                end
                COMB_LIMIT: begin
                    for(i=0;i<4;i=i+1) begin
                        write_l[i]<=sat(comb_pcm_l[i]);write_r[i]<=sat(comb_pcm_r[i]);
                    end
                    clip_q<=(|comb_clip_l)||(|comb_clip_r);
                    state<=AVG_ROUND;
                end
                AVG_ROUND: begin
                    avg_l<=average4(sum_l);avg_r<=average4(sum_r);state<=AP_LOAD;
                end
                AP_LOAD: begin
                    case(ap_step)
                        0: begin ap_x_l<=avg_l;ap_x_r<=avg_r;ap_base_l<=delay_l[4];ap_base_r<=delay_r[4];end
                        1: begin ap_x_l<=ap_l;ap_x_r<=ap_r;ap_base_l<=avg_l;ap_base_r<=avg_r;end
                        2: begin ap_x_l<=ap_l;ap_x_r<=ap_r;ap_base_l<=delay_l[5];ap_base_r<=delay_r[5];end
                        3: begin ap_x_l<=late_l;ap_x_r<=late_r;ap_base_l<=ap_l;ap_base_r<=ap_r;end
                    endcase
                    state<=AP_MULT;
                end
                AP_MULT: begin
                    ap_product_l<=ap_x_l*AP_Q;ap_product_r<=ap_x_r*AP_Q;
                    state<=AP_ROUND;
                end
                AP_ROUND: begin
                    ap_gain_l<=round_q15(42'($signed(ap_product_l)));
                    ap_gain_r<=round_q15(42'($signed(ap_product_r)));
                    state<=AP_ADD;
                end
                AP_ADD: begin
                    if(ap_step[0]) begin
                        ap_pcm_l<=27'($signed(ap_base_l))+ap_gain_l;
                        ap_pcm_r<=27'($signed(ap_base_r))+ap_gain_r;
                    end else begin
                        ap_pcm_l<=27'($signed(ap_base_l))-ap_gain_l;
                        ap_pcm_r<=27'($signed(ap_base_r))-ap_gain_r;
                    end
                    state<=AP_LIMIT;
                end
                AP_LIMIT: begin
                    clip_q<=clip_q|clipped(ap_pcm_l)|clipped(ap_pcm_r);
                    case(ap_step)
                        0: begin ap_l<=sat(ap_pcm_l);ap_r<=sat(ap_pcm_r);end
                        1: begin write_l[4]<=sat(ap_pcm_l);write_r[4]<=sat(ap_pcm_r);end
                        2: begin late_l<=sat(ap_pcm_l);late_r<=sat(ap_pcm_r);end
                        3: begin write_l[5]<=sat(ap_pcm_l);write_r[5]<=sat(ap_pcm_r);end
                    endcase
                    ap_step<=ap_step+1'b1;
                    state<=ap_step==3 ? MIX_MULT : AP_LOAD;
                end
                MIX_MULT: begin
                    dry_l<=x_l*DRY_Q;dry_r<=x_r*DRY_Q;
                    wet_l<=late_l*WET_Q;wet_r<=late_r*WET_Q;
                    state<=MIX_ADD;
                end
                MIX_ADD: begin
                    mix_l<=dry_l+wet_l;mix_r<=dry_r+wet_r;
                    state<=MIX_ROUND;
                end
                MIX_ROUND: begin
                    rounded_l<=round_q15(mix_l);rounded_r<=round_q15(mix_r);
                    state<=COMMIT;
                end
                COMMIT: begin
                    out_left<=bypass_q ? x_l : sat(rounded_l);
                    out_right<=bypass_q ? x_r : sat(rounded_r);
                    out_clip<=bypass_q ? 1'b0 : clip_q|clipped(rounded_l)|clipped(rounded_r);
                    out_valid<=1; state<=IDLE;
                end
                default: state<=IDLE;
            endcase
        end
    end

    initial begin
        if(COMB_DELAY_0<1 || COMB_DELAY_1<1 || COMB_DELAY_2<1 || COMB_DELAY_3<1 ||
           AP_DELAY_0<1 || AP_DELAY_1<1 || COMB_DELAY_0>65535 ||
           COMB_DELAY_1>65535 || COMB_DELAY_2>65535 || COMB_DELAY_3>65535 ||
           AP_DELAY_0>65535 || AP_DELAY_1>65535)
            $fatal(1,"reverb delay must be 1..65535");
        if(FEEDBACK<0 || FEEDBACK>29491 || AP_GAIN<0 || AP_GAIN>29491 ||
           DRY_GAIN<0 || DRY_GAIN>32768 || WET_GAIN<0 || WET_GAIN>32768)
            $fatal(1,"reverb invalid gain/feedback");
    end
endmodule
