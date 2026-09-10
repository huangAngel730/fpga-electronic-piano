`timescale 1ns / 1ps

module tone_generator #(
    parameter integer CLK_FREQ_HZ = 50_000_000,
    parameter integer PHASE_W = 32
) (
    input wire clk, input wire rst_n, input wire [7:0] keys_pressed,
    output wire audio_out, output reg [7:0] active_note
);
    reg [PHASE_W-1:0] phase_acc, phase_step;

    function [PHASE_W-1:0] step_for_hz;
        input integer frequency_hz;
        reg [63:0] numerator;
        begin
            numerator = frequency_hz;
            numerator = numerator << PHASE_W;
            step_for_hz = (numerator + CLK_FREQ_HZ / 2) / CLK_FREQ_HZ;
        end
    endfunction

    always @(*) begin
        phase_step = 0; active_note = 0;
        if (keys_pressed[7]) begin phase_step=step_for_hz(523); active_note=8'h80; end
        else if (keys_pressed[6]) begin phase_step=step_for_hz(494); active_note=8'h40; end
        else if (keys_pressed[5]) begin phase_step=step_for_hz(440); active_note=8'h20; end
        else if (keys_pressed[4]) begin phase_step=step_for_hz(392); active_note=8'h10; end
        else if (keys_pressed[3]) begin phase_step=step_for_hz(349); active_note=8'h08; end
        else if (keys_pressed[2]) begin phase_step=step_for_hz(330); active_note=8'h04; end
        else if (keys_pressed[1]) begin phase_step=step_for_hz(294); active_note=8'h02; end
        else if (keys_pressed[0]) begin phase_step=step_for_hz(262); active_note=8'h01; end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n || phase_step == 0) phase_acc <= 0;
        else phase_acc <= phase_acc + phase_step;
    end
    assign audio_out = (phase_step != 0) ? phase_acc[PHASE_W-1] : 1'b0;
endmodule
