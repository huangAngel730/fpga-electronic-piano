`timescale 1ns/1ps
// Synthetic physical-inspired mono plucked string; no sampled recording.
module guitar_voice #(
    parameter integer OUTPUT_GAIN_Q15 = 98304 // R03 3.0 before final saturation
) (
    input wire clk, rst_n, sample_tick, note_on, note_off, kill,
    input wire [6:0] velocity,
    input wire [31:0] fcw,
    output reg signed [23:0] pcm,
    output reg pcm_valid,
    output wire busy,
    output reg active, protocol_error, invalid_pitch
);
    // The bridge-pluck triangle uses a bounded serial divide by seven.
    reg [6:0] stage;
    assign busy = stage!=0;
    reg [31:0] pitch;
    reg [6:0] vel;
    reg releasing;
    reg [15:0] release_age;
    reg [31:0] age;
    reg [22:0] noise;
    reg signed [23:0] previous_white, previous_delay, loop_sample;
    reg signed [31:0] body_x, body_v, body2_x, body2_v;
    reg signed [23:0] bright_lp, pick_fast, pick_slow, pick_sample;
    reg signed [32:0] pick_velocity_product;
    reg signed [41:0] pick_envelope_product;
    reg signed [23:0] ring[0:1023] /* synthesis syn_ramstyle = "block_ram" */;
    reg [9:0] ptr;
    reg [10:0] fill;
    reg [32:0] remainder;
    reg [48:0] quotient;
    reg [5:0] div_index;
    wire [32:0] trial = (remainder<<1) | (div_index==48 ? 33'd1 : 33'd0);
    wire [48:0] delay_q16 = quotient-49'd32768; // compensate averaging +0.5 sample
    wire [9:0] k_now = delay_q16[25:16];
    wire [15:0] fraction_now = delay_q16[15:0];
    wire [9:0] near_addr = ptr-k_now;
    wire [9:0] far_addr = ptr-k_now-10'd1;
    reg [31:0] pluck_phase,excitation_phase;
    reg [23:0] triangle_digits,triangle_quotient;
    reg [2:0] triangle_remainder;
    reg [4:0] triangle_bits;
    wire [3:0] triangle_trial={triangle_remainder,triangle_digits[23]};
    wire triangle_bit=triangle_trial>=4'd7;
    reg signed [23:0] triangle, excitation_mix;
    reg signed [31:0] excitation_product_q;
    reg [9:0] k;
    reg [15:0] fraction;
    reg signed [23:0] near_d, far_d, interpolated, filtered;
    reg signed [41:0] interp_product;
    wire signed [24:0] difference = {far_d[23],far_d}-{near_d[23],near_d};
    function automatic signed [63:0] sx(input signed [23:0] x);
        sx={{40{x[23]}},x};
    endfunction
    function automatic signed [63:0] round_shift(input signed [63:0] n, input integer b);
        if(n<0) round_shift=-(((-n)+(64'sd1<<(b-1)))>>>b);
        else round_shift=(n+(64'sd1<<(b-1)))>>>b;
    endfunction
    function automatic signed [23:0] sat24(input signed [63:0] n);
        if(n>8388607) sat24=24'sh7fffff;
        else if(n< -64'sd8388608) sat24=24'sh800000;
        else sat24=n[23:0];
    endfunction
    function automatic signed [31:0] sat32(input signed [63:0] n);
        if(n>64'sd2147483647) sat32=32'sh7fffffff;
        else if(n< -64'sd2147483648) sat32=32'sh80000000;
        else sat32=n[31:0];
    endfunction
    wire signed [63:0] white = {{48{noise[22]}},noise[22:7]} <<< 6;
    // Pick noise reaches OUTPUT for only 192 accepted active samples (4ms).
    // Old parallel fast/slow state is multiplied in separate E53/E54 stages.
    wire signed [24:0] pick_band = {pick_fast[23],pick_fast}-{pick_slow[23],pick_slow};
    wire [7:0] pick_envelope = age<192 ? 8'(32'd192-age) : 8'd0;
    wire signed [63:0] pick_fast_next = sx(pick_fast)+((white-sx(pick_fast))>>>1);
    wire signed [63:0] pick_slow_next = sx(pick_slow)+((white-sx(pick_slow))>>>4);
    wire [15:0] feedback = releasing ? 16'd24576 : 16'd32640+{9'd0,vel[6:1]};
    wire signed [40:0] feedback_product = filtered*$signed({1'b0,feedback});
    wire signed [63:0] excitation_n = round_shift({{32{excitation_product_q[31]}},excitation_product_q},7);
    wire signed [63:0] feedback_n = round_shift({{23{feedback_product[40]}},feedback_product},15);
    wire signed [63:0] bx = {{32{body_x[31]}},body_x};
    wire signed [63:0] bv = {{32{body_v[31]}},body_v};
    wire signed [63:0] b2x = {{32{body2_x[31]}},body2_x};
    wire signed [63:0] b2v = {{32{body2_v[31]}},body2_v};
    wire signed [63:0] body_v_next = bv-(bv>>>7)-(bx>>>12)+(sx(loop_sample)>>>10);
    wire signed [63:0] body2_v_next = b2v-(b2v>>>5)-(b2x>>>8)+(sx(loop_sample)>>>9);
    wire signed [63:0] bright_lp_next = sx(bright_lp)+((sx(loop_sample)-sx(bright_lp))>>>2);
    reg signed [24:0] bright_delta;
    reg signed [35:0] body_pick,pickup_low,pickup_high,pickup;
    reg signed [54:0] output_product;
    reg signed [63:0] output_n;

    reg [9:0] near_addr_q,far_addr_q;
    reg signed [23:0] ring_read;
    wire [9:0] ring_addr=stage==51 ? near_addr_q : far_addr_q;
    wire signed [23:0] ring_write=age<({22'd0,k}+32'd1) ? sat24(excitation_n) : sat24(feedback_n);
    always @(posedge clk) begin
        if(stage==51 || stage==52) ring_read<=ring[ring_addr];
        if(stage==57 && rst_n && !kill && active && !(releasing && release_age>=24000))
            ring[ptr]<=ring_write;
    end

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            stage<=0; pcm<=0; pcm_valid<=0; active<=0;
            protocol_error<=0; invalid_pitch<=0; pitch<=19685267; vel<=0;
            releasing<=0; release_age<=0; age<=0; noise<=23'h5a17cd;
            previous_white<=0; previous_delay<=0; loop_sample<=0; body_x<=0; body_v<=0;
            body2_x<=0; body2_v<=0; excitation_phase<=0; triangle<=0;
            pluck_phase<=0;triangle_digits<=0;triangle_quotient<=0;
            triangle_remainder<=0;triangle_bits<=0;
            bright_lp<=0; pick_fast<=0; pick_slow<=0; pick_sample<=0;
            pick_velocity_product<=0; pick_envelope_product<=0;
            excitation_mix<=0; excitation_product_q<=0; ptr<=0; fill<=0;
            remainder<=0; quotient<=0; div_index<=48; k<=0; fraction<=0;
            near_d<=0; far_d<=0; interpolated<=0; filtered<=0; interp_product<=0;
        end else if(kill) begin
            // Kill works even without tick and abandons a pending sample.
            stage<=0; pcm<=0; pcm_valid<=0; active<=0; releasing<=0;
            release_age<=0; age<=0; pluck_phase<=0; ptr<=0; fill<=0;
            previous_white<=0; previous_delay<=0; loop_sample<=0; body_x<=0; body_v<=0;
            body2_x<=0; body2_v<=0; noise<=23'h5a17cd;
            bright_lp<=0; pick_fast<=0; pick_slow<=0; pick_sample<=0;
            pick_velocity_product<=0; pick_envelope_product<=0;
        end else begin
            pcm_valid<=0;
            if(sample_tick && busy) protocol_error<=1;
            if(stage==0) begin
                if(sample_tick) begin
                    stage<=1; remainder<=0; quotient<=0; div_index<=48;
                    if(note_on && velocity!=0) begin
                        if(fcw<7000000 || fcw>120000000) begin
                            invalid_pitch<=1; active<=0;
                        end else begin
                            pitch<=fcw; vel<=velocity; active<=1; releasing<=0;
                            release_age<=0; age<=0; pluck_phase<=0; ptr<=0; fill<=0;
                            previous_white<=0; previous_delay<=0;
                            body_x<=0; body_v<=0; body2_x<=0; body2_v<=0; noise<=23'h5a17cd;
                            bright_lp<=0; pick_fast<=0; pick_slow<=0; pick_sample<=0;
                            pick_velocity_product<=0; pick_envelope_product<=0;
                        end
                    end else if(note_off || (note_on && velocity==0)) begin
                        releasing<=1; release_age<=0;
                    end
                end
            end else if(stage<=49) begin
                if(trial>={1'b0,pitch}) begin
                    remainder<=trial-{1'b0,pitch}; quotient<={quotient[47:0],1'b1};
                end else begin
                    remainder<=trial; quotient<={quotient[47:0],1'b0};
                end
                if(div_index!=0) div_index<=div_index-1'b1;
                stage<=stage+1'b1;
            end else case(stage)
                50: begin
                    k<=k_now; fraction<=fraction_now;
                    near_addr_q<=near_addr;far_addr_q<=far_addr;
                    excitation_phase<=pluck_phase;
                    stage<=51;
                end
                51: stage<=52;
                52: begin near_d<=fill>=k ? ring_read : 24'sd0;stage<=53;end
                53: begin far_d<=fill>k ? ring_read : 24'sd0;stage<=60;end
                60: begin
                    if(excitation_phase[31:29]==0) begin
                        triangle<=excitation_phase[31:8]-24'd1048576;
                        stage<=54;
                    end else begin
                        triangle_digits<=excitation_phase[31:8]-24'd2097152;
                        triangle_quotient<=0;triangle_remainder<=0;triangle_bits<=24;
                        stage<=61;
                    end
                end
                61: begin
                    triangle_digits<={triangle_digits[22:0],1'b0};
                    triangle_remainder<=triangle_bit ? 3'(triangle_trial-4'd7) : triangle_trial[2:0];
                    triangle_quotient<={triangle_quotient[22:0],triangle_bit};
                    triangle_bits<=triangle_bits-1'b1;
                    if(triangle_bits==1) stage<=62;
                end
                62: begin triangle<=24'd1048576-triangle_quotient;stage<=54;end
                54: begin
                    interp_product<=difference*$signed({1'b0,fraction});
                    stage<=55;
                end
                55: begin
                    interpolated<=sat24(sx(near_d)+($signed({{22{interp_product[41]}},interp_product})>>>16));
                    excitation_mix<=triangle;
                    stage<=56;
                end
                56: begin
                    filtered<=sat24(round_shift(sx(interpolated)+sx(previous_delay),1));
                    excitation_product_q<=excitation_mix*$signed({1'b0,vel});
                    pick_velocity_product<=pick_band*$signed({1'b0,vel});
                    previous_delay<=interpolated; stage<=57;
                end
                57: begin
                    if(active && !(releasing && release_age>=24000)) begin
                        pick_envelope_product<=pick_velocity_product*$signed({1'b0,pick_envelope});
                        pick_fast<=sat24(pick_fast_next); pick_slow<=sat24(pick_slow_next);
                        loop_sample<=ring_write;
                        ptr<=ptr+1'b1; if(fill<1024) fill<=fill+1'b1;
                        previous_white<=sat24(white);
                        noise<={noise[21:0],noise[22]^noise[17]};
                        if(age!=32'hffffffff) begin
                            age<=age+1'b1;
                            pluck_phase<=pluck_phase+pitch;
                        end
                        if(releasing && release_age<24000) release_age<=release_age+1'b1;
                    end else begin loop_sample<=0; active<=0; pick_envelope_product<=0; end
                    stage<=58;
                end
                58: begin
                    if(active) begin
                        body_v<=sat32(body_v_next); body_x<=sat32(bx+bv);
                        body2_v<=sat32(body2_v_next); body2_x<=sat32(b2x+b2v);
                        bright_lp<=sat24(bright_lp_next);
                        pick_sample<=sat24(round_shift({{22{pick_envelope_product[41]}},pick_envelope_product},17));
                    end else begin
                        body_x<=0; body_v<=0; body2_x<=0; body2_v<=0;
                        bright_lp<=0; pick_sample<=0;
                    end
                    stage<=59;
                end
                59: begin
                    bright_delta<=25'($signed(loop_sample))-25'($signed(bright_lp));
                    body_pick<=36'(bx>>>6)+36'(b2x>>>4);
                    stage<=63;
                end
                63: begin
                    pickup_low<=36'($signed(loop_sample))+(36'($signed(bright_delta))>>>1);
                    pickup_high<=body_pick+36'($signed(pick_sample));
                    stage<=64;
                end
                64: begin pickup<=pickup_low+pickup_high;stage<=65;end
                65: begin output_product<=pickup*$signed({1'b0,18'(OUTPUT_GAIN_Q15)});stage<=66;end
                66: begin output_n<=round_shift({{9{output_product[54]}},output_product},15);stage<=67;end
                67: begin pcm<=active ? sat24(output_n) : 24'sd0;
                    pcm_valid<=1; stage<=0; end
                default: stage<=0;
            endcase
        end
    end
    initial if(OUTPUT_GAIN_Q15<0 || OUTPUT_GAIN_Q15>131072)
        $fatal(1,"OUTPUT_GAIN_Q15 must be 0..131072 (0..4.0)");
endmodule
