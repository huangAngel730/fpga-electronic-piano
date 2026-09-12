`timescale 1ns / 1ps

module electronic_piano_top #(
    parameter integer CLK_FREQ_HZ = 50_000_000,
    parameter integer DEBOUNCE_MS = 10
) (
    input wire clk, input wire rst_n, input wire [7:0] keys_n,
    output wire audio_out, output wire [7:0] note_led
);
    wire [7:0] keys_pressed;
    key_debounce #(.CLK_FREQ_HZ(CLK_FREQ_HZ), .DEBOUNCE_MS(DEBOUNCE_MS))
        u_key_debounce (.clk(clk), .rst_n(rst_n), .keys_n(keys_n),
                        .keys_pressed(keys_pressed));
    tone_generator #(.CLK_FREQ_HZ(CLK_FREQ_HZ))
        u_tone_generator (.clk(clk), .rst_n(rst_n),
                          .keys_pressed(keys_pressed), .audio_out(audio_out),
                          .active_note(note_led));
endmodule
