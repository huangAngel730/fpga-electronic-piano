`timescale 1ns/1ps
// Independent frame/commit ledger. Synthetic stereo input; no sound claim.
module tb_output_transport;
    logic clk=0,pixel=0,rst_n=0,pixel_run=1;
    always #12.5 clk=~clk;
    always #20 if(pixel_run) pixel=~pixel;
    wire cancel,sv,rv_ready;
    wire [31:0] sid;
    logic rv=0,clipped=0;
    logic [31:0] rid=0;
    logic signed [23:0] l=0,r=0;
    wire signed [23:0] pl,pr,cl,cr,ol,orr,sl,srr;
    wire bclk,lrck,din,ft,commit,cc,ov,sample_valid;
    wire [31:0] fc,reqs,commits,under,clips,cid,oseq,sseq,drops;
    m2_n32_output_transport #(.OBS_DEPTH(2)) dut (
        .clk(clk),.pixel_clk(pixel),.rst_n(rst_n),.display_rst_n(rst_n),
        .candidate_cancel(cancel),.candidate_sample_valid(sv),.candidate_sample_ready(1'b1),.candidate_sample_id(sid),
        .candidate_result_valid(rv),.candidate_result_ready(rv_ready),.candidate_result_id(rid),
        .candidate_left(l),.candidate_right(r),.candidate_clipped(clipped),.play_left(pl),.play_right(pr),
        .bclk(bclk),.lrck(lrck),.din(din),.frame_tick(ft),.commit_pulse(commit),
        .frame_count(fc),.frame_request_count(reqs),.commit_count(commits),.underrun_count(under),.clip_count(clips),
        .committed_id(cid),.committed_left(cl),.committed_right(cr),.committed_clip(cc),
        .observed_valid(ov),.observed_seq(oseq),.observed_left(ol),.observed_right(orr),
        .sample_valid(sample_valid),.sample_seq(sseq),.sample_left(sl),.sample_right(srr),.observation_drop_count(drops)
    );
    integer delay_count=0;
    always @(posedge clk) begin
        if(!rst_n || ft) begin rv<=0;delay_count<=0;end
        else if(sv) begin
            rid<=sid;l<=sid[0] ? -24'sd123456 : 24'sd765432;
            r<=sid[0] ? 24'sd876543 : -24'sd234567;clipped<=sid[0];
            if(sid>=4 && sid<=6) delay_count<=0;else delay_count<=3;
        end else if(delay_count!=0) begin
            delay_count<=delay_count-1;if(delay_count==1) rv<=1;
        end else if(rv && rv_ready) rv<=0;
    end
    logic pending=0,ever=0,waiting_commit=0,expect_obs=0;
    logic signed [23:0] pend_l=0,pend_r=0,held_l=0,held_r=0,accepted_l=0,accepted_r=0,expected_ol=0,expected_or=0;
    logic [31:0] accepted_id=0;
    logic accepted_clip=0;
    integer ncommit=0,nclip=0,nunder=0,nframe=0,nobserve=0,npixel=0,last_frame=-1,cycle=0;
    logic rb,rl,rd,rft;
    // Original sender is reused; bit equality checks the NEW wiring only.
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) reference_sender(
        .clk(clk),.rst_n(rst_n),.valid(1'b1),.pcm_left(pending ? pend_l : held_l),
        .pcm_right(pending ? pend_r : held_r),.bclk(rb),.lrck(rl),.din(rd),.frame_tick(rft)
    );
    logic signed [23:0] observed_ledger_l[0:31],observed_ledger_r[0:31];
    always @(posedge clk) begin
        cycle=cycle+1;
        if(rst_n) begin
            if(pl!==(pending ? pend_l : held_l) || pr!==(pending ? pend_r : held_r)) $fatal(1,"PLAY_PCM_LEDGER_MISMATCH");
            if(expect_obs) begin
                if(!ov || oseq!==nobserve || ol!==expected_ol || orr!==expected_or) $fatal(1,"OBSERVED_PCM_NOT_SENDER_PRE_NBA_INPUT");
                observed_ledger_l[nobserve]=ol;observed_ledger_r[nobserve]=orr;nobserve=nobserve+1;
            end else if(ov) $fatal(1,"EXTRA_OBSERVATION");
            expect_obs=ft;expected_ol=pl;expected_or=pr;
            if(ft) begin
                if(last_frame>=0 && cycle-last_frame!=833 && cycle-last_frame!=834) $fatal(1,"FULL_FRAME_GAP");
                last_frame=cycle;nframe=nframe+1;waiting_commit=0;
                if(sv || rv_ready || commit) $fatal(1,"FRAME_EDGE_OLD_RESULT_ACCEPTED");
                if(pending) begin held_l=pend_l;held_r=pend_r;pending=0;ever=1;end
                else if(ever) nunder=nunder+1;
            end
            if(rv && rv_ready) begin
                if(waiting_commit) $fatal(1,"DOUBLE_RESULT");
                accepted_id=rid;accepted_l=l;accepted_r=r;accepted_clip=clipped;waiting_commit=1;
            end
            if(commit) begin
                if(!waiting_commit || cid!==accepted_id || cl!==accepted_l || cr!==accepted_r || cc!==accepted_clip) $fatal(1,"COMMIT_PCM_CLIP_LEDGER_MISMATCH");
                pend_l=accepted_l;pend_r=accepted_r;pending=1;waiting_commit=0;ncommit=ncommit+1;if(accepted_clip)nclip=nclip+1;
            end
            #1;
            if({bclk,lrck,din,ft}!=={rb,rl,rd,rft}) $fatal(1,"SERIAL_OUTPUT_CHANGED");
            if(commits!==ncommit || clips!==nclip || under!==nunder) $fatal(1,"COUNTER_LEDGER_MISMATCH");
        end
    end
    always @(negedge pixel) if(rst_n && sample_valid) begin
        if(sseq>=nobserve || sl!==observed_ledger_l[sseq] || srr!==observed_ledger_r[sseq]) $fatal(1,"PIXEL_PCM_LEDGER_MISMATCH");
        npixel=npixel+1;
    end
    initial begin
        repeat(6) @(negedge clk);rst_n=1;
        wait(fc==2);@(negedge clk);pixel_run=0;
        wait(fc==9);@(negedge clk);pixel_run=1;
        wait(fc==12);repeat(40) @(negedge clk);
        if(ncommit<6 || nclip<2 || nunder!=3 || drops==0 || npixel<2 || nobserve!=12) $fatal(1,"OUTPUT_COVERAGE_MISSING");
        $display("END frames=%0d commits=%0d clip=%0d underrun=%0d observed=%0d pixel=%0d drops=%0d",nframe,ncommit,nclip,nunder,nobserve,npixel,drops);
        @(negedge clk);rst_n=0;
        repeat(5) @(negedge clk);
        if(commits!==0 || clips!==0 || under!==0 || pl!==0 || pr!==0 || drops!==0) $fatal(1,"OUTPUT_RESET_NOT_CLEAN");
        $display("PASS OUTPUT_TRANSPORT_STEREO_CLIP_UNDERRUN_CDC");$finish;
    end
    initial begin #500us;$fatal(1,"OUTPUT_TIMEOUT");end
endmodule
