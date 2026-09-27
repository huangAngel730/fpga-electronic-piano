// T009 sample-counted boundary gate; not a substitute for model comparison.
// Events driven at negedge; sample_tick accelerated to shorten simulation.
`timescale 1ns/1ps
module tb_adsr_piano;
    logic sys_clk=0;
    always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0, sample_tick=0, note_on=0, note_off=0;
    logic [9:0] velocity=1023;
    wire [15:0] envelope_level;
    wire [2:0] state_out;
    adsr_piano_envelope u_dut(.*);
    integer samples=0, errors=0, checks=0, prev_level, delta;
    task automatic check(input logic ok, input string label_text);
        checks=checks+1;
        if (ok !== 1'b1) begin
            errors=errors+1;
            $display("FAIL %s at samples=%0d level=%0d state=%0d",label_text,samples,envelope_level,state_out);
        end
    endtask
    task automatic reset_dut;
        @(negedge sys_clk);
        sys_rst_n=0;sample_tick=0;note_on=0;note_off=0;
        repeat(3) @(negedge sys_clk);
        check(envelope_level==0 && state_out==0,"reset clears output/state");
        sys_rst_n=1;
        repeat(2) @(negedge sys_clk);
    endtask
    task automatic trigger_on(input logic [9:0] v);
        @(negedge sys_clk);velocity=v;note_on=1;
        @(negedge sys_clk);note_on=0;
        repeat(2) @(negedge sys_clk);
    endtask
    task automatic trigger_off;
        @(negedge sys_clk);note_off=1;
        @(negedge sys_clk);note_off=0;
    endtask
    task automatic step_samples(input integer n);
        repeat(n) begin
            @(negedge sys_clk);sample_tick=1;
            @(negedge sys_clk);sample_tick=0;
            samples=samples+1;
            repeat(2) @(negedge sys_clk);
        end
    endtask
    task automatic retrigger_case(input logic [9:0] old_v, new_v);
        reset_dut();trigger_on(old_v);step_samples(6000);
        trigger_off();step_samples(100);
        prev_level=envelope_level;
        trigger_on(new_v);
        delta=($signed({1'b0,envelope_level})-prev_level);
        if(delta<0)delta=-delta;
        check(delta<=138,"event-level retrigger continuity");
        // Check every early sample; never conditionally skip the assertion.
        repeat(4) begin
            step_samples(1);
            delta=($signed({1'b0,envelope_level})-prev_level);
            if(delta<0)delta=-delta;
            check(delta<=138,"retrigger first-sample continuity");
            prev_level=envelope_level;
        end
    endtask
    initial begin
        reset_dut();trigger_on(1023);step_samples(240);
        check(envelope_level==32767,"full-velocity Attack peak");
        check(state_out==2,"M1 debug encoding DECAY=2 after Attack");
        step_samples(4802);
        check(envelope_level>=13105 && envelope_level<=13107,"full-velocity Sustain endpoint");
        check(state_out==3,"M1 debug encoding SUSTAIN=3 after Decay");
        trigger_off();prev_level=envelope_level;
        check(state_out==4,"M1 debug encoding RELEASE=4 at Note Off");
        repeat(4800) begin
            step_samples(1);
            if(envelope_level>prev_level)begin
                errors=errors+1;
                if(errors<12)$display("FAIL Release increased %0d -> %0d",prev_level,envelope_level);
            end
            prev_level=envelope_level;
        end
        step_samples(1);
        check(envelope_level==0 && state_out==0,"Release reaches idle zero");
        retrigger_case(1023,512);
        retrigger_case(1023,1);
        reset_dut();trigger_on(100);step_samples(5043);
        // M1 model gain100=6803, sustain=floor(13107*6803/32767)=2721.
        check(envelope_level>=2720 && envelope_level<=2722,"velocity100 scaled Sustain");
        trigger_off();step_samples(20);reset_dut();
        // A MIDI event may arrive in the same frame as sample_tick. The
        // accepted sample must not vanish while the synchronous ROM loads.
        reset_dut();
        @(negedge sys_clk);velocity=10'd1023;note_on=1;sample_tick=1;
        @(negedge sys_clk);note_on=0;sample_tick=0;
        repeat(4) @(negedge sys_clk);
        check(envelope_level>=134 && envelope_level<=138,
              "Note On with immediate sample_tick still advances first sample");
        // Note Off accepted on the sample edge must consume its first
        // release step, not silently delay the envelope by a frame.
        reset_dut();trigger_on(1023);step_samples(6000);
        prev_level=envelope_level;
        @(negedge sys_clk);note_off=1;sample_tick=1;
        @(negedge sys_clk);note_off=0;sample_tick=0;
        repeat(2) @(negedge sys_clk);
        check(envelope_level<prev_level && prev_level-envelope_level<=5,
              "Note Off with immediate sample_tick consumes first release step");        check(samples>=27000 && checks>=21,"all tests actually executed");
        if(errors!=0)$fatal(1,"T009 failed: samples=%0d checks=%0d errors=%0d",samples,checks,errors);
        $display("PASS tb_adsr_piano samples=%0d checks=%0d",samples,checks);
        $finish;
    end
    initial begin #10_000_000; $fatal(1,"T009 gate timeout samples=%0d",samples); end
endmodule
// Emits a deterministic trace for external Python comparison. The event
// markers tell the checker which operations to apply to M1's reference model.
module tb_adsr_model_trace;
    logic sys_clk=0;
    always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0, sample_tick=0, note_on=0, note_off=0;
    logic [9:0] velocity=0;
    wire [15:0] envelope_level;
    wire [2:0] state_out;
    adsr_piano_envelope dut(.*);
    integer trace, count=0;
    string trace_path;
    task automatic do_reset;
        @(negedge sys_clk);
        sys_rst_n=0;sample_tick=0;note_on=0;note_off=0;
        repeat(4) @(negedge sys_clk);
        sys_rst_n=1;
        repeat(2) @(negedge sys_clk);
        $fdisplay(trace,"R");
    endtask
    task automatic do_on(input logic [9:0] v);
        @(negedge sys_clk);velocity=v;note_on=1;
        @(negedge sys_clk);note_on=0;
        // Complete two-stage synchronous ROM read before next audio tick.
        repeat(2) @(negedge sys_clk);
        $fdisplay(trace,"N %0d",v);
    endtask
    task automatic do_off;
        @(negedge sys_clk);note_off=1;
        @(negedge sys_clk);note_off=0;
        $fdisplay(trace,"F");
    endtask
    task automatic ticks(input integer n);
        repeat(n) begin
            @(negedge sys_clk);sample_tick=1;
            @(negedge sys_clk);sample_tick=0;
            count=count+1;
            $fdisplay(trace,"S %0d %0d",envelope_level,state_out);
            repeat(2) @(negedge sys_clk);
        end
    endtask
    initial begin
        if(!$value$plusargs("TRACE=%s",trace_path))$fatal(1,"TRACE path required");
        trace=$fopen(trace_path,"w");
        if(!trace)$fatal(1,"Cannot write trace: %s",trace_path);
        do_reset();do_on(1023);
        ticks(240);ticks(4800);ticks(24000);do_off();ticks(4800);
        do_reset();do_on(100);
        ticks(240);ticks(4800);ticks(24000);do_off();ticks(4800);
        do_reset();do_on(1023);
        ticks(240);ticks(4800);ticks(100);do_off();ticks(50);
        do_on(512);ticks(240);ticks(100);
        $fclose(trace);
        if(count<26000)$fatal(1,"Trace incomplete: %0d",count);
        $display("PASS tb_adsr_model_trace samples=%0d",count);
        $finish;
    end
    initial begin #8_000_000; $fatal(1,"Model trace timeout: %0d",count); end
endmodule
