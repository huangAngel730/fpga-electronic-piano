// Sample vector TB. Run from V3 root; +VECTOR=design/model_results/osc_note36.mem
// +FCW=5852464 (note36). Dependencies: baseline V1 oscillator, candidate oscillator.
`timescale 1ns/1ps
module tb_piano_dds_oscillator_v3;
    logic clk=0;
    always #10 clk=~clk;
    logic rst_n=0, tick=0, note_on=0;
    logic [9:0] velocity=900;
    logic [31:0] fcw;
    wire signed [15:0] sample_out;
    logic signed [15:0] expected [0:2047];
    string vector_path;
    integer j, failures=0;
    piano_dds_oscillator_v3 u_dut (
        .sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(tick),
        .note_on(note_on),.velocity(velocity),.fcw(fcw),.wt_sample(sample_out)
    );
    task automatic strike(input logic [9:0] vel);
        begin
            @(negedge clk);velocity=vel;note_on=1;
            @(negedge clk);note_on=0;
            repeat(4) @(negedge clk);
        end
    endtask
    initial begin
        if(!$value$plusargs("VECTOR=%s",vector_path)) $fatal(1,"VECTOR required");
        if(!$value$plusargs("FCW=%d",fcw)) $fatal(1,"FCW required");
        $readmemh(vector_path,expected);
        repeat(5) @(negedge clk);rst_n=1;
        strike(900);
        for(j=0;j<2048;j=j+1) begin
            if(j==1000) strike(120);
            @(negedge clk);tick=1;
            @(negedge clk);tick=0;
            repeat(40) @(negedge clk);
            if(sample_out!==expected[j]) begin
                if(failures<10) $display("FAIL sample %0d got %0d expected %0d",j,sample_out,expected[j]);
                failures=failures+1;
            end
            // Space remaining clocks to 1042-clock sample period, avoiding
            // accelerated simulation hiding inter-sample lifecycle problems.
            repeat(1000) @(negedge clk);
        end
        @(negedge clk);rst_n=0;
        @(negedge clk);
        if(u_dut.bass_sample!==0 || u_dut.phase_acc!==0) $fatal(1,"reset failure");
        if(failures) $fatal(1,"V3 vector failures %0d",failures);
        $display("PASS V3 oscillator 2048 exact samples, retrigger, reset, FCW=%0d",fcw);
        $finish;
    end
    initial begin #100000000; $fatal(1,"TB timeout");end
endmodule
