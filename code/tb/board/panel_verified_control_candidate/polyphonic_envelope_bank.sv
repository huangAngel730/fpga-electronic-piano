// T024 M2 four-lane DDS/ADSR lifecycle and sample-generation scheduler.
// No waveform scaling or PCM arithmetic; M1 ADSR and allocator are unchanged.
// All logic uses clk. rst_n: async assert, synchronously released upstream.
// frame_tick cancels an old generation. One accepted sample_req causes at most
// one lane_tick. Cancelling a computed result does not roll back DSP state.
module polyphonic_envelope_bank #(
    parameter integer PIANO_TIMBRE_ENABLE = 0,
    parameter bit DYNAMIC_TIMBRE_ENABLE = 1'b0,
    parameter bit PANEL_TIMBRE_ENABLE = 1'b0,
    parameter SINE_ROM_FILE = "model/generated/sine_wavetable.hex",
    parameter TRIANGLE_ROM_FILE = "model/generated/triangle_wavetable.hex",
    parameter WAVE_ROM_FILE = "model/generated/wavetables/sine_1024_32767.mem"
) (
    input logic clk, rst_n,
    input logic event_valid,
    output wire event_ready,
    input logic [63:0] event_data,
    input logic frame_tick, sample_req,
    input logic [31:0] sample_req_id,
    output wire calc_ready,
    output logic result_valid,
    input logic result_ready,
    output logic [31:0] result_req_id,
    output logic [63:0] result_envelopes,
    output logic [63:0] result_waves,
    output logic [127:0] result_fcw,
    output logic [3:0] result_occupied,
    output logic [11:0] result_states,
    output wire [31:0] active_voice_count
);
    localparam logic [2:0] IDLE=0, WAIT_DISPATCH=1, SETTLE=2,
                           ADVANCE=3, SNAPSHOT=4, HOLD=5;
    logic [2:0] phase;
    logic [2:0] delay_count;
    logic [31:0] pending_req_id;
    wire dispatch_busy;
    wire [3:0] slot_note_on, slot_note_off, slot_occupied, slot_releasing;
    wire [39:0] slot_velocity;
    wire [127:0] slot_fcw;
    wire [31:0] slot_notes;
    wire [3:0] slot_timbre;
    wire [63:0] envelopes;
    wire [63:0] waves;
    wire [11:0] states;
    wire [3:0] release_done;
    wire lane_tick = rst_n && !frame_tick && phase==ADVANCE;
    // Allow a new frame to cancel a blocked previous result and request again.
    assign calc_ready = rst_n && (phase==IDLE || frame_tick);
    polyphonic_event_router #(.DYNAMIC_TIMBRE_ENABLE(DYNAMIC_TIMBRE_ENABLE),
        .PANEL_TIMBRE_ENABLE(PANEL_TIMBRE_ENABLE)) u_events (
        .clk(clk),.rst_n(rst_n),
        .sample_owner_ready(phase==IDLE && !sample_req && !frame_tick && !result_valid),
        .event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .release_done(release_done),.dispatch_busy(dispatch_busy),
        .slot_note_on(slot_note_on),.slot_note_off(slot_note_off),
        .slot_occupied(slot_occupied),.slot_releasing(slot_releasing),
        .slot_velocity(slot_velocity),.slot_fcw(slot_fcw),.slot_notes(slot_notes),.slot_timbre(slot_timbre),
        .active_voice_count(active_voice_count)
    );
    for(genvar i=0;i<4;i=i+1) begin:g_lane
        if(DYNAMIC_TIMBRE_ENABLE) begin:g_t027
            piano_triangle_voice #(.PIANO_ROM_FILE(WAVE_ROM_FILE),
                .SINE_ROM_FILE(SINE_ROM_FILE),.TRIANGLE_ROM_FILE(TRIANGLE_ROM_FILE)) u_dds (
                .clk(clk),.rst_n(rst_n),.sample_tick(lane_tick),
                .fcw(slot_fcw[32*i+:32]),.velocity(slot_velocity[10*i+:10]),
                .timbre_triangle(slot_timbre[i]),
                .note_on(slot_note_on[i]),.note_off(slot_note_off[i]),
                .wt_sample(waves[16*i+:16])
            );
        end else if(PIANO_TIMBRE_ENABLE) begin:g_piano
            piano_dds_oscillator #(.ROM_FILE(WAVE_ROM_FILE)) u_dds (
                .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(lane_tick),
                .note_on(slot_note_on[i]),.velocity(slot_velocity[10*i+:10]),
                .fcw(slot_fcw[32*i+:32]),.wt_sample(waves[16*i+:16])
            );
        end else begin:g_sine
            dds_oscillator #(.ROM_FILE(WAVE_ROM_FILE)) u_dds (
                .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(lane_tick),
                .fcw(slot_fcw[32*i+:32]),.wt_sample(waves[16*i+:16])
            );
        end
        adsr_piano_envelope u_envelope (
            .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(lane_tick),
            .note_on(slot_note_on[i]),.note_off(slot_note_off[i]),
            .velocity(slot_velocity[10*i+:10]),
            .envelope_level(envelopes[16*i+:16]),.state_out(states[3*i+:3])
        );
        // A held but naturally silent note still has an identity until Note Off.
        // If its envelope is already IDLE, Note Off retires it without waiting
        // for a non-existent Release->IDLE transition.
        assign release_done[i] = rst_n && slot_occupied[i] && slot_releasing[i] &&
                                 states[3*i+:3]==0 && !slot_note_on[i];
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            phase<=IDLE;delay_count<=0;pending_req_id<=0;
            result_valid<=0;result_req_id<=0;result_envelopes<=0;result_waves<=0;
            result_fcw<=0;result_occupied<=0;result_states<=0;
        end else if(frame_tick) begin
            phase<=IDLE;result_valid<=0;
        end else begin
            case(phase)
                IDLE: if(sample_req) begin
                    pending_req_id<=sample_req_id;phase<=WAIT_DISPATCH;
                end
                WAIT_DISPATCH: if(!dispatch_busy && !(|slot_note_on) && !(|slot_note_off)) begin
                    delay_count<=3;phase<=SETTLE;
                end
                SETTLE: if(delay_count==0) phase<=ADVANCE;
                        else delay_count<=delay_count-1'b1;
                ADVANCE: begin phase<=SNAPSHOT;delay_count<= DYNAMIC_TIMBRE_ENABLE ? 4 : 2;end
                SNAPSHOT: if(delay_count==0) begin
                    result_req_id<=pending_req_id;result_envelopes<=envelopes;
                    result_waves<=waves;
                    result_fcw<=slot_fcw;result_occupied<=slot_occupied;
                    result_states<=states;result_valid<=1;phase<=HOLD;
                end else delay_count<=delay_count-1'b1;
                HOLD: if(result_valid && result_ready) begin result_valid<=0;phase<=IDLE;end
                default: begin phase<=IDLE;result_valid<=0;end
            endcase
        end
    end
endmodule