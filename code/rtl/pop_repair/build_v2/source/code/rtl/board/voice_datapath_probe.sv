// M2 T024 resource/timing probe. NOT a playable piano voice.
// Four independent DDS + ADSR lanes -> existing 24-bit stereo mixer.
// The 32767 wavetable is reduced by two bits for a provisional probe only;
// this is NOT the frozen D028 8192-table PCM reference. No allocator, effects,
// event FIFO, frame IDs, I2S or UART are present. Never use its bitstream.
`timescale 1ns/1ps
module voice_datapath_probe #(
    parameter integer LANES = 1
) (
    input  logic         sys_clk,sys_rst_n,sample_tick,
    input  logic [3:0]   note_on,note_off,
    input  logic [39:0]  velocity,
    input  logic [127:0] fcw,
    output logic signed [23:0] pcm_left,pcm_right,
    output logic         clip_any,
    output logic [3:0]   lane_state_nonzero
);
    wire [95:0] lanes_left,lanes_right;
    wire clip_left,clip_right;
    for(genvar i=0;i<4;i=i+1) begin: g_lane
        if(i<LANES) begin: g_present
            wire signed [15:0] wavetable_sample;
            wire [15:0] envelope_level;
            wire [2:0] state_out;
            wire signed [31:0] amplitude_product;
            wire signed [23:0] provisional_voice;
            dds_oscillator u_dds (
                .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),
                .sample_tick(sample_tick),.fcw(fcw[32*i+:32]),
                .wt_sample(wavetable_sample)
            );
            adsr_piano_envelope u_adsr (
                .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),
                .sample_tick(sample_tick),.note_on(note_on[i]),
                .note_off(note_off[i]),.velocity(velocity[10*i+:10]),
                .envelope_level(envelope_level),.state_out(state_out)
            );
            assign amplitude_product = wavetable_sample * $signed({1'b0,envelope_level});
            assign provisional_voice = ($signed(amplitude_product) >>> 17) <<< 8;
            assign lanes_left[24*i+:24] = provisional_voice;
            assign lanes_right[24*i+:24] = -provisional_voice;
            assign lane_state_nonzero[i] = |state_out;
        end else begin: g_absent
            assign lanes_left[24*i+:24] = 24'd0;
            assign lanes_right[24*i+:24] = 24'd0;
            assign lane_state_nonzero[i] = 1'b0;
        end
    end
    pcm_mixer_4voice u_mixer (
        .voices_left(lanes_left),.voices_right(lanes_right),
        .mixed_left(pcm_left),.mixed_right(pcm_right),
        .clip_left(clip_left),.clip_right(clip_right),.clip_any(clip_any)
    );
`ifndef SYNTHESIS
    initial if(LANES<1 || LANES>4)$fatal(1,"LANES must be 1..4");
`endif
endmodule

module voice_datapath_probe_1 (
    input  logic sys_clk,sys_rst_n,sample_tick,
    input  logic [3:0] note_on,note_off,
    input  logic [39:0] velocity,
    input  logic [127:0] fcw,
    output logic signed [23:0] pcm_left,pcm_right,
    output logic clip_any,
    output logic [3:0] lane_state_nonzero
);
    voice_datapath_probe #(.LANES(1)) u_probe (.*);
endmodule

module voice_datapath_probe_4 (
    input  logic sys_clk,sys_rst_n,sample_tick,
    input  logic [3:0] note_on,note_off,
    input  logic [39:0] velocity,
    input  logic [127:0] fcw,
    output logic signed [23:0] pcm_left,pcm_right,
    output logic clip_any,
    output logic [3:0] lane_state_nonzero
);
    voice_datapath_probe #(.LANES(4)) u_probe (.*);
endmodule
