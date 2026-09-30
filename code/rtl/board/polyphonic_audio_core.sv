// T024 approved v1.5 arithmetic -> stereo mixer -> frame commit.
// SOURCE waveform ROM is explicitly 8192 peak; no rescaling of 32767 ROM.
// All stages in clk domain. Result waves/envelopes/ID stable until handshake.
module polyphonic_audio_core (
    input logic clk,rst_n,event_valid,frame_tick,
    input logic [63:0] event_data,
    output wire event_ready,
    output wire signed [23:0] play_left,play_right,
    output wire pending_valid,
    output wire [31:0] active_voice_count,clip_count,audio_underrun,
    output wire [31:0] audio_frame_count,pcm_request_count,pcm_commit_count,
    output wire [31:0] max_processing_cycles
);
    wire sample_req,calc_ready,bank_valid,bank_ready;
    wire [31:0] sample_req_id,bank_id;
    wire [63:0] bank_envelopes,bank_waves;
    wire [127:0] bank_fcw;
    wire [3:0] bank_occupied;
    wire [11:0] bank_states;
    wire [95:0] voices;
    polyphonic_envelope_bank #(.WAVE_ROM_FILE("model/generated/wavetables/sine_1024_8192.mem")) u_bank (
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .frame_tick(frame_tick),.sample_req(sample_req),.sample_req_id(sample_req_id),.calc_ready(calc_ready),
        .result_valid(bank_valid),.result_ready(bank_ready),.result_req_id(bank_id),
        .result_envelopes(bank_envelopes),.result_waves(bank_waves),.result_fcw(bank_fcw),
        .result_occupied(bank_occupied),.result_states(bank_states),.active_voice_count(active_voice_count)
    );
    for(genvar i=0;i<4;i++) begin:g_gain
        wire signed [15:0] scaled;
        wire signed [23:0] pcm;
        voice_gain_q15_candidate u_gain(.wave_sample($signed(bank_waves[16*i+:16])),
            .envelope(bank_envelopes[16*i+:16]),.sample_out(scaled),.pcm_out(pcm));
        assign voices[24*i+:24]=bank_occupied[i] ? pcm : 24'd0;
    end
    polyphonic_pcm_commit u_commit(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .sample_req(sample_req),.sample_req_id(sample_req_id),.result_valid(bank_valid),
        .result_ready(bank_ready),.result_req_id(bank_id),.voices_left(voices),.voices_right(voices),
        .play_left(play_left),.play_right(play_right),.pending_valid(pending_valid),
        .audio_frame_count(audio_frame_count),.pcm_request_count(pcm_request_count),
        .pcm_commit_count(pcm_commit_count),.audio_underrun(audio_underrun),.clip_count(clip_count)
    );
    wire [31:0] unused_overflow;
    system_status_counters u_latency(.clk(clk),.rst_n(rst_n),.pcm_request(sample_req),
        .pcm_commit(u_commit.pcm_valid && u_commit.pcm_ready),.button_overflow(32'd0),.midi_overflow(32'd0),
        .event_fifo_overflow(unused_overflow),.max_processing_cycles(max_processing_cycles));
endmodule