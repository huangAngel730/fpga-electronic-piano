// T004 self-check: compare 1000 actual samples with M1 DDS model.
// Drive at negedge; sample before phase update, matching model.step().
`timescale 1ns/1ps
module tb_dds_oscillator;
    logic sys_clk = 0;
    always #10 sys_clk = ~sys_clk;
    logic sys_rst_n = 0, sample_tick = 0;
    logic [31:0] fcw = 0;
    wire signed [15:0] wt_sample;
    dds_oscillator dut (.*);
    integer file_handle, scan_count, expected_index, expected_sample;
    integer compared = 0;
    logic [31:0] expected_phase, expected_fcw;
    string vectors;
    initial begin
        if (!$value$plusargs("VECTORS=%s", vectors))
            $fatal(1, "VECTORS path is required");
        file_handle = $fopen(vectors, "r");
        if (file_handle == 0) $fatal(1, "Cannot open vectors: %s", vectors);
        repeat (4) @(negedge sys_clk);
        sys_rst_n = 1;
        repeat (2) @(negedge sys_clk);
        for (integer n = 0; n < 1000; n = n + 1) begin
            scan_count = $fscanf(file_handle, "%d %h %h %d\n",
                                 expected_index, expected_fcw, expected_phase, expected_sample);
            if (scan_count != 4 || expected_index != n)
                $fatal(1, "Missing/malformed vector %0d (fields=%0d)", n, scan_count);
            if (n == 900) begin
                sys_rst_n = 0;
                repeat (3) @(negedge sys_clk);
                sys_rst_n = 1;
                repeat (2) @(negedge sys_clk);
            end
            fcw = expected_fcw;
            // Several clocks without sample_tick must preserve phase/sample.
            repeat (3) @(negedge sys_clk);
            #1;
            if (dut.phase_acc !== expected_phase || $signed(wt_sample) !== expected_sample)
                $fatal(1, "sample %0d phase=%h expected=%h value=%0d expected=%0d",
                       n, dut.phase_acc, expected_phase, $signed(wt_sample), expected_sample);
            compared = compared + 1;
            sample_tick = 1;
            @(negedge sys_clk);
            sample_tick = 0;
            repeat (2) @(negedge sys_clk);
        end
        if (compared != 1000) $fatal(1, "Insufficient comparison count: %0d", compared);
        $fclose(file_handle);
        $display("PASS tb_dds_oscillator compared=%0d (FCW change/stall/reset)", compared);
        $finish;
    end
    initial begin
        #2_000_000;
        $fatal(1, "DDS self-check timeout, compared=%0d", compared);
    end
endmodule
