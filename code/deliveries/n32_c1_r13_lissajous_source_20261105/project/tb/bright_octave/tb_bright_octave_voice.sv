`timescale 1ns/1ps

module tb_bright_octave_voice;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic sample_tick = 1'b0;
    logic note_on = 1'b0;
    logic note_off = 1'b0;
    logic timbre_organ = 1'b0;
    logic [9:0] velocity = 10'd800;
    logic [31:0] fcw = 32'h0100_0000;

    wire signed [15:0] baseline_sample;
    wire signed [15:0] candidate_sample;
    wire [15:0] organ_envelope_level;
    wire [2:0] organ_envelope_state;

    logic signed [15:0] bright_rom [0:1023];
    logic signed [15:0] expected_queue [0:2047];
    logic signed [15:0] pending_hold_value;
    logic [31:0] model_phase;
    integer queue_head;
    integer queue_tail;
    integer organ_samples_checked;
    integer piano_cycles_checked;
    logic pending_hold_check;

    always #12.5 clk = ~clk;

    m1td_piano_triangle_voice #(
        .PIANO_ROM_FILE("rom/piano_band_4x256_8191.mem"),
        .SINE_ROM_FILE("rom/sine_wavetable.hex"),
        .TRIANGLE_ROM_FILE("rom/triangle_wavetable.hex")
    ) u_r18_reference (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .note_on(note_on), .note_off(note_off), .timbre_triangle(1'b0),
        .velocity(velocity), .fcw(fcw), .wt_sample(baseline_sample)
    );

    piano_organ_voice #(
        .PIANO_ROM_FILE("rom/piano_band_4x256_8191.mem"),
        .ORGAN_ROM_FILE("rom/bright_octave_4x256_8191.mem"),
        .PRIVATE_M1TD_PIANO(1'b1)
    ) u_candidate (
        .clk(clk), .rst_n(rst_n), .sample_tick(sample_tick),
        .note_on(note_on), .note_off(note_off), .timbre_organ(timbre_organ),
        .velocity(velocity), .fcw(fcw), .wt_sample(candidate_sample)
    );

    organ_envelope #(
        .VELOCITY_ROM_FILE("rom/organ_velocity_gain_1024.mem")
    ) u_organ_envelope (
        .sys_clk(clk), .sys_rst_n(rst_n), .sample_tick(sample_tick),
        .note_on(note_on), .note_off(note_off), .velocity(velocity),
        .envelope_level(organ_envelope_level),
        .state_out(organ_envelope_state)
    );

    initial begin
        $readmemh("rom/bright_octave_4x256_8191.mem", bright_rom);
    end

    // Observe after the active edge. The organ DDS must return exactly the
    // selected Bright Octave word; the adapter then holds it one cycle later.
    always @(negedge clk) begin
        if (!rst_n) begin
            model_phase = 32'd0;
            queue_head = 0;
            queue_tail = 0;
            organ_samples_checked = 0;
            piano_cycles_checked = 0;
            pending_hold_check = 1'b0;
            pending_hold_value = 16'sd0;
        end else begin
            if (!timbre_organ) begin
                piano_cycles_checked = piano_cycles_checked + 1;
                if (candidate_sample !== baseline_sample)
                    $fatal(1, "Piano path changed: candidate=%0d baseline=%0d",
                           candidate_sample, baseline_sample);
            end

            if (pending_hold_check) begin
                if (candidate_sample !== pending_hold_value)
                    $fatal(1, "Organ adapter hold mismatch: got=%0d expected=%0d",
                           candidate_sample, pending_hold_value);
                pending_hold_check = 1'b0;
            end

            if (u_candidate.organ_valid) begin
                if (queue_head >= queue_tail)
                    $fatal(1, "Organ output arrived without a queued request");
                if (u_candidate.organ_wave !== expected_queue[queue_head])
                    $fatal(1, "Bright Octave ROM mismatch at sample %0d: got=%0d expected=%0d",
                           organ_samples_checked, u_candidate.organ_wave,
                           expected_queue[queue_head]);
                pending_hold_value = expected_queue[queue_head];
                pending_hold_check = timbre_organ;
                queue_head = queue_head + 1;
                organ_samples_checked = organ_samples_checked + 1;
            end

            if (sample_tick) begin
                if (queue_tail >= 2048)
                    $fatal(1, "Expected queue overflow");
                expected_queue[queue_tail] = bright_rom[{2'd0, model_phase[31:24]}];
                queue_tail = queue_tail + 1;
                model_phase = model_phase + fcw;
            end
        end
    end

    task automatic pulse_sample;
        begin
            @(negedge clk); #1 sample_tick = 1'b1;
            @(negedge clk); #1 sample_tick = 1'b0;
        end
    endtask

    task automatic pulse_note_on;
        begin
            @(negedge clk); #1 note_on = 1'b1;
            @(negedge clk); #1 note_on = 1'b0;
        end
    endtask

    task automatic pulse_note_off;
        begin
            @(negedge clk); #1 note_off = 1'b1;
            @(negedge clk); #1 note_off = 1'b0;
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        #1 rst_n = 1'b1;
        pulse_note_on();

        // Program 0 must remain byte-for-byte equivalent to the frozen R18
        // Piano adapter while the Bright Octave DDS advances in parallel.
        repeat (32) pulse_sample();
        repeat (8) @(negedge clk);
        if (piano_cycles_checked < 60)
            $fatal(1, "Insufficient Piano equivalence coverage");

        timbre_organ = 1'b1;
        pulse_note_on();
        repeat (128) pulse_sample();
        repeat (4) @(negedge clk);
        if (organ_envelope_state !== 3'd3 || organ_envelope_level == 16'd0)
            $fatal(1, "Organ envelope did not reach sustain: state=%0d level=%0d",
                   organ_envelope_state, organ_envelope_level);

        repeat (32) pulse_sample();
        pulse_note_off();
        repeat (1024) pulse_sample();
        repeat (8) @(negedge clk);
        if (organ_envelope_state !== 3'd0 || organ_envelope_level !== 16'd0)
            $fatal(1, "Organ envelope did not return to idle: state=%0d level=%0d",
                   organ_envelope_state, organ_envelope_level);
        if (organ_samples_checked < 1100)
            $fatal(1, "Insufficient Bright Octave DDS coverage: %0d",
                   organ_samples_checked);

        $display("PASS R18_PIANO_UNCHANGED cycles=%0d", piano_cycles_checked);
        $display("PASS BRIGHT_OCTAVE_DDS samples=%0d", organ_samples_checked);
        $display("PASS BRIGHT_OCTAVE_ENVELOPE attack=128 release=1024");
        $display("BRIGHT_OCTAVE_VOICE_TEST_COMPLETE");
        $finish;
    end

    initial begin
        #2_000_000;
        $fatal(1, "Test watchdog");
    end
endmodule
