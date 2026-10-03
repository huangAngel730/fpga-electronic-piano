`timescale 1ns/1ps
// H: TB wiring only, mono effect copied to L/R. No production core edit.
module tb_delay_pcm;
    import audio_defs_pkg::*;
    parameter integer DEPTH=16;
    logic clk=0, rst_n=0, frame_tick=0, frames_enable=0;
    logic event_valid=0;
    performance_event_t event_data;
    wire event_ready, calc_ready, sample_req, bank_valid, bank_ready;
    wire [31:0] sample_req_id, bank_id, active_count;
    wire [63:0] envelopes, waves;
    wire [127:0] fcws;
    wire [3:0] occupied;
    wire [11:0] states;
    wire [95:0] real_voices;
    logic [95:0] mixer_voices;
    wire signed [23:0] mixed_left, mixed_right;
    wire clip_left, clip_right, clip_any;
    logic cancel=0, allow_results=1;
    logic [15:0] delay_samples=1;
    logic [14:0] dry_gain=32767,wet_gain=32767,feedback=16384;
    wire effect_valid, effect_ready, effect_request_ready;
    wire [31:0] effect_id, pcm_id;
    wire signed [23:0] effect_pcm, pcm_left,pcm_right,play_left,play_right;
    wire pcm_valid,pcm_ready,pcm_clip,pending_valid,hold_ready;
    wire [31:0] frame_count,request_count,commit_count,underruns;
    integer fixture_mode=0,cycle=0,ticks_left=1,cadence=0,fd;
    integer normal_frames=0,tail_requests=0,cancel_count=0,checks=0;
    integer old_ptr,last_frame=0,phase_label=0;
    bit test_passed=0,was_reset=0;
    always #10 clk=~clk;

    polyphonic_envelope_bank #(.PIANO_TIMBRE_ENABLE(1),.WAVE_ROM_FILE("wave.mem")) bank(
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .frame_tick(frame_tick),.sample_req(sample_req),.sample_req_id(sample_req_id),.calc_ready(calc_ready),
        .result_valid(bank_valid),.result_ready(bank_ready),.result_req_id(bank_id),
        .result_envelopes(envelopes),.result_waves(waves),.result_fcw(fcws),
        .result_occupied(occupied),.result_states(states),.active_voice_count(active_count));
    for(genvar k=0;k<4;k++)begin:g_gain
        wire signed [15:0] scaled;
        wire signed [23:0] pcm;
        voice_gain_q15_candidate gain(.wave_sample($signed(waves[16*k+:16])),
            .envelope(envelopes[16*k+:16]),.sample_out(scaled),.pcm_out(pcm));
        assign real_voices[24*k+:24]=occupied[k] ? pcm : 24'd0;
    end
    // Explicit boundary fixtures enter the REAL mixer; normal mode uses bank.
    always @* begin
        mixer_voices=real_voices;
        case(fixture_mode)
            1:mixer_voices={72'd0,24'sd4000000};
            2:mixer_voices=0;
            3:mixer_voices={4{24'h7fffff}};
            4:mixer_voices={4{24'h800000}};
            default:;
        endcase
    end
    pcm_mixer_4voice mixer(.voices_left(mixer_voices),.voices_right(mixer_voices),
        .mixed_left(mixed_left),.mixed_right(mixed_right),.clip_left(clip_left),.clip_right(clip_right),.clip_any(clip_any));
    assign bank_ready=effect_request_ready;
    m3_delay_transaction_adapter #(.DEPTH(DEPTH)) effect(
        .clk(clk),.rst_n(rst_n),.cancel(cancel),.request_valid(bank_valid),.request_ready(effect_request_ready),
        .request_id(bank_id),.request_pcm(mixed_left),.delay_samples(delay_samples),
        .dry_gain(dry_gain),.wet_gain(wet_gain),.feedback(feedback),
        .result_valid(effect_valid),.result_ready(effect_ready),.result_id(effect_id),.result_pcm(effect_pcm));
    assign effect_ready=hold_ready && allow_results;
    pcm_result_hold result_hold(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),.current_req_id(sample_req_id),
        .result_valid(effect_valid && allow_results),.result_ready(hold_ready),.result_req_id(effect_id),
        .result_left(effect_pcm),.result_right(effect_pcm),.result_clip_any(1'b0),
        .pcm_valid(pcm_valid),.pcm_ready(pcm_ready),.pcm_req_id(pcm_id),
        .pcm_left(pcm_left),.pcm_right(pcm_right),.pcm_clip_any(pcm_clip));
    pcm_frame_buffer frame_buffer(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),.calc_ready(calc_ready),
        .sample_req(sample_req),.sample_req_id(sample_req_id),.pcm_valid(pcm_valid),.pcm_ready(pcm_ready),
        .pcm_req_id(pcm_id),.pcm_left(pcm_left),.pcm_right(pcm_right),.play_left(play_left),.play_right(play_right),
        .pending_valid(pending_valid),.audio_frame_count(frame_count),.pcm_request_count(request_count),
        .pcm_commit_count(commit_count),.audio_underrun(underruns));

    task automatic check(input logic ok,input string label);
        checks++;
        if(ok!==1'b1)$fatal(1,"H assertion %s cycle=%0d",label,cycle);
    endtask
    always @(negedge clk)begin
        frame_tick=0;
        if(rst_n && frames_enable)begin
            if(ticks_left==0)begin
                frame_tick=1;ticks_left=(cadence%3==0 ? 1041 : 1042)-1;cadence++;
            end else ticks_left--;
        end else begin ticks_left=1;cadence=0;end
    end
    always @(posedge clk)begin
        cycle++;
        if(!rst_n)begin
            if(!was_reset)$fdisplay(fd,"R %0d",cycle);
            was_reset=1;last_frame=0;
            #1;check(!effect_valid && !pcm_valid && !pending_valid && play_left==0,"reset silence");
        end else begin
            was_reset=0;
            if(cancel)begin cancel_count++;$fdisplay(fd,"X %0d",cycle);end
            if(frame_tick)begin
                if(last_frame!=0)check(cycle-last_frame==1041 || cycle-last_frame==1042,"frame cadence");
                last_frame=cycle;
                $fdisplay(fd,"K %0d %0d %0d %0d %0d %0d %0d",cycle,sample_req_id,pending_valid,
                    $signed(play_left),$signed(play_right),underruns,phase_label);
                if(phase_label==1)begin
                    check(pending_valid && active_count==4,"normal fourvoice frame no underrun");normal_frames++;
                end
            end
            if(bank_valid && bank_ready)begin
                check(bank_id==sample_req_id,"bank frame id");
                check(mixed_left==mixed_right,"mono mix");
                $fdisplay(fd,"B %0d %0d %h %h %h %h %h %0d %0d %0d",cycle,bank_id,waves,envelopes,
                    occupied,real_voices,mixer_voices,$signed(mixed_left),fixture_mode,active_count);
                $fdisplay(fd,"E %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,bank_id,$signed(mixed_left),
                    delay_samples,dry_gain,wet_gain,feedback,fixture_mode,active_count);
                if(active_count==0 && fixture_mode==0)tail_requests++;
            end
            if(effect_valid)begin
                check(effect_id==sample_req_id,"wrong effect frame id");
                $fdisplay(fd,"O %0d %0d %0d %0d",cycle,effect_id,$signed(effect_pcm),effect_ready);
            end
            if(pcm_valid)check(pcm_id==sample_req_id,"PCM frame id");
            if(pcm_valid && pcm_ready)begin
                check(pcm_id==sample_req_id,"PCM frame id");
                $fdisplay(fd,"C %0d %0d %0d %0d",cycle,pcm_id,$signed(pcm_left),$signed(pcm_right));
            end
            old_ptr=effect.u_effect.wr_ptr;
            #1;
            if(effect.u_effect.pcm_valid)$fdisplay(fd,"W %0d %0d %0d %0d",cycle,old_ptr,
                effect.u_effect.wr_ptr,$signed(effect.u_effect.buffer[old_ptr]));
        end
    end
    task automatic frames(input integer count);
        repeat(count)begin @(posedge clk);wait(frame_tick);@(negedge clk);end
    endtask
    task automatic send(input performance_event_t message);
        @(negedge clk);event_data=message;event_valid=1;
        @(posedge clk);while(!event_ready)@(posedge clk);
        @(negedge clk);event_valid=0;repeat(8)@(negedge clk);
    endtask
    task automatic reset_now;
        @(negedge clk);rst_n=0;event_valid=0;cancel=0;allow_results=1;
        repeat(4)@(negedge clk);rst_n=1;repeat(6)@(negedge clk);
    endtask
    function automatic performance_event_t control(input logic pitch,input logic[11:0] value);
        performance_event_t ev;
        ev='0;ev.source_id=1;ev.channel=0;
        ev.event_type=pitch ? EVENT_PITCH_BEND : EVENT_CONTROL_CHANGE;
        ev.control_id=pitch ? CTRL_PITCH_BEND : CTRL_MODULATION;
        ev.control_value=value;return ev;
    endfunction
    initial begin:stimulus
        integer limit;
        fd=$fopen("delay_pcm.capture","w");if(!fd)$fatal(1,"capture open");
        $fdisplay(fd,"H1 %0d",DEPTH);
        reset_now();frames_enable=1;
        // Real V1 four voices, independent channel controls and CC64 lifecycle.
        send(make_note_event(1'b1,1,0,60,900));
        send(make_note_event(1'b1,1,0,64,800));
        send(make_note_event(1'b1,1,0,67,700));
        send(make_note_event(1'b1,1,0,72,1000));
        send(control(1'b1,12'd500));
        send(control(1'b0,12'd1800));
        frames(4);wet_gain=0;frames(16);wet_gain=32767;
        phase_label=1;delay_samples=DEPTH-1;
        frames(512);phase_label=0;
        send(make_sustain_event(1,0,7'd127));
        send(make_note_event(1'b0,1,0,60,0));
        send(make_note_event(1'b0,1,0,64,0));
        send(make_note_event(1'b0,1,0,67,0));
        send(make_note_event(1'b0,1,0,72,0));
        frames(4);check(active_count==4,"CC64 deferred voices");
        send(make_sustain_event(1,0,7'd0));
        limit=0;while(active_count!=0 && limit<4900)begin frames(1);limit++;end
        check(active_count==0,"real release retires voices");
        phase_label=2;frames(DEPTH+64);phase_label=0;
        // Labelled mixer fixtures, not counted as real fourvoice normal frames.
        fixture_mode=1;delay_samples=1;frames(1);
        fixture_mode=2;frames(32);
        fixture_mode=3;frames(8);fixture_mode=4;frames(8);fixture_mode=2;
        // Cancel before raw write, on raw write, after write, and held output.
        for(integer age=1;age<=4;age++)begin
            allow_results=0;
            wait(bank_valid && bank_ready);@(posedge clk);
            repeat(age)@(negedge clk);cancel=1;
            repeat(3)@(negedge clk);cancel=0;allow_results=1;
            frames(3);
        end
        fixture_mode=1;frames(1);fixture_mode=2;
        wait(bank_valid && bank_ready);@(posedge clk);reset_now();
        phase_label=3;frames(8);phase_label=0;
        check(normal_frames>=512 && tail_requests>=DEPTH,"required frame coverage");
        $fdisplay(fd,"END %0d %0d %0d %0d",cycle,normal_frames,tail_requests,cancel_count);
        $fclose(fd);test_passed=1;$display("PASS H mono delay PCM frames=%0d depth=%0d",normal_frames,DEPTH);$finish;
    end
    initial begin #400000000; $fatal(1,"timeout");end
endmodule
