// M2 resource probe: identical interface and timing for 1 and 4 copies.
// Not an audio engine: no DDS, allocator, mixer, PCM buffer or UART.
// Independent velocity/Note On/Off/output prevents merging idle clones.
`timescale 1ns/1ps
module adsr_scale_probe #(
    parameter integer VOICES = 1
) (
    input logic sys_clk,sys_rst_n,sample_tick,
    input logic [3:0] note_on,note_off,
    input logic [39:0] velocity,
    output wire [63:0] envelope_level,
    output wire [11:0] state_out
);
    for(genvar i=0;i<4;i=i+1) begin: g_voice
        if(i<VOICES)begin: g_used
            adsr_piano_envelope u_adsr (
                .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),
                .sample_tick(sample_tick),.note_on(note_on[i]),
                .note_off(note_off[i]),.velocity(velocity[10*i+:10]),
                .envelope_level(envelope_level[16*i+:16]),
                .state_out(state_out[3*i+:3])
            );
        end else begin: g_unused
            assign envelope_level[16*i+:16]=16'd0;
            assign state_out[3*i+:3]=3'd0;
        end
    end
endmodule

module adsr_probe_1 (
    input logic sys_clk,sys_rst_n,sample_tick,
    input logic [3:0] note_on,note_off,
    input logic [39:0] velocity,
    output wire [63:0] envelope_level,
    output wire [11:0] state_out
);
    adsr_scale_probe #(.VOICES(1)) u (.*);
endmodule

module adsr_probe_4 (
    input logic sys_clk,sys_rst_n,sample_tick,
    input logic [3:0] note_on,note_off,
    input logic [39:0] velocity,
    output wire [63:0] envelope_level,
    output wire [11:0] state_out
);
    adsr_scale_probe #(.VOICES(4)) u (.*);
endmodule
