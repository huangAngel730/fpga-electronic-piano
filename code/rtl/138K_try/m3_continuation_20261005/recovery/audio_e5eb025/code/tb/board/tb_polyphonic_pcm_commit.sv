// Four real DDS/ADSR lanes + commit path. PCM below is explicit test stimulus,
// NOT final wave*envelope scaling or the production sound reference.
`timescale 1ns/1ps
module tb_polyphonic_pcm_commit;
    import audio_defs_pkg::*;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,event_valid=0,frame_tick=0;
    logic [63:0] event_data=0;
    wire event_ready,calc_ready,sample_req,bank_valid,pipe_ready;
    wire [31:0] sample_req_id,bank_id,active_voice_count;
    wire [63:0] bank_envelopes,bank_waves;
    wire [127:0] bank_fcw;
    wire [3:0] bank_occupied;
    wire [11:0] bank_states;
    logic deliver=1,wrong_id=0;
    logic [2:0] stimulus=0;
    logic [95:0] lefts,rights;
    wire result_valid=bank_valid && deliver;
    wire result_ready=pipe_ready && deliver;
    wire [31:0] transport_id=wrong_id ? bank_id-1'b1 : bank_id;
    wire signed [23:0] play_left,play_right;
    wire pending_valid,commit_pulse;
    wire [31:0] audio_frame_count,pcm_request_count,pcm_commit_count,audio_underrun,clip_count;
    polyphonic_envelope_bank u_bank (
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .frame_tick(frame_tick),.sample_req(sample_req),.sample_req_id(sample_req_id),.calc_ready(calc_ready),
        .result_valid(bank_valid),.result_ready(result_ready),.result_req_id(bank_id),
        .result_envelopes(bank_envelopes),.result_waves(bank_waves),.result_fcw(bank_fcw),
        .result_occupied(bank_occupied),.result_states(bank_states),.active_voice_count(active_voice_count)
    );
    polyphonic_pcm_commit dut(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .sample_req(sample_req),.sample_req_id(sample_req_id),.result_valid(result_valid),
        .result_ready(pipe_ready),.result_req_id(transport_id),.voices_left(lefts),.voices_right(rights),
        .play_left(play_left),.play_right(play_right),.pending_valid(pending_valid),.commit_pulse(commit_pulse),
        .audio_frame_count(audio_frame_count),.pcm_request_count(pcm_request_count),
        .pcm_commit_count(pcm_commit_count),.audio_underrun(audio_underrun),.clip_count(clip_count)
    );
    always_comb begin
        lefts=0;rights=0;
        for(integer i=0;i<4;i++) begin
            case(stimulus)
                0:begin lefts[24*i+:24]=24'sd100+i;rights[24*i+:24]=-24'sd100-i;end
                1:begin lefts[24*i+:24]=24'sd2097152;rights[24*i+:24]=-24'sd2097152;end
                2:begin lefts[24*i+:24]=-24'sd3000000;rights[24*i+:24]=24'sd3000000;end
                default:begin lefts[24*i+:24]=24'sd55;rights[24*i+:24]=24'sd66;end
            endcase
        end
    end
    integer checks=0,seen_commits=0,seen_clips=0;
    logic signed [23:0] expected_l,expected_r;
    logic [31:0] held_id;
    task automatic check(input logic ok,input string label);
        checks++;if(ok!==1'b1)$fatal(1,"Commit %s req=%0d commits=%0d clips=%0d underrun=%0d",label,sample_req_id,pcm_commit_count,clip_count,audio_underrun);
    endtask
    task automatic next_frame;
        @(negedge clk);frame_tick=1;@(negedge clk);frame_tick=0;
    endtask
    task automatic commit_sample(input logic [2:0] mode,input integer expected_count,input integer expected_clips);
        @(negedge clk);stimulus=mode;
        next_frame();wait(pcm_commit_count==expected_count);repeat(3)@(negedge clk);
        check(pending_valid && clip_count==expected_clips,"one accepted stereo generation counts once");
        check(active_voice_count==4 && bank_occupied==4'b1111,"result generated after four live voice lanes");
    endtask
    always @(posedge clk) if(rst_n) begin
        check(commit_pulse===(dut.pcm_valid && dut.pcm_ready),"exported pulse equals actual commit, never stale or precommit valid");
    end
    always @(posedge clk) if(rst_n && commit_pulse) begin
        seen_commits++;
        check(dut.pcm_req_id==sample_req_id,"commit ID matches current frame");
        if(dut.pcm_clip_any)seen_clips++;
        case(stimulus)
            0:begin expected_l=406;expected_r=-406;end
            1:begin expected_l=24'sh7fffff;expected_r=24'sh800000;end
            2:begin expected_l=24'sh800000;expected_r=24'sh7fffff;end
            default:begin expected_l=220;expected_r=264;end
        endcase
        check(dut.pcm_left===expected_l && dut.pcm_right===expected_r,"mixer and held PCM share generation");
    end
    initial begin
        performance_event_t e;
        repeat(4)@(negedge clk);check(play_left==0 && play_right==0 && clip_count==0,"reset silence and counters");rst_n=1;
        for(integer i=0;i<4;i++)begin
            wait(event_ready);@(negedge clk);e='0;e.event_type=EVENT_NOTE_ON;e.note_number=60+i;e.velocity=1023;event_data=e;event_valid=1;
            @(negedge clk);event_valid=0;wait(event_ready);repeat(4)@(negedge clk);
        end
        commit_sample(0,1,0);check(play_left==406 && play_right==-406,"first pending sample is correct");
        commit_sample(1,2,1);check(play_left==24'sh7fffff && play_right==24'sh800000,"positive saturation with exact negative boundary");
        commit_sample(2,3,2);check(play_left==24'sh800000 && play_right==24'sh7fffff,"both clipping channels still count once");
        // Hold completed bank result across a frame: real upstream backpressure.
        @(negedge clk);deliver=0;next_frame();wait(bank_valid);@(negedge clk);held_id=bank_id;
        repeat(10)@(negedge clk);check(bank_valid && bank_id==held_id && pcm_commit_count==3 && clip_count==2,"held producer cannot commit or count prematurely");
        next_frame();check(!bank_valid && audio_underrun==1,"missing one frame repeats sample and expires held ID");
        wait(bank_valid);@(negedge clk);check(bank_id!=held_id,"fresh generation replaces expired result");deliver=1;
        wait(pcm_commit_count==4);repeat(3)@(negedge clk);check(clip_count==3,"only replacement clipped result counted");
        // Valid but stale request ID must not rescue the old frame or increment clip.
        @(negedge clk);wrong_id=1;next_frame();wait(bank_valid);repeat(10)@(negedge clk);
        check(!pipe_ready && pcm_commit_count==4 && clip_count==3,"stale ID rejected even with result_valid");
        next_frame();check(audio_underrun==2,"stale result causes exactly one later missing frame");
        @(negedge clk);wrong_id=0;stimulus=3;
        wait(pcm_commit_count==5);repeat(3)@(negedge clk);
        check(clip_count==3 && play_left==220 && play_right==264,"recover with clean new PCM and unchanged clip count");
        check(seen_commits==5 && seen_clips==3,"external handshake tally agrees with real counters");
        // A disabled producer must not emit requests or double-count old samples.
        @(negedge clk);deliver=0;next_frame();wait(bank_valid);@(negedge clk);rst_n=0;
        repeat(4)@(negedge clk);
        check(!pending_valid && !bank_valid && play_left==0 && play_right==0 && pcm_commit_count==0 && clip_count==0 && audio_underrun==0,"reset discards outstanding generation and clears all counters");
        $display("PASS polyphonic_pcm_commit checks=%0d commits=%0d clips=%0d",checks,seen_commits,seen_clips);$finish;
    end
    initial begin #2000000;$fatal(1,"Commit chain timeout");end
endmodule