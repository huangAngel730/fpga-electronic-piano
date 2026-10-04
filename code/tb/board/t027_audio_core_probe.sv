// Internal standalone STA harness; no board pins, no downloadable bitstream.
// Dynamic selection is private and disabled by default in formal core.
module t027_audio_core_probe (
    input logic clk, rst_n, event_valid, frame_tick,
    input logic [63:0] event_data,
    input logic [3:0] view,
    output wire event_ready,
    output logic [31:0] observed
);
    wire signed [23:0] play_left, play_right;
    wire pending_valid;
    wire [31:0] active_voice_count, clip_count, audio_underrun;
    wire [31:0] audio_frame_count, pcm_request_count, pcm_commit_count;
    wire [31:0] max_processing_cycles;
    polyphonic_audio_core #(.DYNAMIC_TIMBRE_ENABLE(1'b1),
        .WAVE_ROM_FILE("model/generated/wavetables/piano_band_4x256_8191.mem")) u_core (.*);
    always_comb begin
        case(view)
            0: observed = {{8{play_left[23]}}, play_left};
            1: observed = {{8{play_right[23]}}, play_right};
            2: observed = active_voice_count;
            3: observed = clip_count;
            4: observed = audio_underrun;
            5: observed = pcm_commit_count;
            6: observed = pcm_request_count;
            7: observed = audio_frame_count;
            8: observed = max_processing_cycles;
            9: observed = {31'd0,pending_valid};
            default: observed = 32'd0;
        endcase
    end
endmodule
