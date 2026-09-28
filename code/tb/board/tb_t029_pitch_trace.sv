// M2 T029 isolated cycle-level oracle for an event-time pitch register.
// Run once against original simple_voice and once against generated candidate.
`timescale 1ns/1ps
module tb_t029_pitch_trace;
    import audio_defs_pkg::*;
    logic clk=0; always #5 clk=~clk;
    logic rst_n=0, sample_tick=0, event_valid=0;
    logic event_ready;
    performance_event_t event_data;
    logic signed [23:0] pcm_left, pcm_right;
    logic voice_active;
    logic [6:0] current_note;
    simple_voice dut (
        .clk,.rst_n,.sample_tick,.event_valid,.event_ready,.event_data,
        .pcm_left,.pcm_right,.voice_active,.current_note
    );
    integer cycle=0;
    // Observe every cycle, including the event and sample_tick collision.
    always @(posedge clk) begin
        #1;
        $display("TRACE %0d %0h %0h %0d %0d %0h",cycle,pcm_left,pcm_right,
                 voice_active,current_note,dut.phase_q);
        cycle++;
    end
    initial begin
        event_data='0;
        repeat (3) @(negedge clk);
        rst_n=1;
        for (integer n=0;n<128;n++) begin
            @(negedge clk);
            event_valid=1;
            event_data.event_type=EVENT_NOTE_ON;
            event_data.note_number=7'(n);
            sample_tick=(n%2)==0;
            @(negedge clk);
            event_valid=0;
            sample_tick=1;
            repeat (3) @(negedge clk);
            sample_tick=0;
            // Repeated same note while active, followed by a new active pitch.
            event_valid=1;
            event_data.event_type=EVENT_NOTE_ON;
            event_data.note_number=7'(n);
            @(negedge clk);
            event_data.note_number=7'(n+1);
            sample_tick=1;
            @(negedge clk);
            event_valid=0;
            repeat(2) @(negedge clk);
            // A control event must not change the oscillator's pitch register.
            event_valid=1;
            event_data.event_type=EVENT_CONTROL_CHANGE;
            event_data.note_number=7'(n+17);
            @(negedge clk);
            event_valid=0;
            @(negedge clk);
            sample_tick=0;
            // A nonmatching Note Off must keep the same voice.
            event_valid=1;
            event_data.event_type=EVENT_NOTE_OFF;
            event_data.note_number=7'(n);
            @(negedge clk);
            event_data.note_number=7'(n+1);
            sample_tick=1;
            @(negedge clk);
            event_valid=0;
            sample_tick=0;
        end
        @(negedge clk);
        event_valid=1;
        event_data.event_type=EVENT_ALL_NOTES_OFF;
        @(negedge clk);
        event_valid=0;
        rst_n=0;
        repeat(2) @(negedge clk);
        rst_n=1;
        sample_tick=1;
        repeat(3) @(negedge clk);
        $display("PASS tb_t029_pitch_trace cycles=%0d notes=128 retriggers=128 controls=128",cycle);
        $finish;
    end
    initial begin #100000; $fatal(1,"pitch trace timeout"); end
endmodule
