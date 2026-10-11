`timescale 1ns/1ps
// Test-only H bank + original gain/commit. No production source is edited.
// consumer_enable gates BOTH sides of the public result handshake, never force.
module tb_minclosure;
    logic clk=0;
    always #12.5 clk=~clk;
    logic rst_n=0,frame_tick=0,event_valid=0,consumer_enable=1;
    logic [63:0] event_data=0;
    wire event_ready,sample_req,calc_ready,bank_valid,bank_ready,raw_bank_ready;
    wire [31:0] sample_req_id,bank_id,active_voice_count;
    wire [63:0] bank_envelopes,bank_waves;
    wire [127:0] bank_fcw;
    wire [3:0] bank_occupied;
    wire [11:0] bank_states;
    wire [95:0] voices;
    wire signed [23:0] play_left,play_right;
    wire pending_valid,actual_commit;
    polyphonic_envelope_bank #(.PIANO_TIMBRE_ENABLE(1),
        .WAVE_ROM_FILE("rom/piano_band_4x256_8191.mem")) u_bank(
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),
        .event_data(event_data),.frame_tick(frame_tick),.sample_req(sample_req),
        .sample_req_id(sample_req_id),.calc_ready(calc_ready),
        .result_valid(bank_valid),.result_ready(bank_ready),.result_req_id(bank_id),
        .result_envelopes(bank_envelopes),.result_waves(bank_waves),
        .result_fcw(bank_fcw),.result_occupied(bank_occupied),
        .result_states(bank_states),.active_voice_count(active_voice_count));
    assign bank_ready=raw_bank_ready && consumer_enable;
    for(genvar i=0;i<4;i++)begin:g_gain
        wire signed [15:0] scaled;
        wire signed [23:0] pcm;
        voice_gain_q15_candidate u_gain(.wave_sample($signed(bank_waves[16*i+:16])),
            .envelope(bank_envelopes[16*i+:16]),.sample_out(scaled),.pcm_out(pcm));
        assign voices[24*i+:24]=bank_occupied[i] ? pcm : 24'd0;
    end
    polyphonic_pcm_commit u_commit(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .sample_req(sample_req),.sample_req_id(sample_req_id),
        .result_valid(bank_valid && consumer_enable),.result_ready(raw_bank_ready),
        .result_req_id(bank_id),.voices_left(voices),.voices_right(voices),
        .play_left(play_left),.play_right(play_right),.pending_valid(pending_valid),
        .commit_pulse(actual_commit),.audio_frame_count(),.pcm_request_count(),
        .pcm_commit_count(),.audio_underrun(),.clip_count());

    integer cycle=0,epoch=0,fd,stim_fd,scan_result,next_cycle,existing_capture;
    integer end_cycle,group_code,trace_all,edge_count=0,reset_count=0;
    logic was_reset=0;
    logic [3:0] next_flags;
    logic [63:0] next_event;
    string stimulus_path;
    initial begin
        if(!$value$plusargs("STIMULUS=%s",stimulus_path)
            || !$value$plusargs("END_CYCLE=%d",end_cycle)
            || !$value$plusargs("GROUP=%d",group_code))$fatal(1,"missing approved plan");
        if(group_code!=1 && group_code!=2)$fatal(1,"unknown minclosure group");
        trace_all=(group_code==2);
        stim_fd=$fopen(stimulus_path,"r");
        existing_capture=$fopen("minclosure.jsonl","r");
        if(existing_capture)begin
            $fclose(existing_capture);$fatal(1,"refuse existing capture");
        end
        fd=$fopen("minclosure.jsonl","w");
        if(!stim_fd || !fd)$fatal(1,"minclosure file open");
        scan_result=$fscanf(stim_fd,"%d %h %h\n",next_cycle,next_flags,next_event);
        if(scan_result!=3)$fatal(1,"missing schedule");
        $fdisplay(fd,"{\"tag\":\"META\",\"schema\":1,\"baseline\":\"H_pll_core40_route2\",\"region\":\"pre_NBA\",\"group\":%0d,\"sys_hz\":40000000,\"sample_hz\":48000,\"origin\":\"RTL\"}",group_code);
    end
    // All stimuli change at negedge; no driver/observer posedge races.
    always @(negedge clk)begin
        frame_tick=0;event_valid=0;event_data=0;
        if(scan_result==3 && next_cycle==cycle+1)begin
            rst_n=next_flags[0];frame_tick=next_flags[1];
            event_valid=next_flags[2];consumer_enable=next_flags[3];event_data=next_event;
            scan_result=$fscanf(stim_fd,"%d %h %h\n",next_cycle,next_flags,next_event);
            if(scan_result==3 && next_cycle<=cycle+1)$fatal(1,"schedule order");
            if(scan_result!=3 && scan_result!=-1)$fatal(1,"schedule grammar");
        end
    end
    `include "observer.svh"
    always @(posedge clk)begin
        // This is the sole writer of cycle/epoch, counts and capture records.
        cycle=cycle+1;
        if(!rst_n)begin
            if(!was_reset)begin
                epoch=epoch+1;reset_count=reset_count+1;
                $fdisplay(fd,"{\"tag\":\"RESET\",\"cycle\":%0d,\"epoch\":%0d}",cycle,epoch);
            end
            was_reset=1;
        end else begin
            was_reset=0;
            if(event_valid && !event_ready)$fatal(1,"scheduled event not accepted");
            if(trace_all || event_valid || frame_tick || sample_req || u_bank.lane_tick
                || bank_valid || u_commit.pcm_valid || (|u_bank.slot_note_on)
                || (|u_bank.slot_note_off) || (|u_bank.release_done) || u_bank.u_events.state==11)begin
                edge_count=edge_count+1;
                observe_edge();
            end
        end
        if(cycle==end_cycle)begin
            if(scan_result==3)$fatal(1,"unused schedule rows");
            $fdisplay(fd,"{\"tag\":\"END\",\"cycle\":%0d,\"counts\":{\"EDGE\":%0d,\"RESET\":%0d}}",cycle,edge_count,reset_count);
            $fclose(fd);$fclose(stim_fd);
            #1;$display("MINCLOSURE_CAPTURE_COMPLETE group=%0d (not a math PASS)",group_code);$finish;
        end
    end
endmodule
