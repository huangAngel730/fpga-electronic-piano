`timescale 1ns/1ps

module tb_piano_dds_oscillator_v2;
    logic clk = 0;
    logic rst_n = 0;
    logic sample_tick = 0;
    logic note_on = 0;
    logic [9:0] velocity = 0;
    logic [31:0] fcw = 0;
    logic signed [15:0] wt_sample;
    logic [31:0] phase_before;
    integer errors = 0;
    integer wrap_wait = 0;

    always #10 clk = ~clk;

    piano_dds_oscillator_v2 #(
        .VOICE_INDEX(1),
        .ROM_FILE("model/generated/wavetables_v2/piano_v2_lane1_4x256_8191.mem")
    ) dut (
        .sys_clk(clk), .sys_rst_n(rst_n), .sample_tick(sample_tick),
        .note_on(note_on), .velocity(velocity), .fcw(fcw),
        .wt_sample(wt_sample)
    );

    task tick_sample;
        begin
            @(negedge clk); sample_tick = 1;
            @(negedge clk); sample_tick = 0;
        end
    endtask

    task check(input logic condition, input string message);
        begin
            if (!condition) begin
                $display("FAIL: %s", message);
                errors = errors + 1;
            end
        end
    endtask

    initial begin
        repeat (3) @(negedge clk);
        rst_n = 1;
        @(negedge clk);
        check(dut.phase_acc == 0, "reset phase");
        check(dut.attack_samples_left == 0, "reset attack counter");

        fcw = 32'd23_409_859; // C4
        velocity = 10'd900;
        note_on = 1;
        @(negedge clk); note_on = 0;
        #1;
        check(dut.attack_samples_left == 1392,
              "lane-1 attack stagger is 48 samples");
        check(dut.selected_table == 0, "C4 attack selects ten-partial table");

        repeat (1392) tick_sample();
        #1;
        check(dut.attack_samples_left == 0, "attack counter expires");
        check(dut.phase_acc == 32'd2_521_752_656, "FCW accumulation is exact");
        check(dut.table_change_pending, "body switch waits for phase wrap");
        wrap_wait = 0;
        while ((dut.selected_table != 1) && (wrap_wait < 300)) begin
            tick_sample();
            wrap_wait = wrap_wait + 1;
        end
        check(dut.selected_table == 1, "C4 body selects seven-partial table");
        check(!dut.table_change_pending, "phase-wrap switch completes");

        phase_before = dut.phase_acc;
        fcw = 32'd374_650_331; // near MIDI 108 / top of 88-key range
        note_on = 1;
        @(negedge clk); note_on = 0;
        #1;
        check(dut.phase_acc == phase_before, "note_on does not reset or detune phase");
        check(dut.selected_table == 2, "top-note attack selects five-partial table");

        repeat (48) tick_sample();
        check(dut.phase_acc == ((phase_before + 32'd1_123_673_232) & 32'hffff_ffff),
              "top-note FCW remains unchanged");

        rst_n = 0;
        @(negedge clk); rst_n = 1;
        @(negedge clk);
        check(dut.phase_acc == 0 && dut.attack_samples_left == 0,
              "asynchronous reset clears V2 state");

        if (errors == 0) begin
            $display("PASS: tb_piano_dds_oscillator_v2");
            $finish;
        end
        $fatal(1, "FAIL: %0d checks", errors);
    end
endmodule
