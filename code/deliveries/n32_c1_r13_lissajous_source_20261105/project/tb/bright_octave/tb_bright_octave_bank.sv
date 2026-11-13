`timescale 1ns/1ps

module tb_bright_octave_bank;
    import audio_defs_pkg::*;

    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic event_valid = 1'b0;
    performance_event_t event_data = '0;
    logic frame_tick = 1'b0;
    logic sample_req = 1'b0;
    logic [31:0] sample_req_id = 32'd0;
    logic result_ready = 1'b0;

    wire event_ready;
    wire calc_ready;
    wire result_valid;
    wire [31:0] result_req_id;
    wire [63:0] result_envelopes;
    wire [63:0] result_waves;
    wire [127:0] result_fcw;
    wire [3:0] result_occupied;
    wire [11:0] result_states;
    wire [31:0] active_voice_count;

    integer organ_nonzero_samples = 0;
    integer piano_nonzero_samples = 0;
    integer four_voice_samples = 0;
    integer sample_count = 0;

    always #12.5 clk = ~clk;

    m1td_polyphonic_envelope_bank #(
        .WAVE_ROM_FILE("rom/piano_band_4x256_8191.mem"),
        .ORGAN_ROM_FILE("rom/bright_octave_4x256_8191.mem"),
        .ORGAN_GAIN_ROM_FILE("rom/organ_velocity_gain_1024.mem"),
        .OCT_FILE("rom/oct_ratio_q16.mem"),
        .SUB_FILE("rom/sub_ratio_q16.mem"),
        .LFO_FILE("rom/lfo_sine_q15.mem")
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .event_valid(event_valid), .event_ready(event_ready),
        .event_data(event_data),
        .frame_tick(frame_tick), .sample_req(sample_req),
        .sample_req_id(sample_req_id), .calc_ready(calc_ready),
        .result_valid(result_valid), .result_ready(result_ready),
        .result_req_id(result_req_id),
        .result_envelopes(result_envelopes), .result_waves(result_waves),
        .result_fcw(result_fcw), .result_occupied(result_occupied),
        .result_states(result_states), .active_voice_count(active_voice_count)
    );

    task automatic send_event(input performance_event_t ev);
        begin
            while (!event_ready) @(posedge clk);
            @(negedge clk);
            event_data = ev;
            event_valid = 1'b1;
            @(negedge clk);
            event_valid = 1'b0;
            event_data = '0;
            while (!event_ready) @(posedge clk);
        end
    endtask

    task automatic select_program(input logic program_select);
        performance_event_t ev;
        begin
            ev = '0;
            ev.event_type = EVENT_CONTROL_CHANGE;
            ev.source_id = 4'd0;
            ev.channel = 4'd0;
            ev.control_id = CTRL_VOICE_SELECT;
            ev.control_value = {11'd0, program_select};
            send_event(ev);
        end
    endtask

    task automatic note_on(input logic [6:0] note, input logic [9:0] velocity);
        performance_event_t ev;
        begin
            ev = '0;
            ev.event_type = EVENT_NOTE_ON;
            ev.source_id = 4'd0;
            ev.channel = 4'd0;
            ev.note_number = note;
            ev.velocity = velocity;
            send_event(ev);
        end
    endtask

    task automatic note_off(input logic [6:0] note);
        performance_event_t ev;
        begin
            ev = '0;
            ev.event_type = EVENT_NOTE_OFF;
            ev.source_id = 4'd0;
            ev.channel = 4'd0;
            ev.note_number = note;
            send_event(ev);
        end
    endtask

    task automatic take_sample;
        integer lane;
        integer signed wave_i;
        integer signed env_i;
        integer signed scaled_i;
        begin
            while (!calc_ready) @(posedge clk);
            @(negedge clk);
            sample_req_id = sample_req_id + 32'd1;
            sample_req = 1'b1;
            @(negedge clk);
            sample_req = 1'b0;
            while (!result_valid) @(posedge clk);
            #1;
            if (result_req_id !== sample_req_id)
                $fatal(1, "Request identity mismatch: got=%0d expected=%0d",
                       result_req_id, sample_req_id);
            for (lane = 0; lane < 4; lane = lane + 1) begin
                wave_i = $signed(result_waves[16*lane +: 16]);
                env_i = $signed({1'b0, result_envelopes[16*lane +: 16]});
                scaled_i = (wave_i * env_i) >>> 15;
                if (scaled_i < -32768 || scaled_i > 32767)
                    $fatal(1, "Lane %0d scaling overflow: %0d", lane, scaled_i);
            end
            if (result_occupied == 4'hf)
                four_voice_samples = four_voice_samples + 1;
            sample_count = sample_count + 1;
            @(negedge clk);
            result_ready = 1'b1;
            @(negedge clk);
            result_ready = 1'b0;
        end
    endtask

    initial begin
        repeat (5) @(negedge clk);
        rst_n = 1'b1;

        // Program 1 must be captured by each newly allocated voice.
        select_program(1'b1);
        note_on(7'd60, 10'd800);
        if (dut.slot_timbre[0] !== 1'b1)
            $fatal(1, "First Program-1 note did not capture Bright Octave");

        // Changing K3 while the note is held must not retag that voice.
        select_program(1'b0);
        if (dut.slot_timbre[0] !== 1'b1)
            $fatal(1, "Held voice changed timbre after K3 update");
        note_on(7'd64, 10'd700);
        if (dut.slot_timbre[1:0] !== 2'b01)
            $fatal(1, "Program ownership mismatch after K3 update: %b",
                   dut.slot_timbre[1:0]);

        repeat (160) begin
            take_sample();
            if (result_occupied[0] && result_envelopes[15:0] != 16'd0 &&
                $signed(result_waves[15:0]) != 0)
                organ_nonzero_samples = organ_nonzero_samples + 1;
            if (result_occupied[1] && result_envelopes[31:16] != 16'd0 &&
                $signed(result_waves[31:16]) != 0)
                piano_nonzero_samples = piano_nonzero_samples + 1;
        end
        if (organ_nonzero_samples == 0 || piano_nonzero_samples == 0)
            $fatal(1, "One timbre path stayed silent: organ=%0d piano=%0d",
                   organ_nonzero_samples, piano_nonzero_samples);

        // Four Bright Octave voices exercise the actual bank and arithmetic bound.
        note_off(7'd60);
        note_off(7'd64);
        // Program 0 keeps the frozen Piano release of 4800 samples; wait for
        // both the Piano and Bright Octave lanes before checking retirement.
        repeat (4900) take_sample();
        if (active_voice_count != 0)
            $fatal(1, "Released voices did not retire: %0d", active_voice_count);

        select_program(1'b1);
        note_on(7'd60, 10'd900);
        note_on(7'd64, 10'd900);
        note_on(7'd67, 10'd900);
        note_on(7'd72, 10'd900);
        if (dut.slot_timbre !== 4'hf || active_voice_count != 4)
            $fatal(1, "Four-voice Bright Octave allocation failed: timbre=%b voices=%0d",
                   dut.slot_timbre, active_voice_count);
        repeat (160) take_sample();
        if (four_voice_samples < 100)
            $fatal(1, "Insufficient four-voice result coverage: %0d", four_voice_samples);

        note_off(7'd60);
        note_off(7'd64);
        note_off(7'd67);
        note_off(7'd72);
        repeat (1100) take_sample();
        if (active_voice_count != 0 || result_occupied != 0)
            $fatal(1, "Four released voices did not retire: active=%0d occupied=%b",
                   active_voice_count, result_occupied);

        $display("PASS PROGRAM_OWNERSHIP held_voice_stable=1 new_voice_program=0");
        $display("PASS MIXED_TIMBRES organ_nonzero=%0d piano_nonzero=%0d",
                 organ_nonzero_samples, piano_nonzero_samples);
        $display("PASS FOUR_VOICE_BRIGHT samples=%0d scale_overflow=0", four_voice_samples);
        $display("PASS RELEASE_RETIRE active_voice_count=0");
        $display("BRIGHT_OCTAVE_BANK_TEST_COMPLETE samples=%0d", sample_count);
        $finish;
    end

    initial begin
        #20_000_000;
        $fatal(1, "Test watchdog");
    end
endmodule
