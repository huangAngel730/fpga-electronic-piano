// T009 M2 zero-slope boundary check against unchanged current ADSR RTL.
// Sample counts are independent constants: never reuse DUT ATTACK_SAMPLES.
`timescale 1ns/1ps
module tb_adsr_zero_slope;
    logic sys_clk=0;
    always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0,sample_tick=0,note_on=0,note_off=0;
    logic [9:0] velocity=0;
    wire [15:0] envelope_level;
    wire [2:0] state_out;
    adsr_piano_envelope dut(.*);
    integer checks=0,samples=0,trace;
    string trace_path;
    task automatic check(input logic ok,input string label_text);
        checks++;
        if(ok!==1'b1)$fatal(1,"Zero-slope %s samples=%0d level=%0d state=%0d",label_text,samples,envelope_level,state_out);
    endtask
    task automatic reset_dut;
        @(negedge sys_clk);sys_rst_n=0;sample_tick=0;note_on=0;note_off=0;
        repeat(4)@(negedge sys_clk);
        check(envelope_level==0 && state_out==0,"reset clears output/state");
        sys_rst_n=1;repeat(2)@(negedge sys_clk);
        $fdisplay(trace,"R");
    endtask
    task automatic trigger(input logic [9:0] v);
        @(negedge sys_clk);velocity=v;note_on=1;
        @(negedge sys_clk);note_on=0;
        repeat(3)@(negedge sys_clk);
        $fdisplay(trace,"N %0d",v);
        check(state_out==1,"Note On exposes Attack after ROM load");
    endtask
    task automatic step;
        @(negedge sys_clk);sample_tick=1;
        @(negedge sys_clk);sample_tick=0;
        samples++;
        $fdisplay(trace,"S %0d %0d",envelope_level,state_out);
        repeat(3)@(negedge sys_clk);
    endtask
    task automatic scenario(input logic [9:0] v,input integer peak);
        reset_dut();trigger(v);
        for(integer n=1;n<=240;n++)begin
            step();
            check(state_out==(n<240 ? 1 : 2),"initial Attack phase ends exactly after240 samples");
        end
        check(envelope_level==peak,"initial peak exact");
        // Three same-target retriggers avoid false coverage from a falling ramp.
        repeat(3)begin
            trigger(v);
            check(envelope_level==peak,"event itself preserves current peak");
            for(integer n=1;n<=240;n++)begin
                step();
                check(envelope_level==peak,"all zero-slope samples preserve exact peak");
                check(state_out==(n<240 ? 1 : 2),"zero-slope phase boundary:1/239Attack,240Decay");
            end
        end
        step();
        check(state_out==2 && envelope_level<peak,"first Decay sample happens only after240");
    endtask
    initial begin
        if(!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"TRACE required");
        trace=$fopen(trace_path,"w");if(!trace)$fatal(1,"Cannot open trace");
        scenario(1023,32767);
        scenario(512,13119);
        scenario(1,6553);
        $fclose(trace);
        check(samples==2883,"complete sample count");
        $display("PASS ADSR zero-slope checks=%0d samples=%0d",checks,samples);$finish;
    end
    initial begin #10000000;$fatal(1,"Zero-slope timeout");end
endmodule