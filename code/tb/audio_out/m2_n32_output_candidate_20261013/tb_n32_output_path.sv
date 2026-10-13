`timescale 1ns/1ps
// Short real N32/pROM to sender and observation path; not sound golden replay.
module tb_n32_output_path;
    import audio_defs_pkg::*;
    logic clk=0,pixel=0,rst_n=0,event_valid=0,read_valid=0;
    always #12.5 clk=~clk;
    always #20 pixel=~pixel;
    GSR GSR(.GSRI(1'b1));
    logic [63:0] event_data=0;
    wire er,sv,sready,rv,rready,cancel,fault,idle,clip,ft,commit,cc,ov;
    wire [31:0] sid,rid,fc,reqs,commits,under,clips,cid,oseq;
    wire signed [23:0] l,r,pl,pr,cl,cr,ol,orr;
    wire [31:0] occupied;
    m2_b2d_event_audio_prom #(.N(32),.RESPONSE(1)) source (
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.event_valid(event_valid),.event_ready(er),.event_data(event_data),
        .sample_valid(sv),.sample_ready(sready),.sample_id(sid),.result_valid(rv),.result_ready(rready),
        .result_id(rid),.left(l),.right(r),.clipped(clip),.fault(fault),.idle(idle),.occupied(occupied),
        .read_valid(read_valid),.read_slot(5'd0),.inject_valid(1'b0),.inject_tag(77'd0),.inject_context(74'd0)
    );
    m2_n32_output_transport dut (
        .clk(clk),.pixel_clk(pixel),.rst_n(rst_n),.display_rst_n(rst_n),
        .candidate_cancel(cancel),.candidate_sample_valid(sv),.candidate_sample_ready(sready),.candidate_sample_id(sid),
        .candidate_result_valid(rv),.candidate_result_ready(rready),.candidate_result_id(rid),
        .candidate_left(l),.candidate_right(r),.candidate_clipped(clip),.play_left(pl),.play_right(pr),
        .frame_tick(ft),.commit_pulse(commit),.frame_count(fc),.frame_request_count(reqs),.commit_count(commits),
        .underrun_count(under),.clip_count(clips),.committed_id(cid),.committed_left(cl),.committed_right(cr),
        .committed_clip(cc),.observed_valid(ov),.observed_seq(oseq),.observed_left(ol),.observed_right(orr)
    );
    integer accepted=0,results=0,ncommits=0,nonzero=0,observed=0,blocked=0;
    logic expected_pending=0,expect_obs=0;
    logic [31:0] expected_id=0;
    logic signed [23:0] expected_l=0,expected_r=0,obs_l=0,obs_r=0;
    logic expected_clip=0;
    always @(posedge clk) if(rst_n) begin
        if(fault) $fatal(1,"N32_OUTPUT_FAULT");
        if(expect_obs) begin
            if(!ov || ol!==obs_l || orr!==obs_r || oseq!==observed) $fatal(1,"N32_OUTPUT_OBSERVATION_MISMATCH");
            observed=observed+1;
        end
        expect_obs=ft;obs_l=pl;obs_r=pr;
        if(ft) begin expected_pending=0;if(sv || commit || rready)$fatal(1,"N32_OUTPUT_FRAME_HANDSHAKE");end
        if(sv && !sready)blocked=blocked+1;
        if(sv && sready)accepted=accepted+1;
        if(rv && rready)begin
            results=results+1;expected_pending=1;expected_id=rid;expected_l=l;expected_r=r;expected_clip=clip;
        end
        if(commit)begin
            if(!expected_pending || cid!==expected_id || cl!==expected_l || cr!==expected_r || cc!==expected_clip)
                $fatal(1,"N32_OUTPUT_COMMIT_MISMATCH");
            expected_pending=0;ncommits=ncommits+1;if(cl!=0 || cr!=0)nonzero=nonzero+1;
        end
    end
    integer k,start_frame;
    initial begin
        repeat(8)@(negedge clk);rst_n=1;
`ifdef M2_OUTPUT_FULL32
        for(k=0;k<32;k=k+1) begin
            @(negedge clk);event_data={EVENT_NOTE_ON,4'(k/16),4'(k%16),7'd81,10'd1023,10'd0,8'd0,12'd0,6'd0};event_valid=1;
            while(!er)@(negedge clk);
            @(negedge clk);event_valid=0;
        end
`else
        @(negedge clk);event_data={EVENT_NOTE_ON,4'd1,4'd0,7'd69,10'd900,10'd0,8'd0,12'd0,6'd0};event_valid=1;
        while(!er)@(negedge clk);
        @(negedge clk);event_valid=0;
`endif
        repeat(30)@(negedge clk);start_frame=fc;
        wait(fc==start_frame+2);@(negedge clk);read_valid=1;
        repeat(1500)@(negedge clk);read_valid=0;
        wait(fc==start_frame+12);repeat(500)@(negedge clk);
`ifdef M2_OUTPUT_FULL32
        if(occupied!==32'hffffffff)$fatal(1,"N32_OUTPUT_FULL32_OCCUPANCY_MISSING");
`else
        if(occupied!==32'd1)$fatal(1,"N32_OUTPUT_NOTE_OCCUPANCY_MISSING");
`endif
        if(ncommits<7 || nonzero<5 || results!=ncommits || under<1 || blocked<100 || observed!=fc)
            $fatal(1,"N32_OUTPUT_COVERAGE_MISSING");
        $display("END frames=%0d accepted=%0d results=%0d commits=%0d nonzero=%0d observed=%0d read_blocked=%0d underrun=%0d occupied=%h",fc,accepted,results,ncommits,nonzero,observed,blocked,under,occupied);
        @(negedge clk);rst_n=0;repeat(5)@(negedge clk);
        if(commits!==0 || under!==0 || pl!==0 || pr!==0)$fatal(1,"N32_OUTPUT_RESET");
        $display("PASS N32_PROM_OUTPUT_PATH_READ_RECOVERY NO_NEW_SOUND_GOLDEN");$finish;
    end
    initial begin #500us;$fatal(1,"N32_OUTPUT_TIMEOUT");end
endmodule
