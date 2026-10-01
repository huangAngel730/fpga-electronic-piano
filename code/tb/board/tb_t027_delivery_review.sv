// M2 receipt-only test: candidate RTL is compiled from ignored output.
// No production signal forcing; internal phase is observed only to prove reset.
`timescale 1ns/1ps
module tb_t027_delivery_review;
    logic clk=0, rst_n=0, sample_tick=0, timbre_select=0;
    logic note_on=0, note_off=0;
    logic [31:0] fcw=0;
    wire signed [15:0] sample_out;
    wire sample_valid;
    logic signed [15:0] sine [0:1023], triangle [0:1023];
    integer errors=0, checks=0, n, streaming_errors, sparse_errors;
    integer active_switch_errors, release_errors, phase_errors;
    integer expected_addr [0:2];
    logic expected_valid [0:2];
    logic expected_timbre [0:2];
    integer pre_addr, j, local_errors, valid_count;
    logic [31:0] saved_phase;
    logic signed [15:0] expected_sample;
    timbre_oscillator dut (.*);
    always #10 clk=~clk;
    task automatic cycle;
        @(posedge clk); #1;
        @(negedge clk);
    endtask
    task automatic reset;
        rst_n=0; sample_tick=0; note_on=0; note_off=0; timbre_select=0;fcw=0;
        repeat(5) cycle();
        checks=checks+1;
        if(sample_valid!==0 || sample_out!==0) begin
            $display("ERROR reset did not clear output"); errors=errors+1;
        end
        for(j=0;j<3;j=j+1) begin
            expected_valid[j]=0;expected_addr[j]=0;expected_timbre[j]=0;
        end
        rst_n=1; cycle(); note_on=1;cycle();note_on=0;
    endtask
    task automatic pipeline_test(input bit sparse);
        reset();fcw=32'h00400000;local_errors=0;
        for(n=0;n<80;n=n+1) begin
            sample_tick=sparse ? (n%9==0) : 1;
            pre_addr=dut.phase_acc[31:22];
            for(j=2;j>0;j=j-1) begin
                expected_addr[j]=expected_addr[j-1];
                expected_valid[j]=expected_valid[j-1];
                expected_timbre[j]=expected_timbre[j-1];
            end
            expected_addr[0]=pre_addr;
            expected_valid[0]=sample_tick;
            expected_timbre[0]=timbre_select;
            @(posedge clk); #1;
            checks=checks+1;
            if(sample_valid!==expected_valid[2]) begin
                local_errors=local_errors+1;
            end else if(sample_valid) begin
                expected_sample=expected_timbre[2] ? triangle[expected_addr[2]] : sine[expected_addr[2]];
                if(sample_out!==expected_sample) begin
                    if(local_errors<3) $display("ERROR pipeline sparse=%0d input_addr=%0d expected=%0d actual=%0d",sparse,expected_addr[2],expected_sample,sample_out);
                    local_errors=local_errors+1;
                end
            end
            @(negedge clk);
        end
        errors=errors+local_errors;
        if(sparse) sparse_errors=local_errors;else streaming_errors=local_errors;
    endtask
    initial begin
        $readmemh("sine_wavetable.hex",sine);
        $readmemh("triangle_wavetable.hex",triangle);
        for(n=0;n<1024;n=n+1) begin
            if(^sine[n]===1'bx || ^triangle[n]===1'bx)
                $fatal(1,"Incomplete receipt ROM at address %0d",n);
        end
        @(negedge clk);
        pipeline_test(0);pipeline_test(1);
        reset();fcw=32'h20000000;sample_tick=1;cycle();
        fcw=0;repeat(8)cycle();timbre_select=1;repeat(8)cycle();
        checks=checks+1;active_switch_errors=0;
        if(sample_out!==sine[128]) begin
            $display("ERROR sounding-note timbre changed: sine=%0d actual=%0d",sine[128],sample_out);
            active_switch_errors=1;errors=errors+1;
        end
        reset();fcw=32'h00400000;sample_tick=1;repeat(12)cycle();
        saved_phase=dut.phase_acc;note_off=1;cycle();note_off=0;
        repeat(5)cycle();valid_count=0;
        repeat(12) begin cycle(); if(sample_valid)valid_count=valid_count+1;end
        checks=checks+1;release_errors=0;
        if(valid_count!=12 || dut.phase_acc===saved_phase+fcw) begin
            $display("ERROR release oscillator stopped: valid_count=%0d/12",valid_count);
            release_errors=1;errors=errors+1;
        end
        reset();fcw=32'h00400000;sample_tick=1;repeat(12)cycle();
        sample_tick=0;saved_phase=dut.phase_acc;note_on=1;cycle();note_on=0;
        checks=checks+1;phase_errors=0;
        if(dut.phase_acc!==saved_phase) begin
            $display("ERROR retrigger phase reset: before=%h after=%h",saved_phase,dut.phase_acc);
            phase_errors=1;errors=errors+1;
        end
        reset();
        $display("RESULT checks=%0d stream_errors=%0d sparse_errors=%0d active_switch_errors=%0d release_errors=%0d phase_errors=%0d total_errors=%0d",checks,streaming_errors,sparse_errors,active_switch_errors,release_errors,phase_errors,errors);
        if(errors) $fatal(1,"T027 candidate rejected by M2 receipt test");
        $display("PASS T027 receipt RTL");$finish;
    end
endmodule
