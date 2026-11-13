// Mono stems, stereo FX result. One request owns the pipeline through HOLD.
// clk=40 MHz, active-low async reset. One accepted frame advances each history.
module c1_pcm_effects #(
    parameter integer DELAY_SAMPLES=14400
) (
    input wire clk,rst_n,cancel,frame_tick,
    input wire [31:0] current_req_id,
    input wire input_valid,
    output wire input_ready,
    input wire [31:0] input_id,
    input wire [2:0] requested_mode,
    input wire [2:0] requested_timbre,
    input wire signed [31:0] piano,organ,
    input wire signed [23:0] snare,sax,guitar,
    input wire upstream_clip,
    output wire result_valid,
    input wire result_ready,
    output logic [31:0] result_id,
    output logic signed [23:0] left,right,
    output logic [7:0] clip_bits,
    output wire busy
);
    localparam integer AW=$clog2(DELAY_SAMPLES);
    typedef enum logic [4:0] {
        IDLE, SUM_PAIRS, SUM_TOTAL, PREPARE, REBASE, DISPATCH, DELAY_READ,
        DELAY_ADD, DELAY_LIMIT, DELAY_WRITE, WAIT_FX, SCALE, OUTPUT_PCM, HOLD
    } state_t;
    state_t state;
    localparam logic [2:0] FX_DELAY=0, FX_CHORUS=1, FX_REVERB_ALL=2,
        FX_REVERB_SOLO=3, FX_DRY=4;
    logic [2:0] mode_q;
    logic [2:0] timbre_q;
    logic [7:0] level; // Q7, 128 samples per half; ~5.33ms per complete switch
    logic canceled,up_q,send_clip;
    logic signed [23:0] selected_q,dry_q,reverb_in_q,echo_q,echo_read;
    logic signed [31:0] pair_a_q,pair_b_q,guitar_q,stem_q,sum_q;
    logic signed [31:0] feedback_q,echo_sum_q;
    logic signed [23:0] delay_write_q,target_l,target_r;
    logic rebase_pending, reverb_clear_pending;
    logic signed [40:0] scale_l,scale_r;
    logic [AW-1:0] delay_ptr;
    logic [AW:0] delay_fill;
    logic signed [23:0] delay_mem [0:DELAY_SAMPLES-1] /* synthesis syn_ramstyle = "block_ram" */;
    wire stop=cancel || frame_tick;
    wire timbre_change=timbre_q!=requested_timbre;
    wire solo_reverb=mode_q==FX_REVERB_SOLO;
    wire request_solo_reverb=requested_mode==FX_REVERB_SOLO;
    wire solo_mode=mode_q==FX_DELAY || mode_q==FX_CHORUS || solo_reverb || mode_q==FX_DRY;
    wire reroute=(mode_q!=requested_mode) || (solo_mode && timbre_change);
    wire change_at_zero=reroute && level==0;
    wire clear_private=state==REBASE && rebase_pending;
    wire clear_reverb=state==REBASE && reverb_clear_pending;
    wire go=state==DISPATCH;
    wire signed [23:0] chorus_l,chorus_r,reverb_l;
    wire chorus_ready,reverb_ready,chorus_valid,reverb_valid,chorus_clip,reverb_clip;
    wire collect=state==WAIT_FX && chorus_valid && reverb_valid;
    assign input_ready=rst_n && state==IDLE && !stop;
    assign result_valid=rst_n && state==HOLD && !stop && !canceled &&
        result_id==current_req_id;
    assign busy=state!=IDLE;
    function automatic signed [31:0] extend24(input logic signed [23:0] x);
        extend24={{8{x[23]}},x};
    endfunction
    function automatic logic clipped(input logic signed [31:0] x);
        clipped=x>32'sd8388607 || x< -32'sd8388608;
    endfunction
    function automatic signed [23:0] saturate(input logic signed [31:0] x);
        if(x>32'sd8388607) saturate=24'sh7fffff;
        else if(x< -32'sd8388608) saturate=24'sh800000;
        else saturate=x[23:0];
    endfunction
    function automatic signed [31:0] stem(input logic [2:0] t,
        input logic signed [31:0] p,o,
        input logic signed [23:0] n,s,g);
        case(t)
            0: stem=p;
            1: stem=o;
            2: stem=extend24(n);
            3: stem=extend24(s);
            4: stem=extend24(g);
            default: stem=0;
        endcase
    endfunction
    wire signed [31:0] pair_a=piano+organ;
    wire signed [31:0] pair_b=extend24(snare)+extend24(sax);
    wire signed [31:0] chosen=stem(change_at_zero ? requested_timbre : timbre_q, piano,organ,snare,sax,guitar);
    wire signed [31:0] delayed=delay_fill==DELAY_SAMPLES ? extend24(echo_read) : 32'sd0;
    wire signed [31:0] feedback_sum=extend24(selected_q)+(delayed>>>2);
    wire signed [31:0] echo_mix=(extend24(selected_q)+delayed)>>>1;
    // All routes fade through zero so switching cannot leak a different
    // instrument into a solo effect or abruptly expose the ensemble bus.

    // Histories are clock-enabled, with separate RAM read and write cycles.
    // Clearing pointer/fill invalidates old samples without a RAM-wide reset.
    always @(posedge clk) begin
        if(state==DELAY_READ) echo_read<=delay_mem[delay_ptr];
        if(state==DELAY_WRITE) delay_mem[delay_ptr]<=delay_write_q;
    end
    fx_chorus u_chorus(
        .clk(clk),.rst_n(rst_n),.clear(clear_private),.in_valid(go),.in_ready(chorus_ready),
        .in_left(selected_q),.in_right(selected_q),.bypass(1'b0),
        .out_valid(chorus_valid),.out_ready(collect),.out_left(chorus_l),.out_right(chorus_r),
        .out_clip(chorus_clip));
    // 22938 / 32768 ~= 0.70 wet gain, with the existing 1.0 dry gain.
    fx_reverb #(.WET_GAIN(22938)) u_reverb(
        .clk(clk),.rst_n(rst_n),.clear(clear_reverb),.in_valid(go),.in_ready(reverb_ready),
        .in_left(reverb_in_q),.in_right(24'sd0),.bypass(1'b0),
        .out_valid(reverb_valid),.out_ready(collect),.out_left(reverb_l),.out_right(),
        .out_clip(reverb_clip));

    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE; mode_q<=0; timbre_q<=0; level<=0;
            delay_ptr<=0; delay_fill<=0; canceled<=0; send_clip<=0; up_q<=0;
            selected_q<=0; sum_q<=0; dry_q<=0; reverb_in_q<=0; echo_q<=0;
            pair_a_q<=0; pair_b_q<=0; guitar_q<=0; stem_q<=0; rebase_pending<=0; reverb_clear_pending<=0;
            feedback_q<=0; echo_sum_q<=0; delay_write_q<=0;
            target_l<=0; target_r<=0;
            scale_l<=0; scale_r<=0;
            result_id<=0; left<=0; right<=0; clip_bits<=0;
        end else begin
            if(stop && busy) canceled<=1;
            case(state)
                IDLE: if(input_valid && input_ready) begin
                    result_id<=input_id; canceled<=0; stem_q<=chosen;
                    pair_a_q<=pair_a; pair_b_q<=pair_b; guitar_q<=extend24(guitar);
                    up_q<=upstream_clip; rebase_pending<=change_at_zero && timbre_change;
                    // A solo route never inherits another stem's history.
                    reverb_clear_pending<=change_at_zero &&
                        ((solo_reverb != request_solo_reverb) ||
                         (solo_reverb && timbre_change));
                    state<=SUM_PAIRS;
                    if(change_at_zero) begin
                        mode_q<=requested_mode;
                        timbre_q<=requested_timbre;
                    end else begin
                        if(reroute) level<=level-1'b1;
                        else if(level!=8'd128) level<=level+1'b1;
                    end
                end
                SUM_PAIRS: begin
                    sum_q<=pair_a_q+pair_b_q;
                    selected_q<=saturate(stem_q);
                    state<=SUM_TOTAL;
                end
                SUM_TOTAL: begin
                    sum_q<=sum_q+guitar_q;
                    state<=PREPARE;
                end
                PREPARE: begin
                    dry_q<=saturate(sum_q);
                    reverb_in_q<=solo_reverb ? selected_q : saturate(sum_q);
                    state<=(rebase_pending || reverb_clear_pending) ? REBASE : DISPATCH;
                end
                REBASE: begin
                    if(rebase_pending) begin delay_ptr<=0; delay_fill<=0; end
                    state<=DISPATCH;
                end
                DISPATCH: state<=DELAY_READ;
                DELAY_READ: state<=DELAY_ADD;
                DELAY_ADD: begin
                    feedback_q<=feedback_sum;
                    echo_sum_q<=echo_mix;
                    state<=DELAY_LIMIT;
                end
                DELAY_LIMIT: begin
                    delay_write_q<=saturate(feedback_q);
                    echo_q<=saturate(echo_sum_q); send_clip<=clipped(feedback_q);
                    state<=DELAY_WRITE;
                end
                DELAY_WRITE: begin
                    if(delay_ptr==DELAY_SAMPLES-1) delay_ptr<=0;
                    else delay_ptr<=delay_ptr+1'b1;
                    if(delay_fill!=DELAY_SAMPLES) delay_fill<=delay_fill+1'b1;
                    state<=WAIT_FX;
                end
                WAIT_FX: if(collect) begin
                    case(mode_q)
                        FX_DELAY: begin
                            target_l<=echo_q; target_r<=echo_q;
                        end
                        FX_CHORUS: begin
                            target_l<=chorus_l; target_r<=chorus_r;
                        end
                        FX_REVERB_ALL, FX_REVERB_SOLO: begin
                            target_l<=reverb_l; target_r<=reverb_l;
                        end
                        default: begin target_l<=selected_q; target_r<=selected_q; end
                    endcase
                    case(mode_q)
                        FX_DELAY: send_clip<=send_clip;
                        FX_CHORUS: send_clip<=chorus_clip;
                        FX_REVERB_ALL, FX_REVERB_SOLO: send_clip<=reverb_clip;
                        default: send_clip<=0;
                    endcase
                    state<=SCALE;
                end
                SCALE: begin
                    scale_l<=target_l*$signed({1'b0,level});
                    scale_r<=target_r*$signed({1'b0,level});
                    state<=OUTPUT_PCM;
                end
                OUTPUT_PCM: begin
                    left<=scale_l[30:7]; right<=scale_r[30:7];
                    clip_bits<={2'b0,{2{send_clip}},{2{up_q || clipped(sum_q)}},
                        2'b00};
                    state<=HOLD;
                end
                HOLD: if(canceled || stop || result_ready || result_id!=current_req_id) state<=IDLE;
                default: state<=IDLE;
            endcase
        end
    end
    // synthesis translate_off
    initial if(DELAY_SAMPLES<2) $fatal(1,"C1 delay must have at least two samples");
    always @(posedge clk) if(rst_n && go && !(chorus_ready && reverb_ready))
        $fatal(1,"C1 FX frame overlap");
    // synthesis translate_on
endmodule
