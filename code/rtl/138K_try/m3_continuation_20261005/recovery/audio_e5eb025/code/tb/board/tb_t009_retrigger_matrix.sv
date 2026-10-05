// M2 independent T009 model-versus-RTL retrigger matrix. No source edits.
`timescale 1ns/1ps
module tb_t009_retrigger_matrix;
    logic sys_clk=0;
    always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0, sample_tick=0, note_on=0, note_off=0;
    logic [9:0] velocity=0;
    wire [15:0] envelope_level;
    wire [2:0] state_out;
    adsr_piano_envelope dut(.*);
    integer trace, samples=0;
    string trace_path;
    task automatic reset_dut;
        @(negedge sys_clk);
        sys_rst_n=0;sample_tick=0;note_on=0;note_off=0;
        repeat(4) @(negedge sys_clk);
        sys_rst_n=1;
        repeat(2) @(negedge sys_clk);
        $fdisplay(trace,"R");
    endtask
    task automatic on(input logic [9:0] v);
        @(negedge sys_clk);velocity=v;note_on=1;
        @(negedge sys_clk);note_on=0;
        repeat(2) @(negedge sys_clk);
        $fdisplay(trace,"N %0d",v);
    endtask
    task automatic off;
        @(negedge sys_clk);note_off=1;
        @(negedge sys_clk);note_off=0;
        $fdisplay(trace,"F");
    endtask
    task automatic ticks(input integer n);
        repeat(n) begin
            @(negedge sys_clk);sample_tick=1;
            @(negedge sys_clk);sample_tick=0;
            samples++;
            $fdisplay(trace,"S %0d %0d",envelope_level,state_out);
            repeat(2) @(negedge sys_clk);
        end
    endtask
    initial begin
        if(!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"TRACE path required");
        trace=$fopen(trace_path,"w");
        if(!trace)$fatal(1,"Cannot write trace");
        reset_dut();on(1023);ticks(40);on(1);ticks(241);
        reset_dut();on(1023);ticks(240);ticks(100);on(1);ticks(241);
        reset_dut();on(1023);ticks(240);ticks(4800);ticks(1000);on(1);ticks(241);
        reset_dut();on(1023);ticks(240);ticks(4800);ticks(1000);off();ticks(1);
        on(1);ticks(241);
        $fclose(trace);
        if(samples!=13425)$fatal(1,"Unexpected matrix count=%0d",samples);
        $display("PASS tb_t009_retrigger_matrix samples=%0d",samples);
        $finish;
    end
    initial begin #8_000_000;$fatal(1,"T009 matrix timeout samples=%0d",samples);end
endmodule
