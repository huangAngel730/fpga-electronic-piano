`timescale 1ns/1ps
module tb_delay_transaction;
    parameter integer DEPTH=16;
    logic clk=0, rst_n=0, cancel=0, request_valid=0, result_ready=0;
    logic request_ready, result_valid;
    logic [31:0] request_id=0, result_id;
    logic signed [23:0] request_pcm=0, result_pcm;
    logic [15:0] delay_samples=0;
    logic [14:0] dry_gain=0, wet_gain=0, feedback=0;
    integer vectors, capture, count=0, n, reset_v, cancel_v, valid_v, ready_v;
    integer id_v, pcm_v, delay_v, dry_v, wet_v, fb_v;
    integer old_ptr;
    bit test_passed=0;
    always #10 clk=~clk;
    m3_delay_transaction_adapter #(.DEPTH(DEPTH)) dut(.*);
    initial begin
        vectors=$fopen("vectors.txt","r"); capture=$fopen("transaction.capture","w");
        if (!vectors || !capture) $fatal(1,"missing input/capture");
        $fdisplay(capture,"G1 %0d",DEPTH);
        while (!$feof(vectors)) begin
            n=$fscanf(vectors,"%d %d %d %d %d %d %d %d %d %d\n",
                reset_v,cancel_v,valid_v,id_v,pcm_v,delay_v,dry_v,wet_v,fb_v,ready_v);
            if (n!=10) $fatal(1,"bad vector");
            @(negedge clk);
            rst_n=reset_v; cancel=cancel_v; request_valid=valid_v; request_id=id_v;
            request_pcm=pcm_v; delay_samples=delay_v; dry_gain=dry_v;
            wet_gain=wet_v; feedback=fb_v; result_ready=ready_v;
            @(posedge clk);
            old_ptr=dut.u_effect.wr_ptr;
            $fwrite(capture,"C %0d %0d %0d %0d %0d %0d ",count,
                request_ready,result_valid,result_id,$signed(result_pcm),dut.u_effect.sample_enable);
            #1;
            $fdisplay(capture,"%0d %0d %0d %0d %0d %0d %0d %0d %0d",
                request_ready,result_valid,result_id,$signed(result_pcm),
                dut.u_effect.pcm_valid,$signed(dut.u_effect.pcm_out),
                old_ptr,dut.u_effect.wr_ptr,$signed(dut.u_effect.buffer[old_ptr]));
            count=count+1;
        end
        if(count<100) $fatal(1,"short vectors");
        $fdisplay(capture,"END %0d",count); $fclose(capture); $fclose(vectors);
        test_passed=1; $display("PASS G capture cycles=%0d depth=%0d",count,DEPTH); $finish;
    end
    initial begin #100000000; $fatal(1,"timeout"); end
endmodule
