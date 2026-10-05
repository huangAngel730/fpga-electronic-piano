`timescale 1ns/1ps
module tb_tool_probe;
    reg clk = 0;
    reg rst_n = 0;
    wire tick;
    integer cycle;
    integer expected;
    tool_probe dut(.sys_clk(clk), .rst_n(rst_n), .tick(tick));
    always #10 clk = !clk;
    task check_cycle;
        input integer want;
        begin
            @(posedge clk); #1;
            if (tick !== ((want >> 7) & 1)) $fatal(1, "counter output mismatch");
        end
    endtask
    initial begin
        check_cycle(0);
        @(negedge clk); rst_n = 1;
        expected = 0;
        for (cycle = 0; cycle < 600; cycle = cycle + 1) begin
            expected = (expected + 1) & 255;
            check_cycle(expected);
        end
        // Reset during operation, then restart: abnormal interruption covered.
        @(negedge clk); rst_n = 0;
        check_cycle(0);
        check_cycle(0);
        @(negedge clk); rst_n = 1;
        check_cycle(1);
        $display("PASS tool_probe: reset, normal count, wrap, reset interruption");
        $finish;
    end
    initial begin #20000; $fatal(1, "timeout"); end
endmodule
