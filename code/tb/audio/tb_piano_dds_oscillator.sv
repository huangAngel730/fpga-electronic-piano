`timescale 1ns/1ps

module tb_piano_dds_oscillator;
    logic clk = 0;
    logic rst_n = 0;
    logic sample_tick = 0;
    logic note_on = 0;
    logic [9:0] velocity = 0;
    logic [31:0] fcw = 0;
    logic signed [15:0] wt_sample;
    integer errors = 0;
    integer wrap_wait = 0;

    always #10 clk = ~clk;

    piano_dds_oscillator #(
        .ROM_FILE("model/generated/wavetables/piano_band_4x256_8191.mem")
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

        fcw = 32'd23_409_859; // C4, 261.6256 Hz at 48 kHz
        velocity = 10'd900;
        note_on = 1;
        @(negedge clk); note_on = 0;
        #1;
        check(dut.attack_samples_left == 1440, "high velocity attack length");
        check(dut.selected_table == 0, "low-note attack selects rich table");

        repeat (1440) tick_sample();
        #1;
        check(dut.attack_samples_left == 0, "attack expires");
        check(dut.phase_acc == 32'd3_645_425_888, "FCW is not detuned");
        check(dut.table_change_pending, "body change waits for phase wrap");
        wrap_wait = 0;
        while ((dut.selected_table != 1) && (wrap_wait < 300)) begin
            tick_sample();
            wrap_wait = wrap_wait + 1;
        end
        check(dut.selected_table == 1, "low-note body selects medium table at wrap");
        check(!dut.table_change_pending, "phase-aligned body switch completes");

        fcw = 32'd374_650_331; // near top of 88-key range
        velocity = 10'd900;
        note_on = 1;
        @(negedge clk); note_on = 0;
        #1;
        check(dut.selected_table == 2, "high-note attack selects three-partial table");

        rst_n = 0;
        @(negedge clk); rst_n = 1;
        @(negedge clk);
        check(dut.phase_acc == 0 && dut.attack_samples_left == 0,
              "asynchronous reset clears state");

        if (errors == 0) begin
            $display("PASS: tb_piano_dds_oscillator");
            $finish;
        end
        $fatal(1, "FAIL: %0d checks", errors);
    end
endmodule

