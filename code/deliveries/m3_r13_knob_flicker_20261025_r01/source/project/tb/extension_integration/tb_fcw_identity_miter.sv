`timescale 1ns/1ps
module tb_fcw_identity_miter;
    logic clk=0,rst_n=0,en=0,note_on=0;
    logic signed[11:0]bend=0;
    logic[11:0]modulation=0;
    logic[4:0]pitch_range=0;
    logic[31:0]base_fcw=0;
    wire[31:0]actual,reference;
    wire actual_valid,reference_valid;
    integer comparisons=0,valid_results=0,resets=0;
    always #12.5 clk=~clk;
    m1td_pitch_mod_fcw_pipeline dut(.sys_clk(clk),.sys_rst_n(rst_n),
        .sample_enable(en),.note_on(note_on),.bend(bend),.modulation(modulation),
        .pitch_range(pitch_range),.base_fcw(base_fcw),.fcw_out(actual),.fcw_valid(actual_valid));
    m1td_pitch_mod_fcw_reference ref_dut(.sys_clk(clk),.sys_rst_n(rst_n),
        .sample_enable(en),.note_on(note_on),.bend(bend),.modulation(modulation),
        .pitch_range(pitch_range),.base_fcw(base_fcw),.fcw_out(reference),.fcw_valid(reference_valid));
    always @(posedge clk)begin
        #1;
        if(actual_valid!==reference_valid || actual!==reference)
            $fatal(1,"FCW identity mismatch cycle=%0d actual=%h/%b ref=%h/%b",
                comparisons,actual,actual_valid,reference,reference_valid);
        comparisons=comparisons+1;
        if(actual_valid)valid_results=valid_results+1;
    end
    initial begin
        #2;rst_n=0;#2;
        repeat(3)@(negedge clk);rst_n=1;
        for(integer i=0;i<20000;i=i+1)begin
            @(negedge clk);
            en=(i%23<16);note_on=(i%29==0);
            bend=(i<4096) ? i : $urandom;
            modulation=(i<4096) ? i : $urandom;
            pitch_range=i%25;base_fcw=$urandom;
            if(i%7==0)base_fcw=0;
            if(i%7==1)base_fcw=32'h80000000;
            if(i%7==2)base_fcw=32'hffffffff;
            if(i%313==0)begin rst_n=0;#3;rst_n=1;resets=resets+1;end
        end
        @(negedge clk);en=0;note_on=0;
        repeat(10)@(negedge clk);
        if(valid_results<10000 || resets<60)$fatal(1,"coverage missing");
        $display("FCW_IDENTITY_MITER_COMPLETE comparisons=%0d valid=%0d async_resets=%0d",
            comparisons,valid_results,resets);
        $finish;
    end
    initial begin #1000000;$fatal(1,"watchdog");end
endmodule
