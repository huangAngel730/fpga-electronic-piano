// Isolated N=4/8/16/32 dual-timbre structural successor, not a production top.
// Single clk, async active-low whole-domain reset, synchronized release upstream.
// M1 ADSR/Pitch modules and numerical ROMs are readonly pinned dependencies.
// Both DDS states advance once at ADVANCE. Serial shared ROMs preserve Piano's
// post-advance/table sample and the secondary timbre's pre-advance sample.
// In the R18 production integration the secondary ROM is Bright Octave:
// four 256-sample banks selected from the current FCW. No divide-by-N.
// A cancel AFTER ADVANCE drains the remaining hidden wave updates for ALL lanes;
// it suppresses writeback/publication but NEVER rolls back phase/envelope/LFO.
module m2_polyphony_audio_backend #(
    parameter integer N=32, SW=$clog2(N), TW=72+SW,
    parameter integer WAVE_RESPONSE_CYCLES=1, FRAME_LIMIT=833,
    parameter WAVE_FILE="rom/piano_band_4x256_8191.mem",
    parameter TRIANGLE_FILE="rom/triangle_wavetable.hex",
    parameter OCT_FILE="rom/oct_ratio_q16.mem",
    parameter SUB_FILE="rom/sub_ratio_q16.mem",
    parameter LFO_FILE="rom/lfo_sine_q15.mem"
) (
    input wire clk,rst_n,cancel,
    input wire events_valid,
    output wire events_ready,
    input wire [N-1:0] note_on,note_off,
    input wire [N*10-1:0] velocity,
    input wire [N*32-1:0] base_fcw,event_base_fcw,
    input wire [N*12-1:0] bend,modulation,
    input wire [N*5-1:0] pitch_range,
    input wire [N-1:0] occupied,timbres,
    input wire [N*4-1:0] sources,channels,
    input wire [N*32-1:0] generations,
    input wire request_valid,layer_both,
    output wire request_ready,
    input wire [31:0] request_id,
    output logic result_valid,
    input wire result_ready,
    output logic [31:0] result_id,
    output logic [N*4-1:0] result_sources,result_channels,
    output logic [N*32-1:0] result_generations,
    output logic signed [23:0] pcm_left,pcm_right,
    output logic signed [31:0] piano_pcm,organ_pcm,
    output logic clipped,deadline_missed,
    output logic [N-1:0] completed_mask,
    output wire advance_pulse,engine_empty,
    output logic lane_valid,
    output logic [SW-1:0] lane_slot,
    output logic lane_timbre,
    output logic signed [15:0] lane_wave,
    output logic [15:0] lane_envelope,
    output logic signed [23:0] lane_pcm,
    output logic [31:0] lane_phase,lane_triangle_phase,lane_fcw,
    output logic [1:0] lane_table,
    output wire [N*32-1:0] computed_fcw,
    output wire [N*16-1:0] live_envelopes,
    output wire [N*3-1:0] live_states,
    output wire [N*32-1:0] piano_phases,triangle_phases
);
    localparam [3:0] IDLE=0,PITCH=1,ADVANCE=2,SETTLE=3,ROM_START=4,
        ROM_WAIT=5,GAIN=6,ACCUM=7,OUTPUT_HOLD=8,DRAIN=9;
    logic [3:0] state;
    // Same-cycle ADVANCE qualifier without decoding the FSM at every lane.
    (* syn_keep=1 *) logic advance_pending;
    logic [SW-1:0] cursor;
    logic [7:0] wait_count,rom_inflight;
    logic [31:0] age;
    logic killed,rom_qualified;
    logic [N-1:0] held_occupied,held_timbres;
    logic [N*32-1:0] held_base,fcw_values;
    logic [N*16-1:0] held_envelopes;
    (* syn_keep=1, syn_dont_touch=1 *) wire [N*16-1:0] envelopes_capture;
    logic [31:0] phase_acc [0:N-1];
    logic [31:0] triangle_phase [0:N-1],triangle_sample_phase [0:N-1];
    logic [10:0] attack_left [0:N-1];
    logic [1:0] active_table [0:N-1],pending_table [0:N-1];
    logic table_pending [0:N-1];
    // Both path observations finish after cancel too. They do not own tokens.
    logic signed [15:0] piano_hold [0:N-1],triangle_hold [0:N-1];
    wire [N*32-1:0] pitch_values;
    wire pitch_ready,pitch_busy,pitch_done;
    wire envelope_busy,envelope_done;
    wire accepted=request_valid && request_ready;
    wire accepted_event=events_valid && events_ready;
    assign request_ready=!cancel && state==IDLE &&
        !events_valid && !envelope_busy;
    assign events_ready=!cancel && state==IDLE && !envelope_busy;
    assign advance_pulse=advance_pending && !cancel;
    assign computed_fcw=fcw_values;
    assign engine_empty=state==IDLE && !pitch_busy && !envelope_busy &&
        rom_inflight==0 && !result_valid;
    wire [N-1:0] on_pulse=note_on & {N{accepted_event}};
    wire [N-1:0] off_pulse=note_off & {N{accepted_event}};

    // R18: R16/R17 exposed flattened envelope bit 38 as the sole remaining
    // audio hold endpoint.  Delay only that same-cycle capture bit; every bit
    // remains numerically identical and no envelope/sample latency is added.
    for(genvar env_hold_bit=0;env_hold_bit<N*16;env_hold_bit=env_hold_bit+1) begin:g_env_capture
        if(env_hold_bit==38) begin:g_hold
            (* syn_keep=1, syn_dont_touch=1 *) wire hold_l0,hold_l1;
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_hold_0(
                .I0(live_envelopes[env_hold_bit]),.F(hold_l0));
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_hold_1(
                .I0(hold_l0),.F(hold_l1));
            assign envelopes_capture[env_hold_bit]=hold_l1;
        end else begin:g_direct
            assign envelopes_capture[env_hold_bit]=live_envelopes[env_hold_bit];
        end
    end

    m2_polyphony_envelope_engine #(.N(N)) u_shared_envelope(
        .clk(clk),.rst_n(rst_n),
        .event_start(accepted_event),.note_on(note_on),.note_off(note_off),
        .velocity(velocity),.timbres(timbres),
        .sample_start(advance_pulse),.busy(envelope_busy),.done(envelope_done),
        .live_envelopes(live_envelopes),.live_states(live_states));

    for(genvar i=0;i<N;i++) begin:g_continuous
        assign piano_phases[32*i+:32]=phase_acc[i];
        assign triangle_phases[32*i+:32]=triangle_phase[i];
        // Events and sample ADVANCE are mutually exclusive. Keep the
        // incoming-event FCW out of the recurrent phase arithmetic cone.
        wire [31:0] event_fcw=event_base_fcw[32*i+:32];
        wire [31:0] sample_fcw=fcw_values[32*i+:32];
        // The unsigned carry is exactly the phase wrap. Reusing it avoids
        // chaining the phase adder to a second wide magnitude comparator.
        wire [32:0] phase_sum={1'b0,phase_acc[i]}+{1'b0,sample_fcw};
        wire [31:0] next_phase=phase_sum[31:0];
        wire wraps=phase_sum[32];
        // synthesis translate_off
        always @(posedge clk) if(rst_n && advance_pulse)
            if(wraps !== (next_phase<phase_acc[i]))
                $fatal(1,"unsigned phase wrap mismatch");
        // synthesis translate_on
        wire [1:0] sample_body=sample_fcw<=32'd134217728 ? 1 :
            sample_fcw<=32'd268435456 ? 2 : 3;
        wire [1:0] event_body=event_fcw<=32'd134217728 ? 1 :
            event_fcw<=32'd268435456 ? 2 : 3;
        wire [1:0] event_attack=event_fcw<=32'd134217728 ? 0 :
            event_fcw<=32'd268435456 ? 1 : event_fcw<=32'd536870912 ? 2 : 3;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) begin
                phase_acc[i]<=0;triangle_phase[i]<=0;triangle_sample_phase[i]<=0;
                attack_left[i]<=0;active_table[i]<=3;pending_table[i]<=3;table_pending[i]<=0;
            end else begin
                if(on_pulse[i]) begin
                    attack_left[i]<=velocity[10*i+:10]>=768 ? 1440 :
                        velocity[10*i+:10]>=512 ? 960 : velocity[10*i+:10]>=256 ? 480 : 0;
                    active_table[i]<=velocity[10*i+:10]>=256 ? event_attack : event_body;
                    table_pending[i]<=0;
                end
                if(advance_pulse) begin
                    phase_acc[i]<=next_phase;
                    triangle_sample_phase[i]<=triangle_phase[i];
                    triangle_phase[i]<=triangle_phase[i]+sample_fcw;
                end
                if(!on_pulse[i] && advance_pulse) begin
                    if(table_pending[i] && wraps) begin
                        active_table[i]<=pending_table[i];table_pending[i]<=0;
                    end else if(attack_left[i]!=0) begin
                        attack_left[i]<=attack_left[i]-1'b1;
                        if(attack_left[i]==1) begin
                            if(wraps) active_table[i]<=sample_body;
                            else begin pending_table[i]<=sample_body;table_pending[i]<=1;end
                        end
                    end
                end
            end
        end
    end

    // One arithmetic/ROM pitch pipeline services all voices. Per-voice LFO
    // phase remains independent inside the engine. Serial launch completes in
    // at most N+7 clocks, preserving the 833-clock frame deadline at N=32.
    m2_polyphony_pitch_engine #(.N(N),.SW(SW),.OCT_FILE(OCT_FILE),
        .SUB_FILE(SUB_FILE),.LFO_FILE(LFO_FILE)) u_shared_pitch(
        .clk(clk),.rst_n(rst_n),.start(accepted),.start_ready(pitch_ready),
        .busy(pitch_busy),.done(pitch_done),.note_on(on_pulse),
        .occupied(occupied),.base_fcw(base_fcw),.bend(bend),
        .modulation(modulation),.pitch_range(pitch_range),
        .fcw_values(pitch_values));

    // One port per shared bank, one lane address pair at a time. READ latency1.
    // RESPONSE adds explicit response holding; it is not vendor primitive latency.
    wire [9:0] piano_addr={active_table[cursor],phase_acc[cursor][31:24]};
    // Bright Octave uses the same four-bank FCW split as the accepted R18
    // organ_dds_oscillator. Registering/capturing the phase per lane above
    // keeps this address path shallow and preserves the pre-advance sample.
    wire [31:0] secondary_fcw=fcw_values[32*cursor+:32];
    wire [1:0] secondary_bank=secondary_fcw<32'd134217728 ? 2'd0 :
        secondary_fcw<32'd268435456 ? 2'd1 :
        secondary_fcw<32'd536870912 ? 2'd2 : 2'd3;
    wire [9:0] triangle_addr={secondary_bank,triangle_sample_phase[cursor][31:24]};
    wire [TW-1:0] rom_tag={result_id,result_sources[4*cursor+:4],
        result_channels[4*cursor+:4],result_generations[32*cursor+:32],cursor};
    wire [TW-1:0] rom_response_tag;
    wire rom_valid;
    wire signed [15:0] piano_q,triangle_q;
    m2_polyphony_rom #(.TAG_BITS(TW),.PIANO_FILE(WAVE_FILE),
        .TRIANGLE_FILE(TRIANGLE_FILE)) wave_storage(
        .clk(clk),.rst_n(rst_n),.ce(state==ROM_START),
        .piano_addr(piano_addr),.triangle_addr(triangle_addr),.tag_in(rom_tag),
        .valid(rom_valid),.tag_out(rom_response_tag),
        .piano_data(piano_q),.triangle_data(triangle_q));
    wire signed [15:0] organ_wave=secondary_fcw[31] ? 16'sd0 : triangle_q;
    wire signed [15:0] chosen_wave=held_timbres[cursor] ? organ_wave : piano_q;
    wire signed [15:0] layered_wave=held_timbres[cursor] ? piano_q : organ_wave;
    logic held_layer_both;
    logic signed [15:0] layered_wave_q;
    logic signed [16:0] layered_env_q;
    logic signed [23:0] layered_pcm;
    wire signed [16:0] positive_env=$signed({1'b0,held_envelopes[16*cursor+:16]});
    wire signed [32:0] product=chosen_wave*positive_env;
    wire signed [32:0] scaled_floor=product>>>15;
    wire signed [32:0] layered_product=layered_wave_q*layered_env_q;
    wire signed [32:0] layered_floor=layered_product>>>15;
    logic signed [31:0] accumulator,piano_accumulator,organ_accumulator;
    wire signed [31:0] voice_extended={{8{lane_pcm[23]}},lane_pcm};
    wire signed [31:0] total=accumulator+voice_extended;
    // ACCUM uses the same cursor as the preceding GAIN, including the last lane.
    // The layer uses the same key/velocity/envelope owner as the primary
    // waveform. Existing independent piano and organ phase states are reused.
    wire signed [31:0] layered_extended={{8{layered_pcm[23]}},layered_pcm};
    wire signed [31:0] piano_total=piano_accumulator+(lane_timbre ? layered_extended : voice_extended);
    wire signed [31:0] organ_total=organ_accumulator+(lane_timbre ? voice_extended : layered_extended);
    function automatic [23:0] saturated(input logic signed [31:0] value);
        if(value>32'sd8388607) saturated=24'h7fffff;
        else if(value< -32'sd8388608) saturated=24'h800000;
        else saturated=value[23:0];
    endfunction
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin rom_inflight<=0;end
        else begin
            if(state==ROM_START) rom_inflight<=WAVE_RESPONSE_CYCLES;
            else if(rom_inflight!=0) rom_inflight<=rom_inflight-1'b1;
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            advance_pending<=0;
            state<=IDLE;cursor<=0;wait_count<=0;age<=0;killed<=0;rom_qualified<=0;
            held_occupied<=0;held_timbres<=0;held_base<=0;fcw_values<=0;held_envelopes<=0;
            result_valid<=0;result_id<=0;result_sources<=0;result_channels<=0;
            result_generations<=0;pcm_left<=0;pcm_right<=0;clipped<=0;
            piano_pcm<=0;organ_pcm<=0;piano_accumulator<=0;organ_accumulator<=0;
            deadline_missed<=0;completed_mask<=0;accumulator<=0;
            held_layer_both<=0;layered_pcm<=0;
            layered_wave_q<=0;layered_env_q<=0;
            lane_valid<=0;lane_slot<=0;lane_timbre<=0;lane_wave<=0;lane_envelope<=0;
            lane_pcm<=0;lane_phase<=0;lane_triangle_phase<=0;lane_fcw<=0;lane_table<=3;
            for(integer j=0;j<N;j++) begin piano_hold[j]<=0;triangle_hold[j]<=0;end
        end else begin
            advance_pending<=0;
            lane_valid<=0;
            if(state!=IDLE && state!=OUTPUT_HOLD && state!=DRAIN) age<=age+1'b1;
            if(cancel) killed<=1;
            if(rom_valid) rom_qualified<=1;
            case(state)
                IDLE:if(accepted) begin
                    killed<=0;rom_qualified<=0;
                    held_layer_both<=layer_both;
                    held_occupied<=occupied;held_timbres<=timbres;held_base<=base_fcw;
                    result_id<=request_id;result_sources<=sources;
                    result_channels<=channels;result_generations<=generations;
                    age<=0;completed_mask<=0;accumulator<=0;deadline_missed<=0;
                    piano_accumulator<=0;organ_accumulator<=0;
                    state<=PITCH;
                end
                PITCH:if(killed || cancel) state<=DRAIN;
                    else if(pitch_done) begin
                        for(integer k=0;k<N;k++)
                            fcw_values[32*k+:32]<=held_occupied[k] ?
                                pitch_values[32*k+:32] : held_base[32*k+:32];
                        advance_pending<=1;
                        state<=ADVANCE;
                    end
                ADVANCE:if(killed || cancel) state<=DRAIN;
                    else begin wait_count<=4;state<=SETTLE;end
                // After ADVANCE, finish ALL hidden path updates even if killed.
                SETTLE:if(wait_count!=0) wait_count<=wait_count-1'b1;
                    else if(!envelope_busy) begin
                        held_envelopes<=envelopes_capture;cursor<=0;state<=ROM_START;
                    end
                ROM_START:begin
                    rom_qualified<=0;wait_count<=WAVE_RESPONSE_CYCLES;state<=ROM_WAIT;
                end
                ROM_WAIT:if(wait_count!=1) wait_count<=wait_count-1'b1;
                    else begin
                        layered_wave_q<=(held_layer_both && held_occupied[cursor]) ?
                            layered_wave : 16'sd0;
                        layered_env_q<=positive_env;
                        state<=GAIN;
                    end
                GAIN:begin
                    piano_hold[cursor]<=piano_q;triangle_hold[cursor]<=triangle_q;
                    lane_valid<=!killed && !cancel;lane_slot<=cursor;
                    lane_timbre<=held_timbres[cursor];lane_wave<=chosen_wave;
                    lane_envelope<=held_envelopes[16*cursor+:16];
                    lane_phase<=phase_acc[cursor];lane_triangle_phase<=triangle_sample_phase[cursor];
                    lane_table<=active_table[cursor];lane_fcw<=fcw_values[32*cursor+:32];
                    lane_pcm<=held_occupied[cursor] ? {scaled_floor[15:0],8'b0} : 24'd0;
                    layered_pcm<={layered_floor[15:0],8'b0};
                    completed_mask[cursor]<=1;state<=ACCUM;
                end
                ACCUM:begin
                    accumulator<=total;
                    piano_accumulator<=piano_total;organ_accumulator<=organ_total;
                    if(cursor==N-1) begin
                        if(killed || cancel) begin result_valid<=0;state<=DRAIN;end
                        else begin
                            pcm_left<=saturated(total);pcm_right<=saturated(total);
                            piano_pcm<=piano_total;organ_pcm<=organ_total;
                            clipped<=total>32'sd8388607 || total< -32'sd8388608;
                            deadline_missed<=age+1>=FRAME_LIMIT;
                            result_valid<=1;state<=OUTPUT_HOLD;
                        end
                    end else begin cursor<=cursor+1'b1;state<=ROM_START;end
                end
                OUTPUT_HOLD:if(killed || cancel) begin result_valid<=0;state<=DRAIN;end
                    else if(result_valid && result_ready) begin result_valid<=0;state<=IDLE;end
                DRAIN:if(!pitch_busy && !envelope_busy && rom_inflight==0) state<=IDLE;
                default:begin result_valid<=0;killed<=1;state<=DRAIN;end
            endcase
        end
    end
    // synthesis translate_off
    initial begin
        if(!(N==4 || N==8 || N==16 || N==32)) $fatal(1,"POLY_N_NOT_SUPPORTED");
        if(WAVE_RESPONSE_CYCLES<1 || WAVE_RESPONSE_CYCLES>64)
            $fatal(1,"POLY_BAD_ROM_HOLD_BOUND");
        if(SW!=$clog2(N) || TW!=72+SW) $fatal(1,"POLY_TAG_WIDTH");
    end
    always @(posedge clk) if(rst_n) begin
        if (advance_pulse !== (!cancel && !killed && state==ADVANCE))
            $fatal(1,"ADVANCE_PULSE_FENCE_MISMATCH");
        if(accepted && !pitch_ready) $fatal(1,"POLY_PITCH_NOT_READY");
        if(state==GAIN && (!rom_qualified || rom_response_tag!==rom_tag))
            $fatal(1,"POLY_ROM_RESPONSE_IDENTITY");
        if(state==GAIN && held_envelopes[16*cursor+:16]>32767)
            $fatal(1,"POLY_ENV_OUTSIDE_Q15");
    end
    // synthesis translate_on
endmodule
