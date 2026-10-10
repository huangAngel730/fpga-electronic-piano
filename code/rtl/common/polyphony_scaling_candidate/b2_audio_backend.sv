// D043/D044 independent B2a hybrid math backend, NOT a MIDI voice allocator.
// clk only; asynchronous active-low whole-domain reset (release is upstream).
// Preserve per-lane continuous frozen ADSR/Pitch pipelines; share ONLY the
// piano wave ROM, signed gain multiplier and serial signed32 accumulation.
// Events accepted only idle; request captures all controls/identities atomically.
// cancel discards the token/output, NEVER rolls back DDS/ADSR/LFO advancement.
module b2_audio_backend #(
    parameter integer N = 4,
    parameter integer WAVE_RESPONSE_CYCLES = 1,
    parameter WAVE_FILE = "E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/piano_band_4x256_8191.mem",
    parameter OCT_FILE = "E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/oct_ratio_q16.mem",
    parameter SUB_FILE = "E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/sub_ratio_q16.mem",
    parameter LFO_FILE = "E:/FPGA/GAOYUNFPGA/team/fpga-electronic-piano/code/rtl/138K_try/hold_trials_20261005/L_locations_guard065/rom/lfo_sine_q15.mem",
    parameter integer SW = $clog2(N)
) (
    input wire clk, rst_n, cancel,
    input wire events_valid,
    output wire events_ready,
    input wire [N-1:0] note_on, note_off,
    input wire [N*10-1:0] velocity,
    input wire [N*32-1:0] base_fcw,
    input wire [N*12-1:0] bend, modulation,
    input wire [N*5-1:0] pitch_range,
    input wire [N-1:0] occupied,
    input wire [N*4-1:0] sources, channels,
    input wire [N*32-1:0] generations,
    input wire request_valid,
    output wire request_ready,
    input wire [31:0] request_id,
    output logic result_valid,
    input wire result_ready,
    output logic [31:0] result_id,
    output logic [N*4-1:0] result_sources, result_channels,
    output logic [N*32-1:0] result_generations,
    output logic signed [23:0] pcm_left, pcm_right,
    output logic clipped, deadline_missed,
    output logic [N-1:0] completed_mask,
    output wire advance_pulse, engine_empty,
    // Public verification/adapter taps, not hierarchical register peeking.
    output logic lane_valid,
    output logic [SW-1:0] lane_slot,
    output logic signed [15:0] lane_wave,
    output logic [15:0] lane_envelope,
    output logic signed [23:0] lane_pcm,
    output logic [31:0] lane_phase, lane_fcw,
    output logic [1:0] lane_table,
    output wire [N*32-1:0] computed_fcw,
    output wire [N*16-1:0] live_envelopes,
    output wire [N*3-1:0] live_states
);
    localparam [3:0] IDLE=0, PITCH=1, ADVANCE=2, SETTLE=3,
        ROM_START=4, ROM_WAIT=5, GAIN=6, ACCUM=7, OUTPUT_HOLD=8, DRAIN=9;
    logic [3:0] state;
    logic [SW-1:0] cursor;
    logic [7:0] wait_count, pitch_inflight, rom_inflight;
    logic [31:0] age;
    logic [N-1:0] held_occupied;
    logic [N*32-1:0] held_base;
    logic [N*32-1:0] fcw_values;
    logic [N*16-1:0] held_envelopes;
    logic [31:0] phase_acc [0:N-1];
    logic [10:0] attack_left [0:N-1];
    logic [1:0] active_table [0:N-1], pending_table [0:N-1];
    logic table_pending [0:N-1];
    wire [N-1:0] pitch_valid;
    wire [N*32-1:0] pitch_values;
    wire accepted = request_valid && request_ready;
    wire accepted_event = events_valid && events_ready;
    assign request_ready = rst_n && !cancel && state==IDLE && !events_valid;
    assign events_ready = rst_n && !cancel && state==IDLE;
    assign advance_pulse = rst_n && !cancel && state==ADVANCE;
    assign computed_fcw = fcw_values;
    assign engine_empty = state==IDLE && pitch_inflight==0 &&
        rom_inflight==0 && !(|pitch_valid) && !result_valid;
    wire [N-1:0] on_pulse = note_on & {N{accepted_event}};
    wire [N-1:0] off_pulse = note_off & {N{accepted_event}};

    for(genvar i=0;i<N;i=i+1) begin:g_continuous
        adsr_piano_envelope u_adsr(
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(advance_pulse),
            .note_on(on_pulse[i]),.note_off(off_pulse[i]),
            .velocity(velocity[10*i+:10]),
            .envelope_level(live_envelopes[16*i+:16]),.state_out(live_states[3*i+:3]));
        pitch_mod_fcw_pipeline #(.OCT_FILE(OCT_FILE),.SUB_FILE(SUB_FILE),.LFO_FILE(LFO_FILE)) u_pitch(
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_enable(accepted && occupied[i]),
            .note_on(on_pulse[i]),.bend($signed(bend[12*i+:12])),
            .modulation(modulation[12*i+:12]),.pitch_range(pitch_range[5*i+:5]),
            .base_fcw(base_fcw[32*i+:32]),.fcw_out(pitch_values[32*i+:32]),
            .fcw_valid(pitch_valid[i]));
        // Every lane advances at the SAME accepted sample edge. These arrays
        // are persistent DSP state, separate from B1's discardable token banks.
        wire [31:0] now_fcw = state==IDLE ? base_fcw[32*i+:32] : fcw_values[32*i+:32];
        wire [31:0] next_phase = phase_acc[i] + now_fcw;
        wire wraps = next_phase < phase_acc[i];
        wire [1:0] body = now_fcw<=32'd134217728 ? 1 : now_fcw<=32'd268435456 ? 2 : 3;
        wire [1:0] attack = now_fcw<=32'd134217728 ? 0 : now_fcw<=32'd268435456 ? 1 :
            now_fcw<=32'd536870912 ? 2 : 3;
        always_ff @(posedge clk or negedge rst_n) begin
            if(!rst_n) begin
                phase_acc[i]<=0;attack_left[i]<=0;active_table[i]<=3;
                pending_table[i]<=3;table_pending[i]<=0;
            end else begin
                if(on_pulse[i]) begin
                    attack_left[i]<=velocity[10*i+:10]>=768 ? 1440 :
                        velocity[10*i+:10]>=512 ? 960 : velocity[10*i+:10]>=256 ? 480 : 0;
                    active_table[i]<=velocity[10*i+:10]>=256 ? attack : body;
                    table_pending[i]<=0;
                end
                if(advance_pulse) phase_acc[i]<=next_phase;
                if(!on_pulse[i] && advance_pulse) begin
                    if(table_pending[i] && wraps) begin
                        active_table[i]<=pending_table[i];table_pending[i]<=0;
                    end else if(attack_left[i]!=0) begin
                        attack_left[i]<=attack_left[i]-1'b1;
                        if(attack_left[i]==1) begin
                            if(wraps) active_table[i]<=body;
                            else begin pending_table[i]<=body;table_pending[i]<=1;end
                        end
                    end
                end
            end
        end
    end

    // One physical synchronous piano-ROM read. WAVE_RESPONSE_CYCLES models
    // downstream response holding, NOT a claim about the vendor RAM's latency.
    logic signed [15:0] wave_rom [0:1023];
    logic signed [15:0] wave_q;
    wire [9:0] wave_addr = {active_table[cursor],phase_acc[cursor][31:24]};
    initial $readmemh(WAVE_FILE,wave_rom);
    always_ff @(posedge clk) if(state==ROM_START && !cancel)
        wave_q<=wave_rom[wave_addr];
    wire signed [16:0] positive_env = $signed({1'b0,held_envelopes[16*cursor+:16]});
    wire signed [32:0] product = wave_q * positive_env;
    wire signed [32:0] scaled_floor = product >>> 15;
    logic signed [31:0] accumulator;
    wire signed [31:0] voice_extended = {{8{lane_pcm[23]}},lane_pcm};
    wire signed [31:0] total = accumulator + voice_extended;
    function automatic [23:0] saturated(input logic signed [31:0] value);
        if(value>32'sd8388607) saturated=24'h7fffff;
        else if(value< -32'sd8388608) saturated=24'h800000;
        else saturated=value[23:0];
    endfunction
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin pitch_inflight<=0;rom_inflight<=0;end
        else begin
            if(accepted && (|occupied)) pitch_inflight<=7;
            else if(pitch_inflight!=0) pitch_inflight<=pitch_inflight-1'b1;
            if(state==ROM_START && !cancel) rom_inflight<=WAVE_RESPONSE_CYCLES;
            else if(rom_inflight!=0) rom_inflight<=rom_inflight-1'b1;
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;cursor<=0;wait_count<=0;age<=0;
            held_occupied<=0;held_base<=0;fcw_values<=0;held_envelopes<=0;
            result_valid<=0;result_id<=0;result_sources<=0;result_channels<=0;
            result_generations<=0;pcm_left<=0;pcm_right<=0;clipped<=0;
            deadline_missed<=0;completed_mask<=0;accumulator<=0;
            lane_valid<=0;lane_slot<=0;lane_wave<=0;lane_envelope<=0;
            lane_pcm<=0;lane_phase<=0;lane_fcw<=0;lane_table<=3;
        end else begin
            lane_valid<=0;
            if(state!=IDLE && state!=OUTPUT_HOLD && state!=DRAIN) age<=age+1'b1;
            if(cancel) begin
                state<=DRAIN;result_valid<=0;
            end else case(state)
                IDLE: if(accepted) begin
                    held_occupied<=occupied;held_base<=base_fcw;
                    result_id<=request_id;result_sources<=sources;
                    result_channels<=channels;result_generations<=generations;
                    age<=0;completed_mask<=0;accumulator<=0;deadline_missed<=0;
                    wait_count<=7;state<=PITCH;
                end
                PITCH: if(wait_count!=1) wait_count<=wait_count-1'b1;
                    else begin
                        for(integer k=0;k<N;k=k+1)
                            fcw_values[32*k+:32]<=held_occupied[k] ? pitch_values[32*k+:32] : held_base[32*k+:32];
                        state<=ADVANCE;
                    end
                ADVANCE: begin wait_count<=4;state<=SETTLE;end
                SETTLE: if(wait_count!=0) wait_count<=wait_count-1'b1;
                    else begin held_envelopes<=live_envelopes;cursor<=0;state<=ROM_START;end
                ROM_START: begin wait_count<=WAVE_RESPONSE_CYCLES;state<=ROM_WAIT;end
                ROM_WAIT: if(wait_count!=1) wait_count<=wait_count-1'b1;else state<=GAIN;
                GAIN: begin
                    lane_valid<=1;lane_slot<=cursor;lane_wave<=wave_q;
                    lane_envelope<=held_envelopes[16*cursor+:16];
                    lane_phase<=phase_acc[cursor];lane_table<=active_table[cursor];
                    lane_fcw<=fcw_values[32*cursor+:32];
`ifdef B2_MUTANT_GAIN_ZERO
                    lane_pcm<=held_occupied[cursor] ?
                        {16'(product / 33'sd32768),8'b0} : 0;
`else
                    lane_pcm<=held_occupied[cursor] ? {scaled_floor[15:0],8'b0} : 0;
`endif
                    completed_mask[cursor]<=1;state<=ACCUM;
                end
                ACCUM: begin
                    accumulator<=total;
`ifdef B2_MUTANT_SKIP_LAST
                    if(cursor==N-2) begin
`else
                    if(cursor==N-1) begin
`endif
                        pcm_left<=saturated(total);pcm_right<=saturated(total);
                        clipped<=total>32'sd8388607 || total< -32'sd8388608;
                        deadline_missed<=age+1>=833;
                        result_valid<=1;state<=OUTPUT_HOLD;
                    end else begin cursor<=cursor+1'b1;state<=ROM_START;end
                end
                OUTPUT_HOLD: if(result_valid && result_ready) begin result_valid<=0;state<=IDLE;end
                DRAIN: if(pitch_inflight==0 && rom_inflight==0 && !(|pitch_valid)) state<=IDLE;
                default: begin result_valid<=0;state<=DRAIN;end
            endcase
        end
    end
    // synthesis translate_off
    initial begin
        if(!(N==4 || N==8 || N==16 || N==32)) $fatal(1,"N_NOT_SUPPORTED");
        if(WAVE_RESPONSE_CYCLES<1 || WAVE_RESPONSE_CYCLES>64) $fatal(1,"BAD_ROM_RESPONSE_BOUND");
        for(integer a=0;a<1024;a=a+1)
            if(^wave_rom[a]===1'bx) $fatal(1,"MISSING_PIANO_ROM_WORD");
    end
    always @(posedge clk) if(rst_n && state==PITCH && wait_count==1 && !cancel &&
        (pitch_valid & held_occupied)!=held_occupied) $fatal(1,"PITCH_RESULT_NOT_READY");
    // synthesis translate_on
endmodule
