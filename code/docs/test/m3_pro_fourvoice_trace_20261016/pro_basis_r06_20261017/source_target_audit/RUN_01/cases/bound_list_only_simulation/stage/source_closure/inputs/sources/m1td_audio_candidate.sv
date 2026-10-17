// Isolated four-voice mixed stereo producer, 40 MHz / 48 kHz contract.
// Event/ROM/math definitions are copied frozen dependencies, never edited in place.
// Request IDs and frame cancellation are supplied by M2's eventual frame buffer.
// No I2S/board ports, no clip commit counter: clipped metadata belongs to this result.
module m1td_audio_candidate (
    input logic clk, rst_n, event_valid, frame_tick, sample_req,
    input logic [63:0] event_data,
    input logic [31:0] sample_req_id,
    output wire event_ready, calc_ready,
    output wire result_valid,
    input logic result_ready,
    output logic [31:0] result_id,
    output logic signed [23:0] result_left, result_right,
    output logic clipped_left, clipped_right,
    output wire [31:0] active_voice_count
);
    wire bank_valid, bank_ready;
    wire [31:0] bank_id;
    wire [63:0] envelopes, waves;
    wire [3:0] occupied;
    wire [95:0] voices;
    wire signed [23:0] mixed_left, mixed_right;
    wire mix_clip_left, mix_clip_right;
    m1td_polyphonic_envelope_bank #(.WAVE_ROM_FILE("rom/piano_band_4x256_8191.mem"))u_bank(
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .frame_tick(frame_tick),.sample_req(sample_req),.sample_req_id(sample_req_id),.calc_ready(calc_ready),
        .result_valid(bank_valid),.result_ready(bank_ready),.result_req_id(bank_id),
        .result_envelopes(envelopes),.result_waves(waves),.result_fcw(),.result_occupied(occupied),
        .result_states(),.active_voice_count(active_voice_count));
    for(genvar i=0;i<4;i++)begin:g_gain
        wire signed [23:0] pcm;
        m1td_voice_gain_q15_candidate u_gain(.wave_sample($signed(waves[16*i+:16])),
            .envelope(envelopes[16*i+:16]),.sample_out(),.pcm_out(pcm));
        assign voices[24*i+:24]=occupied[i] ? pcm : 24'd0;
    end
    m1td_pcm_mixer_4voice u_mix(.voices_left(voices),.voices_right(voices),
        .mixed_left(mixed_left),.mixed_right(mixed_right),.clip_left(mix_clip_left),
        .clip_right(mix_clip_right),.clip_any());
    logic request_window,held_valid;
    assign result_valid=rst_n && !frame_tick && held_valid && result_id==sample_req_id;
    assign bank_ready=rst_n && request_window && !frame_tick && !held_valid && bank_id==sample_req_id;
    always_ff @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            request_window<=0;held_valid<=0;result_id<=0;result_left<=0;result_right<=0;
            clipped_left<=0;clipped_right<=0;
        end else if(frame_tick)begin
            request_window<=1;held_valid<=0;
        end else if(result_valid && result_ready)begin
            held_valid<=0;
        end else if(bank_valid && bank_ready)begin
            request_window<=0;held_valid<=1;result_id<=bank_id;
            result_left<=mixed_left;result_right<=mixed_right;
            clipped_left<=mix_clip_left;clipped_right<=mix_clip_right;
        end
    end
endmodule
