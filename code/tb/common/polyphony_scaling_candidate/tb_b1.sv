`timescale 1ns/1ps
// Public ports only. This queue is a MOCK operator, not a sound engine.
module tb_b1;
`ifndef B1_N
`define B1_N 4
`endif
`ifndef B1_LATENCY
`define B1_LATENCY 1
`endif
`ifndef B1_MODE
`define B1_MODE 0
`endif
    parameter integer N=`B1_N, LATENCY=`B1_LATENCY, MODE=`B1_MODE;
    localparam CW=635, SW=$clog2(N), TW=72+SW;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, cancel=0, soft_reset=0;
    reg cfg_valid=0, ctl_valid=0, begin_valid=0, read_valid=0;
    wire cfg_ready, ctl_ready, begin_ready, read_ready;
    reg [SW-1:0] cfg_slot=0, read_slot=0;
    reg [39:0] cfg_identity=0;
    reg [1:0] cfg_flags=0;
    reg [CW-1:0] cfg_context=0;
    reg [7:0] ctl_identity=0;
    reg [28:0] ctl_value=0;
    reg ctl_pedal=0;
    reg [31:0] begin_request=0;
    wire req_valid, req_ready, req_pedal;
    wire [TW-1:0] req_tag;
    wire [CW-1:0] req_context;
    wire [1:0] req_flags;
    wire [28:0] req_control;
    reg req_gate=1, rom_stall=0, drain_auto=1;
    wire rom_in_ready, rom_out_valid, rom_empty;
    wire [TW-1:0] rom_out_tag;
    wire [15:0] rom_out_data;
    assign req_ready=req_gate && rom_in_ready;
    reg stim_valid=0, stim_owned=0;
    reg [TW-1:0] stim_tag=0;
    reg [CW-1:0] stim_context=0;
    reg auto_valid=0;
    reg [TW-1:0] auto_tag=0;
    reg [CW-1:0] auto_context=0;
    wire draining, drain_fault, busy, deadline_missed;
    wire res_valid=draining ? auto_valid : stim_valid;
    wire [TW-1:0] res_tag=draining ? auto_tag : stim_tag;
    wire [CW-1:0] res_context=draining ? auto_context : stim_context;
    wire res_ready, res_accepted;
    wire result_empty=!res_valid;
    reg [N-1:0] pending=0, rom_seen=0;
    reg [N-1:0] rom_visible=0;
    wire engine_empty=!(|pending);
    reg [TW-1:0] tags [0:N-1];
    reg [CW-1:0] results [0:N-1];
    reg [CW-1:0] expected [0:N-1];
    integer due [0:N-1], issued_at [0:N-1];
    integer cycle=0, issues=0, returns=0, commits=0;
    integer delay_cycles=5;
    reg commit_ready=0;
    wire commit_valid;
    wire [31:0] commit_request;
    wire read_out_valid;
    wire [CW-1:0] read_context;
    reg [SW-1:0] last_read_slot;
    reg prior_req_hold=0, prior_rom_hold=0, prior_commit_hold=0;
    reg [TW+CW+31:0] prior_req;
    reg [TW+15:0] prior_rom;
    reg [31:0] prior_commit;
    integer k, s, a, chosen;

    b1_scheduler #(.N(N)) dut (.*);
    b1_tagged_rom #(.TW(TW), .LATENCY(LATENCY)) rom (
        .clk(clk), .rst_n(rst_n), .drain(draining),
        .in_valid(req_valid && req_gate), .in_ready(rom_in_ready),
        .in_addr(req_context[7:0]), .in_tag(req_tag),
        .out_valid(rom_out_valid), .out_ready(!rom_stall),
        .out_data(rom_out_data), .out_tag(rom_out_tag), .empty(rom_empty)
    );

    function automatic [CW-1:0] fixture_result(
        input [CW-1:0] ctx, input [TW-1:0] tag,
        input [28:0] control, input [1:0] flags, input pedal
    );
        reg [CW-1:0] value;
        begin
            value=~ctx;
            value[31:0]=value[31:0] ^ tag[31:0] ^ (tag>>32) ^
                         control ^ (flags<<20) ^ (pedal ? 32'h80000000 : 0) ^ 32'h5a36c17e;
            fixture_result=value;
        end
    endfunction

    // A pending operation remains owned through its ROM read, latency and return.
    // No queue is cleared on cancel or LOCAL reset; only whole-domain rst_n clears it.
    always @(negedge clk) begin
        auto_valid=0;
        chosen=-1;
        for (k=0; k<N; k=k+1)
            if (pending[k] && rom_seen[k] && cycle>=due[k]) chosen=k;
        if (draining && drain_auto && chosen>=0) begin
            auto_valid=1;
            auto_tag=tags[chosen];
            auto_context=results[chosen];
        end
    end

    always @(posedge clk) begin
        cycle=cycle+1;
        if (!rst_n) begin
            pending=0; rom_seen=0; rom_visible=0; issues=0; returns=0;
            prior_req_hold=0; prior_rom_hold=0; prior_commit_hold=0;
            $display("B1 %0d COLD",cycle);
        end else begin
            if (prior_req_hold && !cancel && !soft_reset &&
                (!req_valid || {req_tag,req_context,req_flags,req_control,req_pedal} !== prior_req))
                $fatal(1,"CHECK_REQUEST_STABILITY");
            if (prior_rom_hold && (!rom_out_valid || {rom_out_tag,rom_out_data} !== prior_rom))
                $fatal(1,"CHECK_ROM_STABILITY");
            if (prior_commit_hold && !cancel && !soft_reset &&
                (!commit_valid || commit_request!==prior_commit)) $fatal(1,"CHECK_COMMIT_STABILITY");
            prior_req_hold=req_valid && !req_ready;
            prior_req={req_tag,req_context,req_flags,req_control,req_pedal};
            prior_rom_hold=rom_out_valid && !(!rom_stall || draining);
            prior_rom={rom_out_tag,rom_out_data};
            prior_commit_hold=commit_valid && !commit_ready;
            prior_commit=commit_request;
            if (busy && (cfg_ready || ctl_ready || begin_ready || read_ready))
                $fatal(1,"CHECK_ATOMIC_EVENT_LOCK");
            if (soft_reset) $display("B1 %0d SOFT",cycle);
            else if (cancel) $display("B1 %0d CANCEL",cycle);
            if (ctl_valid && ctl_ready)
                $display("B1 %0d CTRL %0h %0h %0d",cycle,ctl_identity,ctl_value,ctl_pedal);
            if (cfg_valid && cfg_ready) begin
                $display("B1 %0d CFG %0d %0h %0h %0h",cycle,cfg_slot,cfg_identity,cfg_flags,cfg_context);
                expected[cfg_slot]=cfg_context;
            end
            if (begin_valid && begin_ready) begin
                issues=0; returns=0;
                $display("B1 %0d BEGIN %0h",cycle,begin_request);
            end
            if (req_valid && req_ready) begin
                s=req_tag[SW-1:0];
                if (pending[s]) $fatal(1,"CHECK_OVERLAPPING_OWNERSHIP");
                tags[s]=req_tag;
                results[s]=fixture_result(req_context,req_tag,req_control,req_flags,req_pedal);
                pending[s]=1; rom_seen[s]=0; rom_visible[s]=0;
                due[s]=cycle+delay_cycles; issued_at[s]=cycle;
                issues=issues+1;
                $display("B1 %0d ISSUE %0h %0h %0h %0h %0d",cycle,req_tag,req_context,req_flags,req_control,req_pedal);
            end
            if (rom_out_valid && !rom_visible[rom_out_tag[SW-1:0]]) begin
                rom_visible[rom_out_tag[SW-1:0]]=1;
                $display("B1 %0d ROM_VISIBLE %0h",cycle,rom_out_tag);
            end
            if (rom_out_valid && (!rom_stall || draining)) begin
                s=rom_out_tag[SW-1:0];
                if (!pending[s] || rom_out_tag!==tags[s]) $fatal(1,"CHECK_ROM_TAG");
                // Address was ctx[7:0], recovered from NOT/XOR is not used: keep
                // independent address scoreboard from the accepted public port.
                if (cycle-issued_at[s]<LATENCY) $fatal(1,"CHECK_ROM_LATENCY");
                rom_seen[s]=1;
                $display("B1 %0d ROM %0h %0h",cycle,rom_out_tag,rom_out_data);
            end
            if (res_valid && res_ready) begin
                $display("B1 %0d RESULT %0h %0h %0d",cycle,res_tag,res_context,res_accepted);
                if (!draining && stim_valid && !stim_owned && res_accepted)
                    $fatal(1,"CHECK_TAG_GENERATION_OR_UNISSUED");
                if ((draining || stim_owned) && pending[res_tag[SW-1:0]] &&
                    res_tag===tags[res_tag[SW-1:0]]) begin
                    if (!rom_seen[res_tag[SW-1:0]]) $fatal(1,"CHECK_RETURN_BEFORE_ROM");
                    pending[res_tag[SW-1:0]]=0;
                    if (!draining) returns=returns+1;
                end
            end
            if (commit_valid) begin
                if (issues!=N || returns!=N) $fatal(1,"CHECK_ALL_N_BEFORE_COMMIT");
                if (commit_ready) begin
                    $display("B1 %0d COMMIT %0h %0d",cycle,commit_request,deadline_missed);
                    commits=commits+1;
                    for (a=0; a<N; a=a+1) expected[a]=results[a];
                end
            end
            if (draining) begin
                $display("B1 %0d DRAIN %0d %0d %0d %0d",cycle,rom_empty,engine_empty,result_empty,drain_fault);
                if (!rom_empty && !rom_out_valid)
                    $display("B1 %0d ROM_INFLIGHT_NOT_EMPTY",cycle);
            end
            if (read_valid && read_ready) begin
                last_read_slot=read_slot;
                $display("B1 %0d READ_REQ %0d",cycle,read_slot);
            end
            if (read_out_valid) begin
                $display("B1 %0d READ %0d %0h",cycle,last_read_slot,read_context);
                if (read_context!==expected[last_read_slot]) $fatal(1,"CHECK_BANK_ATOMIC_READBACK");
            end
            if (soft_reset) for (a=0; a<N; a=a+1) expected[a]=0;
        end
    end

    task automatic clocks(input integer count);
        integer j;
        begin for(j=0;j<count;j=j+1) @(negedge clk); end
    endtask
    task automatic cold;
        begin
            @(negedge clk); rst_n=0; cancel=0; soft_reset=0;
            stim_valid=0; cfg_valid=0; ctl_valid=0; begin_valid=0;
            req_gate=1; drain_auto=1; rom_stall=0; commit_ready=0;
            clocks(3); rst_n=1; clocks(2);
            for (integer j=0;j<N;j=j+1) expected[j]=0;
        end
    endtask
    task automatic configure(input [31:0] generation);
        integer j;
        reg [CW-1:0] value;
        begin
            for(j=0;j<256;j=j+1) begin
                @(negedge clk); ctl_valid=1; ctl_identity=j;
                ctl_value=(j*1234567)^29'h13579b; ctl_pedal=(j%3)==0;
                @(negedge clk); ctl_valid=0;
            end
            for(j=0;j<N;j=j+1) begin
                value=0; value[CW-1 -: 32]=32'h9abcdef0+j;
                value[31:0]=32'h13572400+j;
                @(negedge clk); cfg_valid=1; cfg_slot=j;
                cfg_identity={4'(j%16),4'((j*3+2)%16),generation};
                cfg_flags=(j%3==2) ? 3 : j%3; cfg_context=value;
                @(negedge clk); cfg_valid=0;
            end
        end
    endtask
    task automatic begin_frame(input [31:0] id);
        begin
            @(negedge clk); begin_valid=1; begin_request=id;
            while(!begin_ready) @(negedge clk);
            @(negedge clk); begin_valid=0;
        end
    endtask
    task automatic emit(input [TW-1:0] tag, input [CW-1:0] ctx, input owned);
        begin
            @(negedge clk); stim_valid=1; stim_tag=tag; stim_context=ctx; stim_owned=owned;
            @(negedge clk); stim_valid=0; stim_owned=0;
        end
    endtask
    task automatic wait_idle;
        integer j;
        begin
            j=0;
            while(busy && !drain_fault && j<100) begin clocks(1); j=j+1; end
            if (busy) $fatal(1,"CHECK_DRAIN_DID_NOT_RECOVER");
        end
    endtask
    task automatic read_all;
        integer j;
        begin
            for(j=0;j<N;j=j+1) begin
                @(negedge clk); read_valid=1; read_slot=j;
                @(negedge clk); read_valid=0;
                clocks(2);
            end
        end
    endtask
    task automatic complete_frame;
        integer j;
        begin
            wait(issues==N && (&rom_seen)); clocks(2);
            // Complete wrong generation/request/source/channel and duplicates.
            emit(tags[0] ^ ({{(TW-1){1'b0}},1'b1} << SW), 0, 0);
            emit(tags[0] ^ ({{(TW-1){1'b0}},1'b1} << (SW+40)), 0, 0);
            emit(tags[0] ^ ({{(TW-1){1'b0}},1'b1} << (SW+36)), 0, 0);
            emit(tags[0] ^ ({{(TW-1){1'b0}},1'b1} << (SW+32)), 0, 0);
            // Legal reorder: last slot deliberately left until every other slot.
            for(j=N-2;j>=0;j=j-1) emit(tags[j],results[j],1);
            emit(tags[0],results[0],0);
            clocks(3);
            if (commit_valid) $fatal(1,"CHECK_ALL_N_BEFORE_COMMIT");
            emit(tags[N-1],results[N-1],1);
            wait(commit_valid); clocks(4); // output backpressure, stable request
            @(negedge clk); commit_ready=1;
            @(negedge clk); commit_ready=0;
            wait_idle(); read_all();
        end
    endtask

    initial begin
        $display("B1_HEADER %0d %0d %0d",N,LATENCY,MODE);
        cold(); configure(32'hffffffff);
        $display("B1_CASE config_frame_read_port_priority");
        // A held begin must wait for the one accepted configuration write.
        @(negedge clk); cfg_valid=1; cfg_slot=0;
        cfg_identity=40'h02ffffffff; cfg_flags=0; cfg_context=expected[0];
        begin_valid=1; begin_request=7; read_valid=1; read_slot=0;
        @(negedge clk);
        if (busy) $fatal(1,"CHECK_CONFIG_PRIORITY");
        cfg_valid=0; read_valid=0;
        @(negedge clk); begin_valid=0;
        complete_frame();
        $display("B1_CASE normal_backpressure_reorder_all_identities");
        req_gate=0; rom_stall=1;
        begin_frame(32'hffffffff);
        // Unissued result, including a slot whose complete identity is known.
        emit({32'hffffffff,40'h02ffffffff,{SW{1'b0}}},0,0);
        wait(req_valid); clocks(3);
        cfg_valid=1; ctl_valid=1; clocks(3); cfg_valid=0; ctl_valid=0;
        req_gate=1;
        wait(rom_out_valid); clocks(3); rom_stall=0;
        complete_frame();
        $display("B1_CASE wrap_full_tag_reuse_after_real_empty");
        // Same full request/identity first, then modulo32 wrap; permitted only
        // after real queue/ROM ownership is empty.
        begin_frame(32'hffffffff); complete_frame();
        configure(0); begin_frame(0); complete_frame();

        if (MODE==1) begin
            $display("B1_CASE slow_operator_deadline_not_audio_budget");
            delay_cycles=1000;
            begin_frame(1);
            wait(issues==N && (&rom_seen));
            clocks(1005);
            complete_frame();
            if (!deadline_missed) $fatal(1,"CHECK_SLOW_DEADLINE");
        end else begin
            // Cancel and local reset at read/capture/offer/return/held commit.
            for(integer phase=0;phase<6;phase=phase+1) begin
                for(integer reset_kind=0;reset_kind<2;reset_kind=reset_kind+1) begin
                    $display("B1_CASE abort_%0d_%0d",phase,reset_kind);
                    begin_frame(100+phase*2+reset_kind);
                    if (phase==1) clocks(1);
                    if (phase==2) begin req_gate=0; wait(req_valid); clocks(2); end
                    if (phase==3) begin wait(issues>=1); clocks(1); end
                    if (phase==4) begin wait(issues==N); clocks(1); end
                    if (phase==5) begin
                        wait(issues==N && (&rom_seen));
                        for(integer j=N-1;j>=0;j=j-1) emit(tags[j],results[j],1);
                        wait(commit_valid); clocks(2);
                    end
                    if(reset_kind) soft_reset=1; else cancel=1;
                    @(negedge clk); soft_reset=0; cancel=0; req_gate=1;
                    wait_idle(); read_all();
                    configure(phase+reset_kind+20);
                    begin_frame(100+phase*2+reset_kind); complete_frame();
                end
            end
            $display("B1_CASE timeout_local_reset_cannot_extend_fence");
            drain_auto=0; begin_frame(200);
            wait(issues>=1);
            @(negedge clk); cancel=1;
            clocks(2); cancel=0;
            for(integer j=0;j<N+16;j=j+1) begin
                soft_reset=j%2; cancel=!(j%2); clocks(1);
            end
            soft_reset=0; cancel=0;
            if (!drain_fault || begin_ready || cfg_ready) $fatal(1,"CHECK_FAIL_CLOSED_TIMEOUT");
            $display("B1_CASE whole_domain_reset_recovery");
            cold(); configure(0); begin_frame(0); complete_frame();
        end
        $display("B1_END %0d %0d",cycle,commits);
        $finish;
    end
    initial begin #1000000; $fatal(1,"CHECK_TEST_TIMEOUT"); end
endmodule
