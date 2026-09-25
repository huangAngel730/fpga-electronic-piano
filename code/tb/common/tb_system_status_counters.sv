`timescale 1ns/1ps
module tb_system_status_counters;
    logic clk = 0;
    always #5 clk = ~clk;
    logic rst_n = 0;
    logic pcm_request = 0, pcm_commit = 0;
    logic [31:0] button_overflow = 0, midi_overflow = 0;
    logic [31:0] event_fifo_overflow, max_processing_cycles;
    integer checks = 0;
    system_status_counters dut (.*);

    task automatic tick(input bit request_now, input bit commit_now);
        pcm_request = request_now;
        pcm_commit = commit_now;
        @(posedge clk);
        #1; // allow register updates to settle
        @(negedge clk);
        pcm_request = 0;
        pcm_commit = 0;
    endtask
    task automatic check(input bit pass, input string description);
        if (!pass) $fatal(1, "%s", description);
        checks++;
    endtask
    initial begin
        repeat (3) @(negedge clk);
        check(event_fifo_overflow == 0 && max_processing_cycles == 0,
              "reset clears both metrics");
        rst_n = 1;
        button_overflow = 2;
        midi_overflow = 3;
        #1; check(event_fifo_overflow == 5, "local drop counts aggregate");
        midi_overflow = 32'hffff_ffff;
        #1; check(event_fifo_overflow == 32'hffff_ffff, "sum saturates");
        midi_overflow = 3;
        tick(1, 0);
        tick(0, 0);
        tick(0, 1);
        check(max_processing_cycles == 2, "request-to-commit two cycles");
        tick(1, 0);
        tick(0, 1);
        check(max_processing_cycles == 2, "shorter completion keeps peak");
        tick(1, 0);
        repeat (5) tick(0, 0);
        tick(1, 0); // new generation cancels old incomplete request
        tick(0, 0);
        tick(0, 0);
        tick(0, 1);
        check(max_processing_cycles == 3, "replaced request excluded from peak");
        tick(1, 1);
        check(max_processing_cycles == 3, "simultaneous zero-cycle result");
        tick(0, 1);
        check(max_processing_cycles == 3, "orphan commit ignored");
        tick(1, 0);
        rst_n = 0;
        @(negedge clk);
        #1;
        check(max_processing_cycles == 0 && event_fifo_overflow == 0,
              "runtime reset clears pending request and telemetry");
        $display("PASS tb_system_status_counters checks=%0d", checks);
        $finish;
    end
    initial begin #10000; $fatal(1, "counter timeout"); end
endmodule
