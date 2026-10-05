`timescale 1ns/1ps
// F: actual pin-level UARTs -> public FIFO -> real candidate bank -> PCM commit.
// Test-only competitor/backpressure is explicit, never a replacement allocator.
module tb_system_control_pipeline;
    import audio_defs_pkg::*;
    logic clk=0;
    always #10 clk=~clk;
    logic rst_n=0,rx_a=1,rx_b=1,frame_tick=0,frames_enable=0;
    logic allow_events=1,fixture_select=0,fixture_valid=0,center_compare=1;
    performance_event_t fixture_data;
    wire a_valid,b_valid,a_ready,b_ready,fixture_ready;
    performance_event_t a_data,b_data,input_b,fifo_data;
    wire fifo_valid,fifo_ready,bank_ready,reference_ready;
    wire [15:0] fifo_level,fifo_peak,a_level,b_level;
    wire [31:0] a_overflow,b_overflow,a_errors,b_errors,a_frames,b_frames;
    wire signed [23:0] play_left,play_right;
    wire pending_valid;
    wire [31:0] active_voice_count,clip_count,audio_underrun,audio_frame_count;
    wire [31:0] pcm_request_count,pcm_commit_count,max_processing_cycles;
    integer fd,cycle=0,epoch=0,checks=0,total_pcm=0,nonzero_pcm=0;
    integer full_pop_push=0,control_stalls=0,edge_events=0,center_samples=0;
    integer reset_partial=0,reset_compute=0,reset_pending=0;
    integer ticks_left=1,cadence_index=0,last_frame_cycle=0,last_request_cycle=0;
    integer synthetic_pushes=0,normal_pushes=0,normal_pcm=0;
    logic was_reset=0,expected_control_apply=0;
    logic test_passed=0;
    logic fifo_was_stalled=0;
    logic [63:0] fifo_held;
    logic commit_check;
    logic signed [23:0] committing_left,committing_right;
    logic [63:0] ref_env,ref_wave;
    logic [3:0] ref_mask;
    logic [31:0] ref_id;
    wire ref_valid,ref_calc_ready;
    wire [63:0] ref_env_bus,ref_wave_bus;
    wire [127:0] ref_fcw_bus;
    wire [3:0] ref_mask_bus;
    wire [11:0] ref_states;
    wire [31:0] ref_id_bus,ref_count;
    wire [7:0] wave_tables;
    for(genvar observe_lane=0;observe_lane<4;observe_lane++)begin:g_observe
        assign wave_tables[2*observe_lane+:2]=dut.u_bank.g_lane[observe_lane].g_piano.u_dds.active_table;
    end

    midi_input #(.SOURCE_ID(1)) input_a(
        .clk(clk),.rst_n(rst_n),.midi_rx_async(rx_a),.event_ready(a_ready),
        .event_valid(a_valid),.event_data(a_data),.event_fifo_level(a_level),
        .event_fifo_high_watermark(),.uart_frame_error_count(a_frames),
        .parser_error_count(a_errors),.event_fifo_overflow_count(a_overflow),.midi_rx_busy());
    midi_input #(.SOURCE_ID(9)) input_second(
        .clk(clk),.rst_n(rst_n),.midi_rx_async(rx_b),.event_ready(b_ready),
        .event_valid(b_valid),.event_data(b_data),.event_fifo_level(b_level),
        .event_fifo_high_watermark(),.uart_frame_error_count(b_frames),
        .parser_error_count(b_errors),.event_fifo_overflow_count(b_overflow),.midi_rx_busy());
    assign input_b=fixture_select ? fixture_data : b_data;
    assign b_ready=!fixture_select && fixture_ready;
    performance_event_fifo #(.DEPTH(32)) u_fifo(
        .clk(clk),.rst_n(rst_n),.button_valid(fixture_select ? fixture_valid : b_valid),
        .button_ready(fixture_ready),.button_data(input_b),.midi_valid(a_valid),
        .midi_ready(a_ready),.midi_data(a_data),.event_valid(fifo_valid),
        .event_ready(fifo_ready),.event_data(fifo_data),.event_fifo_level(fifo_level),
        .event_fifo_high_watermark(fifo_peak));
    assign fifo_ready=allow_events && bank_ready;
    polyphonic_audio_core #(.PIANO_TIMBRE_ENABLE(1),.WAVE_ROM_FILE("wave.mem")) dut(
        .clk(clk),.rst_n(rst_n),.event_valid(fifo_valid && allow_events),
        .event_ready(bank_ready),.event_data(fifo_data),.frame_tick(frame_tick),
        .play_left(play_left),.play_right(play_right),.pending_valid(pending_valid),
        .active_voice_count(active_voice_count),.clip_count(clip_count),
        .audio_underrun(audio_underrun),.audio_frame_count(audio_frame_count),
        .pcm_request_count(pcm_request_count),.pcm_commit_count(pcm_commit_count),
        .max_processing_cycles(max_processing_cycles));
    // Existing reviewed ADSR-pipelined V1/CC64 bank, without Pitch/Mod, only for
    // center/Mod0 comparison. It receives actual FIFO acceptances, not fixtures.
    bank_reference #(.PIANO_TIMBRE_ENABLE(1),.WAVE_ROM_FILE("wave.mem")) reference_bank(
        .clk(clk),.rst_n(rst_n),.event_valid(fifo_valid && fifo_ready),
        .event_ready(reference_ready),.event_data(fifo_data),.frame_tick(frame_tick),
        .sample_req(dut.sample_req),.sample_req_id(dut.sample_req_id),
        .calc_ready(ref_calc_ready),.result_valid(ref_valid),.result_ready(1'b1),
        .result_req_id(ref_id_bus),.result_envelopes(ref_env_bus),.result_waves(ref_wave_bus),
        .result_fcw(ref_fcw_bus),.result_occupied(ref_mask_bus),.result_states(ref_states),
        .active_voice_count(ref_count));

    task automatic check(input logic ok,input string label);
        checks++;
        if(ok!==1'b1)$fatal(1,"F assertion %s epoch=%0d cycle=%0d",label,epoch,cycle);
    endtask
    always @(negedge clk) begin
        frame_tick=0;
        if(rst_n && frames_enable)begin
            if(ticks_left==0)begin
                frame_tick=1;
                // 50MHz / 48kHz: 1041,1042,1042 clocks per three frames.
                ticks_left=(cadence_index%3==0 ? 1041 : 1042)-1;
                cadence_index++;
            end else ticks_left--;
        end else begin ticks_left=1;cadence_index=0;end
    end

    always @(posedge clk) begin : capture
        cycle++;
        if(!rst_n)begin
            if(!was_reset)begin epoch++;$fdisplay(fd,"R %0d %0d",cycle,epoch);end
            was_reset=1;last_frame_cycle=0;expected_control_apply=0;fifo_was_stalled=0;
        end else begin
            was_reset=0;
            if(fifo_was_stalled)check(fifo_valid && fifo_data===fifo_held,"public FIFO stalled payload stable");
            fifo_was_stalled=fifo_valid && !fifo_ready;fifo_held=fifo_data;
            if(input_a.uart_rx_valid && !input_a.uart_frame_error)
                $fdisplay(fd,"U %0d 1 %02h",cycle,input_a.uart_rx_data);
            if(input_second.uart_rx_valid && !input_second.uart_frame_error)
                $fdisplay(fd,"U %0d 9 %02h",cycle,input_second.uart_rx_data);
            if(a_valid && a_ready)begin
                $fdisplay(fd,"P %0d %016h 0",cycle,a_data);normal_pushes++;
            end
            if((fixture_select ? fixture_valid : b_valid) && fixture_ready)begin
                $fdisplay(fd,"P %0d %016h %0d",cycle,input_b,fixture_select);
                if(fixture_select)synthetic_pushes++;else normal_pushes++;
            end
            if(fifo_level==32 && fifo_ready && (a_valid&&a_ready ||
                    (fixture_select ? fixture_valid : b_valid)&&fixture_ready)) full_pop_push++;
            if(fifo_valid && !fifo_ready && (fifo_data.event_type==EVENT_PITCH_BEND ||
                    fifo_data.event_type==EVENT_CONTROL_CHANGE && fifo_data.control_id==CTRL_MODULATION))
                control_stalls++;
            expected_control_apply=fifo_valid && fifo_ready &&
                (fifo_data.event_type==EVENT_PITCH_BEND ||
                fifo_data.event_type==EVENT_CONTROL_CHANGE && fifo_data.control_id==CTRL_MODULATION);
            commit_check=dut.actual_commit;
            committing_left=dut.u_commit.pcm_left;committing_right=dut.u_commit.pcm_right;
            if(fifo_valid && fifo_ready)begin
                $fdisplay(fd,"E %0d %016h",cycle,fifo_data);
                if(center_compare)check(reference_ready,"center reference accepts same actual event");
                if(cycle-last_frame_cycle<64)edge_events++;
            end
            if(frame_tick)begin
                if(last_frame_cycle!=0)check(cycle-last_frame_cycle==1041 ||
                    cycle-last_frame_cycle==1042,"legal frame cadence");
                last_frame_cycle=cycle;
                check(audio_underrun==0,"no accidental PCM underrun");
                $fdisplay(fd,"K %0d %0d",cycle,dut.sample_req_id+1);
            end
            if(dut.sample_req)begin
                last_request_cycle=cycle;
                $fdisplay(fd,"J %0d %0d",cycle,dut.sample_req_id);
            end
            if(dut.u_bank.slot_note_on)
                $fdisplay(fd,"N %0d %h",cycle,dut.u_bank.slot_note_on);
            if(dut.u_bank.control_request_valid && dut.u_bank.control_request_ready)
                $fdisplay(fd,"Q %0d %0d %h %04h %04h %032h %032h %08h",cycle,
                    dut.u_bank.pending_req_id,dut.u_bank.slot_occupied,dut.u_bank.slot_sources,
                    dut.u_bank.slot_channels,dut.u_bank.slot_generations,dut.u_bank.slot_fcw,dut.u_bank.slot_notes);
            if(dut.u_bank.control_snapshot_valid && dut.u_bank.control_snapshot_ready && dut.u_bank.phase==4)
                $fdisplay(fd,"S %0d %0d %012h %012h %05h",cycle,
                    dut.u_bank.control_id,dut.u_bank.control_bend,dut.u_bank.control_mod,dut.u_bank.control_range);
            if(dut.u_bank.u_pitch_mod.accepted)
                $fdisplay(fd,"C %0d %0d",cycle,dut.u_bank.control_id);
            if(dut.u_bank.fcw_result_valid && dut.u_bank.fcw_result_ready && dut.u_bank.phase==4)
                $fdisplay(fd,"F %0d %0d %h %04h %04h %032h %032h",cycle,dut.u_bank.fcw_id,
                    dut.u_bank.fcw_occupied,dut.u_bank.fcw_sources,dut.u_bank.fcw_channels,
                    dut.u_bank.fcw_generations,dut.u_bank.fcw_values);
            if(dut.u_bank.lane_tick)
                $fdisplay(fd,"D %0d %0d %032h",cycle,dut.u_bank.pending_req_id,dut.u_bank.dds_fcw);
            if(ref_valid)begin ref_env=ref_env_bus;ref_wave=ref_wave_bus;ref_mask=ref_mask_bus;ref_id=ref_id_bus;end
            if(dut.bank_valid && dut.bank_ready)begin
                check(dut.bank_id==dut.sample_req_id,"bank current generation tag");
                $fdisplay(fd,"H %0d %0d %h %016h %016h %02h",cycle,dut.bank_id,
                    dut.bank_occupied,dut.bank_waves,dut.bank_envelopes,wave_tables);
                if(center_compare)begin
                    check(ref_id==dut.bank_id && {ref_env,ref_wave,ref_mask}===
                        {dut.bank_envelopes,dut.bank_waves,dut.bank_occupied},"center bank V1/CC64 equivalence");
                    center_samples++;
                end
            end
            if(dut.u_commit.pcm_valid)
                check(dut.u_commit.pcm_req_id==dut.sample_req_id,"PCM frame tag mismatch");
            if(dut.actual_commit)begin
                check(cycle-last_request_cycle<100,"PCM calculation bounded within frame");
                $fdisplay(fd,"M %0d %0d %06h %06h %0d",cycle,dut.u_commit.pcm_req_id,
                    dut.u_commit.pcm_left,dut.u_commit.pcm_right,fixture_select);
                total_pcm++;normal_pcm++;
                if(dut.u_commit.pcm_left!=0)nonzero_pcm++;
            end
            #1;
            if(commit_check)check(pending_valid && play_left===committing_left &&
                play_right===committing_right,"actual frame buffer exposes committed stereo PCM");
            check(dut.u_bank.u_controls.control_applied===expected_control_apply,
                "control updated before public FIFO acceptance");
            check(a_overflow==0 && b_overflow==0 && a_frames==0 && b_frames==0,
                "bounded DIN inputs no overflow/frame errors");
            check(!$isunknown({play_left,play_right,pending_valid,fifo_valid,fifo_ready}),"no X on public outputs");
        end
    end

    task automatic uart_byte(input integer source,input logic[7:0] value);
        @(negedge clk);
        if(source==1)rx_a=0;else rx_b=0;
        repeat(1600)@(negedge clk);
        for(integer bit_index=0;bit_index<8;bit_index++)begin
            if(source==1)rx_a=value[bit_index];else rx_b=value[bit_index];
            repeat(1600)@(negedge clk);
        end
        if(source==1)rx_a=1;else rx_b=1;
        repeat(1600)@(negedge clk);
    endtask
    task automatic drain;
        integer guard;guard=0;
        while((fifo_level!=0 || a_level!=0 || b_level!=0 || a_valid || b_valid ||
                dut.u_bank.dispatch_busy) && guard<60000)begin @(negedge clk);guard++;end
        check(guard<60000,"bounded input drain");repeat(120)@(negedge clk);
    endtask
    task automatic message(input integer source,input logic[7:0] status,input integer first,second);
        uart_byte(source,status);uart_byte(source,8'(first));
        if(status[7:4]!=12)uart_byte(source,8'(second));
        drain();
    endtask
    function automatic integer find_voice(input integer source,channel,note_number);
        find_voice=-1;
        for(integer lane=0;lane<4;lane++)if(dut.u_bank.slot_occupied[lane] &&
            dut.u_bank.slot_sources[4*lane+:4]==source && dut.u_bank.slot_channels[4*lane+:4]==channel &&
            dut.u_bank.slot_notes[8*lane+:8]==note_number)find_voice=lane;
    endfunction
    task automatic mark(input string name);
        $fdisplay(fd,"T %0d %s",cycle,name);
    endtask
    task automatic reset_chain;
        @(negedge clk);frames_enable=0;rst_n=0;rx_a=1;rx_b=1;
        fixture_valid=0;fixture_select=0;allow_events=1;
        #2;check(play_left==0 && play_right==0 && !pending_valid,"async reset silence");
        repeat(5)@(negedge clk);rst_n=1;
        repeat(5)@(negedge clk);check(fifo_level==0,"reset FIFO flush");frames_enable=1;
    endtask
    task automatic fixture_send(input performance_event_t value);
        integer guard;guard=0;
        @(negedge clk);fixture_select=1;fixture_data=value;fixture_valid=1;
        do begin @(posedge clk);guard++;end while(!fixture_ready && guard<1000);
        check(guard<1000,"fixture source handshake bounded");
        @(negedge clk);fixture_valid=0;
    endtask
    function automatic performance_event_t fixture_program(input integer number);
        performance_event_t value;value='0;value.event_type=EVENT_CONTROL_CHANGE;
        value.source_id=15;value.channel=15;value.control_id=CTRL_VOICE_SELECT;
        value.control_value=12'(number);return value;
    endfunction

    initial begin : stimulus
        integer lane,old_lane,start_pcm,saved_generation;
        performance_event_t pitch_fixture;
        fd=$fopen("midi_pcm.capture","w");if(!fd)$fatal(1,"capture open failed");
        fixture_data='0;reset_chain();
        message(1,8'h90,60,127);message(1,8'h91,64,96);
        message(9,8'h90,67,64);message(1,8'h90,72,32);
        check(active_voice_count==4,"real four voices");
        check(find_voice(1,0,60)>=0 && find_voice(1,1,64)>=0 && find_voice(9,0,67)>=0 &&
            find_voice(1,0,72)>=0,"four source channel identities");mark("four_voices");
        start_pcm=total_pcm;while(total_pcm-start_pcm<512)@(negedge clk);
        check(center_samples>=512,"512 center bank comparisons");mark("center512");center_compare=0;
        message(1,8'he0,127,127);message(1,8'he1,0,0);message(9,8'hb0,1,127);
        start_pcm=total_pcm;while(total_pcm-start_pcm<256)@(negedge clk);mark("held_controls");
        old_lane=find_voice(1,0,60);message(9,8'h92,79,120);
        check(find_voice(1,0,60)==-1 && find_voice(9,2,79)==old_lane,"fifth steals oldest real slot");
        saved_generation=dut.u_bank.slot_generations[32*old_lane+:32];
        message(1,8'h80,60,0);
        check(find_voice(9,2,79)==old_lane && !dut.u_bank.slot_releasing[old_lane] &&
            dut.u_bank.slot_generations[32*old_lane+:32]==saved_generation,"old off isolates stolen identity");
        mark("steal_old_off");
        lane=find_voice(1,1,64);message(1,8'h91,64,0);
        check(dut.u_bank.slot_releasing[lane],"velocity zero releases");mark("velocity_zero");
        saved_generation=dut.u_bank.slot_generations[32*lane+:32];
        message(1,8'h91,64,96);
        check(find_voice(1,1,64)==lane && !dut.u_bank.slot_releasing[lane] &&
            dut.u_bank.slot_generations[32*lane+:32]==saved_generation+1,"release retrigger generation");
        mark("release_retrigger");
        message(1,8'hb0,64,127);lane=find_voice(1,0,72);message(1,8'h80,72,0);
        check(!dut.u_bank.slot_releasing[lane] &&
            dut.u_bank.u_events.controller_deferred[lane],"pedal holds released key");
        message(1,8'he0,0,64);message(1,8'hb0,1,95);
        check(!dut.u_bank.slot_releasing[lane],"tail controls preserve pedal hold");mark("pedal_tail_controls");
        message(1,8'hb0,64,0);check(dut.u_bank.slot_releasing[lane],"pedal up releases deferred voice");
        check(!dut.u_bank.slot_releasing[find_voice(1,1,64)],"pedal does not release still held key");
        message(1,8'he0,0,48);message(1,8'hb0,1,35);mark("release_controls");
        // Re-arm the pedal and same tail, then replace the deferred identity.
        message(1,8'h90,72,96);message(1,8'hb0,64,127);message(1,8'h80,72,0);
        lane=find_voice(1,0,72);
        check(dut.u_bank.u_events.controller_deferred[lane],"deferred identity before steal");
        // After 72 retrigger, LRU order is 67,79,64,72. Replace all four by
        // actual NoteOns so the last one must steal the deferred 72 slot.
        message(9,8'h93,81,100);message(9,8'h94,84,100);
        message(9,8'h95,86,100);message(9,8'h96,88,100);
        check(find_voice(1,0,72)==-1 && find_voice(9,6,88)==lane,"pedal deferred voice stolen");
        saved_generation=dut.u_bank.slot_generations[32*lane+:32];
        message(1,8'hb0,64,0);message(1,8'h80,72,0);
        check(find_voice(9,6,88)==lane && !dut.u_bank.slot_releasing[lane] &&
            dut.u_bank.slot_generations[32*lane+:32]==saved_generation,
            "old pedal generation cannot release replacement");mark("pedal_steal");
        message(1,8'hc0,127,0);mark("program_transport");

        // Pin-level completion close to the next frame: change only idle time,
        // never shorten the 1600-clock UART bits or force internal parser state.
        uart_byte(1,8'he1);uart_byte(1,0);
        while(ticks_left!=618)@(negedge clk);
        uart_byte(1,72);drain();check(edge_events>0,"sample-edge acceptance observed");mark("sample_edge");

        // Explicit overload fixture: fill public FIFO while downstream paused.
        allow_events=0;fixture_select=1;
        for(integer i=0;i<32;i++)fixture_send(fixture_program(i));
        check(fifo_level==32,"public FIFO full fixture");
        @(negedge clk);fixture_valid=1;fixture_data=fixture_program(32);allow_events=1;
        begin integer guard;guard=0;
            do begin @(posedge clk);guard++;end while(!fixture_ready && guard<2000);
            check(guard<2000,"full simultaneous pop push accepted");
        end
        @(negedge clk);fixture_valid=0;drain();check(full_pop_push>0,"full pop push coverage");
        fixture_select=0;mark("fifo_pressure");

        // Control is queued behind the actual bank's PCM owner, not accepted
        // until ready. The third behavioral mutant must fail here.
        wait(dut.sample_req);@(negedge clk);
        pitch_fixture='0;pitch_fixture.event_type=EVENT_PITCH_BEND;
        pitch_fixture.source_id=1;pitch_fixture.channel=1;pitch_fixture.control_id=CTRL_PITCH_BEND;
        pitch_fixture.control_value=12'h400;
        fixture_send(pitch_fixture);drain();fixture_select=0;
        check(control_stalls>0,"unaccepted control head coverage");mark("accepted_only");

        // Added stage may never advance the wave under a same-edge frame cancel.
        wait(dut.u_bank.phase==9);reset_chain();mark("reset_verify");
        message(1,8'h90,69,100);

        // Deliberately abandon an incomplete real MIDI message by reset.
        uart_byte(1,8'h90);uart_byte(1,65);
        @(negedge clk);rx_a=0;repeat(400)@(negedge clk);
        reset_partial++;reset_chain();mark("reset_partial");
        message(1,8'h90,69,100);
        wait(dut.u_bank.u_pitch_mod.busy && dut.u_bank.u_pitch_mod.age==2);
        reset_compute++;reset_chain();mark("reset_compute");
        message(9,8'h90,67,100);
        wait(pending_valid);reset_pending++;reset_chain();mark("reset_pending");
        message(1,8'h90,69,127);message(1,8'he0,0,80);message(1,8'hb0,1,127);
        start_pcm=total_pcm;while(total_pcm-start_pcm<128)@(negedge clk);mark("recovered");drain();
        frames_enable=0;
        while(!pending_valid)@(negedge clk);
        check(normal_pcm>=512 && nonzero_pcm>=512 && full_pop_push>0 && control_stalls>0 &&
            edge_events>0 && center_samples>=512 && reset_partial==1 && reset_compute==1 && reset_pending==1,
            "nonempty F required coverage");
        check(a_errors==0 && b_errors==0 && audio_underrun==0,"final clean parser and PCM recovery");
        $fdisplay(fd,"END %0d %0d %0d %0d %0d %0d %0d %0d %0d",total_pcm,nonzero_pcm,
            full_pop_push,control_stalls,edge_events,center_samples,normal_pushes,synthetic_pushes,checks);
        $fclose(fd);test_passed=1;
        $display("PASS F real UART FIFO allocator V1 CC64 PitchMod PCM frames=%0d checks=%0d",total_pcm,checks);
        $finish;
    end
    initial begin #160000000;$fatal(1,"F overall timeout");end
endmodule
