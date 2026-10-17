// Monitor self-test: synthetic public-port stimuli, not a Pro DUT.
`timescale 1ns/1ps
module tb_pro_frame_monitor;
    reg clk=0,rst_n=0,pll_locked=0,audio_stable=0,pa_en=0;
    reg frame_tick=0,cancel=0,req_valid=0,req_ready=0,lane_tick=0;
    reg result_valid=0,result_ready=0,clipped=0,commit=0,commit_clipped=0,finish=0;
    reg [31:0] req_id=0,lane_req_id=0,result_id=0,commit_id=0;
    reg [63:0] req_payload=0;
    reg [1:0] lane=0;
    reg signed [23:0] left=0,right=0,commit_left=0,commit_right=0;
    reg bclk=0,ws=0,din=0,frame_enable=1;
    integer fault=0,countdown=20,phase=0,k;
    wire [31:0] accepted_count,committed_count,canceled_count,max_commit_cycles;
    always #12.5 clk=~clk;
    pro_frame_monitor #(.MAX_IDS(32)) monitor(.*);
    always @(negedge clk) begin
        frame_tick=0;
        if(!rst_n) begin countdown=20;phase=0;end
        else if(frame_enable) begin
            countdown=countdown-1;
            if(countdown==0) begin
                frame_tick=1;
                countdown=(fault==11) ? 833 : ((phase==2) ? 834 : 833);
                phase=(phase+1)%3;
                if(fault==10) countdown=800;
            end
        end
    end
    task reset_domain;
        begin
            @(negedge clk);rst_n=0;pll_locked=0;audio_stable=0;pa_en=0;
            req_valid=0;req_ready=0;result_valid=0;result_ready=0;commit=0;lane_tick=0;cancel=0;
            repeat(3) @(negedge clk);
            rst_n=1;pll_locked=1;audio_stable=1;
            // Remaining muted is legal after stable; no fixed 8-cycle PA policy.
            pa_en=0;
        end
    endtask
    task offer;
        input [31:0] id;
        input integer stalled;
        begin
            @(posedge frame_tick);@(negedge clk);
            req_id=id;req_payload={id,32'h55aa1234};req_valid=1;req_ready=!stalled;
            if(stalled) begin
                repeat(3) @(negedge clk);
                if(fault==1) req_valid=0;
                if(fault==2) req_payload=req_payload ^ 64'd1;
                @(negedge clk);req_ready=1;
            end
            @(negedge clk);req_valid=0;req_ready=0;
        end
    endtask
    task complete;
        input [31:0] id;
        begin
            for(k=0;k<4;k=k+1) begin
                lane_tick=1;lane=k;lane_req_id=id;
                if(fault==5 && k==3) lane=2;
                if(fault==6 && k==3) lane_tick=0;
                if(fault==19) lane_req_id=id^32'd1;
                @(negedge clk);
            end
            lane_tick=0;result_id=id;left=-24'sd65537;right=24'sd8388607;
            clipped=0;result_valid=1;result_ready=0;
            if(fault==3) result_id=id^32'd1;
            if(fault==20) left=24'bx;
            repeat(3) @(negedge clk);
            if(fault==4) left=left^24'd1;
            @(negedge clk);result_ready=1;
            @(negedge clk);
            if(fault==17) @(negedge clk);
            result_valid=0;result_ready=0;
            commit=1;commit_id=id;commit_left=left;commit_right=right;commit_clipped=clipped;
            if(fault==16) commit_clipped=1;
            @(negedge clk);commit=0;
        end
    endtask
    initial begin
        if(!$value$plusargs("FAULT=%d",fault)) fault=0;
        $display("MONITOR_FIXTURE_ONLY fault=%0d",fault);
        reset_domain();
        if(fault>=21 && fault<=24) begin
            offer(32'd7,0);frame_enable=0;
            // offer returns at the negedge following the accepting posedge.
            repeat((fault<=22) ? 832 : 831) @(negedge clk);
            if(fault==21 || fault==23) cancel=1;
            else begin rst_n=0;pa_en=0;end
            @(negedge clk);
            if(fault<=22) $fatal(1,"FAULT_ESCAPED");
            if(fault==23) cancel=0;
            else begin repeat(2) @(negedge clk);rst_n=1;end
            finish=1;@(negedge clk);
            if(accepted_count!=1 || committed_count!=0 || canceled_count!=1)
                $fatal(1,"SELFTEST_BOUNDARY_COUNTS");
            $display("PASS PRO_MONITOR_BOUNDARY_SELFTEST_ONLY");$finish;
        end else if(fault==12 || fault==13 || fault==14) begin
            @(negedge clk);pa_en=1;
            if(fault==12) pll_locked=0;
            if(fault==13) audio_stable=0;
            if(fault==14) rst_n=0;
            repeat(2) @(negedge clk);
        end else if(fault==10 || fault==11) begin
            repeat(6000) @(negedge clk);
        end else if(fault==7 || fault==8 || fault==9 || fault==15) begin
            offer(32'd7,0);
            if(fault==7) begin cancel=1;@(negedge clk);cancel=0;end
            if(fault==8) reset_domain();
            if(fault==7 || fault==8) begin result_valid=1;result_id=7;repeat(2) @(negedge clk);end
            if(fault==9) begin frame_enable=0;repeat(840) @(negedge clk);end
            if(fault==15) begin finish=1;@(negedge clk);end
        end else begin
            offer(32'hfffffffe,1);complete(32'hfffffffe);
            if(fault==18) begin offer(32'hfffffffe,0);end
            offer(32'hffffffff,0);complete(32'hffffffff);
            offer(32'd0,0);complete(32'd0);
            offer(32'd1,0);complete(32'd1);
            offer(32'd2,0);cancel=1;@(negedge clk);cancel=0;
            offer(32'd3,0);reset_domain();
            offer(32'd0,0);complete(32'd0);
            offer(32'd1,0);complete(32'd1);
            if(accepted_count!=8 || committed_count!=6 || canceled_count!=2)
                $fatal(1,"SELFTEST_COUNTS");
            finish=1;@(negedge clk);
            if(fault!=0) $fatal(1,"FAULT_ESCAPED");
            $display("PASS PRO_MONITOR_SELFTEST_ONLY");$finish;
        end
        $fatal(1,"FAULT_ESCAPED");
    end
    initial begin #1000000;$fatal(1,"SELFTEST_TIMEOUT");end
endmodule
