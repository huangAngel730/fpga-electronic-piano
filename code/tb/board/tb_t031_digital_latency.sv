// M2 read-only formal-top latency evidence. Real50MHz/31250baud/48kHz.
// Two identical production tops; reference omits ONLY the target message.
// First response means first complete PT8211 word different from reference,
// not any nonzero mixed audio. No force, accelerated clock, PCM bypass or STA.
`timescale 1ns/1ps
module tb_t031_digital_latency;
    import audio_defs_pkg::*;
    logic sys_clk=0;always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0,midi_rx=1,r_midi_rx=1;
    logic [1:0] key_n=2'b11;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx;
    wire r_bclk,r_lrck,r_din,r_pa,r_uart;
    electronic_piano_top dut(.*);
    electronic_piano_top reference_top(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.key_n(key_n),
        .midi_rx(r_midi_rx),.i2s_bclk(r_bclk),.i2s_lrck(r_lrck),.i2s_din(r_din),.pa_en(r_pa),.uart_tx(r_uart));
    localparam integer BIT_CYCLES=1600;
    integer checks=0,word_checks=0,trials=0,fd=0,rx_count=0,half_edges=0,halves=0;
    integer frame_min=2000000000,frame_max=0;
    longint last_frame=0,last_bclk=0;
    longint start_cycle=0,last_rx_cycle=0,event_cycle=0,route_cycle=0,sample_cycle=0;
    longint commit_cycle=0,buffer_cycle=0,load_cycle=0,right_cycle=0,left_cycle=0;
    logic [31:0] word_bits=0,reference_bits=0;
    logic ws_seen=0,previous_ws=0,measuring=0;
    logic signed [15:0] expected_l=0,expected_r=0,ref_expected_l=0,ref_expected_r=0;
    logic signed [15:0] half_expected=0,half_reference=0;
    logic [6:0] target_note;
    integer target_velocity=0,target_phase=0,target_voices_before=0;
    integer dut_right_value=0,ref_right_value=0,dut_left_value=0,ref_left_value=0;
    bit suppress_target;
    string csv_path,label_text;
    function automatic longint now_cycle;
        now_cycle=$time/20;
    endfunction
    function automatic logic signed [15:0] dac_value(input logic signed [23:0] value);
        logic signed [24:0] shifted;
        shifted=($signed({value[23],value})+25'sd128)>>>8;
        if(shifted>32767)dac_value=16'sh7fff;
        else if(shifted< -32768)dac_value=16'sh8000;
        else dac_value=shifted[15:0];
    endfunction
    task automatic check(input logic condition,input string reason);
        checks++;if(condition!==1'b1)$fatal(1,"T031 %s trial=%0d label=%s",reason,trials,label_text);
    endtask
    always @(posedge sys_clk)begin
        if(dut.rst_sync_n)begin
            check(i2s_bclk===r_bclk && i2s_lrck===r_lrck,"audio clocks same with omitted target");
            if(measuring && dut.u_midi_input.uart_rx_valid)begin
                rx_count++;
                if(rx_count==1)check(dut.u_midi_input.uart_rx_data==8'h90,"received target status byte");
                if(rx_count==2)check(dut.u_midi_input.uart_rx_data=={1'b0,target_note},"received target note byte exact without sign extension");
                if(rx_count==3)check(dut.u_midi_input.uart_rx_data==8'(target_velocity),"received target raw velocity exact");
                if(rx_count==3)last_rx_cycle=now_cycle();
            end
            if(measuring && event_cycle==0 && dut.shared_event_valid && dut.shared_event_ready &&
                dut.shared_event_data.event_type==EVENT_NOTE_ON && dut.shared_event_data.note_number==target_note)
                event_cycle=now_cycle();
            if(measuring && event_cycle!=0 && route_cycle==0 && (|dut.g_polyphonic.u_audio_core.u_bank.slot_note_on))
                route_cycle=now_cycle();
            if(measuring && route_cycle!=0 && sample_cycle==0 && dut.g_polyphonic.u_audio_core.u_bank.lane_tick)
                sample_cycle=now_cycle();
            if(measuring && sample_cycle!=0 && commit_cycle==0 && dut.g_polyphonic.u_audio_core.actual_commit)
                commit_cycle=now_cycle();
            if(dut.i2s_frame_tick)begin
                expected_l=dac_value(dut.buffered_left);expected_r=dac_value(dut.buffered_right);
                ref_expected_l=dac_value(reference_top.buffered_left);ref_expected_r=dac_value(reference_top.buffered_right);
                if(measuring && load_cycle==0 && (expected_l!==ref_expected_l || expected_r!==ref_expected_r))load_cycle=now_cycle();
                if(last_frame!=0)begin
                    if(now_cycle()-last_frame<frame_min)frame_min=now_cycle()-last_frame;
                    if(now_cycle()-last_frame>frame_max)frame_max=now_cycle()-last_frame;
                end
                last_frame=now_cycle();
            end
        end else begin
            expected_l=0;expected_r=0;ref_expected_l=0;ref_expected_r=0;last_frame=0;
        end
        #1;
        if(measuring && buffer_cycle==0 &&
            (dut.buffered_left!==reference_top.buffered_left || dut.buffered_right!==reference_top.buffered_right))
            buffer_cycle=now_cycle();
    end
    // Decode only physical BCLK/WS/DIN. At WS change the previous completed
    // word is checked, but completion timestamp is its LAST actual BCLK rise.
    always @(posedge i2s_bclk or negedge sys_rst_n)begin
        if(!sys_rst_n)begin
            word_bits=0;reference_bits=0;ws_seen=0;half_edges=0;halves=0;
            half_expected=0;half_reference=0;last_bclk=0;
        end else if(dut.rst_sync_n)begin
            if(!ws_seen)begin ws_seen=1;previous_ws=i2s_lrck;end
            if(i2s_lrck!==previous_ws)begin
                if(halves>=3)begin
                    check(half_edges==32,"PT8211 complete32BCLK half word");
                    check(word_bits[15:0]===half_expected && reference_bits[15:0]===half_reference,"physical decoded samples match accepted PCM");
                    word_checks++;
                    if(measuring && word_bits[15:0]!==reference_bits[15:0])begin
                        if(previous_ws==0 && right_cycle==0)begin
                            right_cycle=last_bclk;dut_right_value=$signed(word_bits[15:0]);ref_right_value=$signed(reference_bits[15:0]);
                        end
                        if(previous_ws==1 && left_cycle==0)begin
                            left_cycle=last_bclk;dut_left_value=$signed(word_bits[15:0]);ref_left_value=$signed(reference_bits[15:0]);
                        end
                    end
                end
                halves++;half_edges=0;word_bits=0;reference_bits=0;previous_ws=i2s_lrck;
                half_expected=i2s_lrck?expected_l:expected_r;
                half_reference=i2s_lrck?ref_expected_l:ref_expected_r;
            end
            word_bits={word_bits[30:0],i2s_din};reference_bits={reference_bits[30:0],r_din};
            half_edges++;last_bclk=now_cycle();
        end
    end
    task automatic byte_in(input logic [7:0] value,input logic omit_reference,input logic omit_dut);
        @(negedge sys_clk);midi_rx=omit_dut?1:0;r_midi_rx=omit_reference?1:0;
        repeat(BIT_CYCLES)@(negedge sys_clk);
        for(integer bit_no=0;bit_no<8;bit_no++)begin
            midi_rx=omit_dut?1:value[bit_no];r_midi_rx=omit_reference?1:value[bit_no];
            repeat(BIT_CYCLES)@(negedge sys_clk);
        end
        midi_rx=1;r_midi_rx=1;repeat(BIT_CYCLES)@(negedge sys_clk);
    endtask
    task automatic common_note(input logic on,input logic [6:0] number,input logic [6:0] velocity);
        byte_in(on?8'h90:8'h80,0,0);byte_in({1'b0,number},0,0);byte_in({1'b0,velocity},0,0);
        repeat(100)@(negedge sys_clk);
    endtask
    task automatic reset_both;
        @(negedge sys_clk);measuring=0;sys_rst_n=0;midi_rx=1;r_midi_rx=1;
        repeat(6)@(negedge sys_clk);sys_rst_n=1;
        repeat(2500)@(negedge sys_clk);
        check(dut.buffered_left===reference_top.buffered_left && dut.status_active_voice_count==0,"fresh deterministic paired baseline");
    endtask
    task automatic target(input string label_value,input integer note_number,velocity,phase,voices);
        integer waited;
        wait(dut.u_i2s_tx.slot_cnt==phase);
        @(negedge sys_clk);label_text=label_value;target_note=7'(note_number);target_velocity=velocity;
        target_phase=phase;target_voices_before=voices;trials++;
        check(dut.status_active_voice_count==voices && reference_top.status_active_voice_count==voices,"workload setup count");
        check(dut.buffered_left===reference_top.buffered_left && dut.buffered_right===reference_top.buffered_right,"paired outputs equal before causal message");
        rx_count=0;last_rx_cycle=0;event_cycle=0;route_cycle=0;sample_cycle=0;commit_cycle=0;
        buffer_cycle=0;load_cycle=0;right_cycle=0;left_cycle=0;start_cycle=now_cycle()+1;
        measuring=1;
        // Start-cycle belongs to this task's next negedge: byte_in also waits
        // that edge. Reference RX stays idle only for this full target message.
        byte_in(8'h90,1,suppress_target);byte_in(8'(note_number),1,suppress_target);byte_in(8'(velocity),1,suppress_target);
        waited=0;
        while((right_cycle==0 || left_cycle==0) && waited<20000)begin
            @(negedge sys_clk);waited++;
        end
        if(right_cycle==0 || left_cycle==0)begin
            $display("DEBUG response rx=%0d parse_errors=%0d UART_errors=%0d active=%0d notes=%h events=%0d route=%0d sample=%0d commit=%0d buffer=%0d load=%0d R=%0d L=%0d current_PCM=%0d ref=%0d expected_R=%0d expected_L=%0d",rx_count,dut.u_midi_input.parser_error_count,dut.u_midi_input.uart_frame_error_count,dut.status_active_voice_count,dut.g_polyphonic.u_audio_core.u_bank.slot_notes,event_cycle,route_cycle,sample_cycle,commit_cycle,buffer_cycle,load_cycle,right_cycle,left_cycle,dut.buffered_left,reference_top.buffered_left,expected_r,expected_l);
        end
        check(right_cycle!=0 && left_cycle!=0,"NO_TARGET_RESPONSE causal output missing");
        check(rx_count==3 && last_rx_cycle>start_cycle,"exact three target bytes received");
        check(start_cycle<last_rx_cycle && last_rx_cycle<=event_cycle && event_cycle<=route_cycle && route_cycle<=sample_cycle && sample_cycle<=commit_cycle,"ordered receive/event/voice/sample/commit stages");
        check(commit_cycle<=buffer_cycle && buffer_cycle<=load_cycle && load_cycle<=right_cycle && load_cycle<=left_cycle,"causal PCM-to-serialized response stages");
        check(right_cycle-start_cycle<500000 && left_cycle-start_cycle<500000,"digital output below10ms test bound");
        check(dut.audio_underrun==0 && reference_top.audio_underrun==0 && dut.status_event_overflow==0 && dut.status_clip_count==0,"no silent drop/underrun/clipping");
        $fdisplay(fd,"%s,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",label_text,trials,note_number,velocity,phase,voices,start_cycle,last_rx_cycle,event_cycle,route_cycle,sample_cycle,commit_cycle,buffer_cycle,load_cycle,right_cycle,left_cycle,dut_right_value,ref_right_value,dut_left_value,ref_left_value);
        $fflush(fd);
        $display("PASS latency trial=%0d %s start_to_R_cycles=%0d start_to_L_cycles=%0d received_to_R_cycles=%0d",trials,label_text,right_cycle-start_cycle,left_cycle-start_cycle,right_cycle-last_rx_cycle);$fflush();
        measuring=0;
    endtask
    initial begin
        suppress_target=$test$plusargs("SUPPRESS_TARGET");
        if(!$value$plusargs("CSV=%s",csv_path))$fatal(1,"CSV required");
        fd=$fopen(csv_path,"w");if(!fd)$fatal(1,"Cannot open results");
        $fdisplay(fd,"scenario,trial,note,raw_velocity,message_start_slot,voices_before,start_cycle,final_byte_rx_cycle,event_accept_cycle,note_on_cycle,first_sample_cycle,first_commit_cycle,first_buffer_diff_cycle,first_frame_diff_cycle,right_word_complete_cycle,left_word_complete_cycle,dut_right_pcm16,reference_right_pcm16,dut_left_pcm16,reference_left_pcm16");
        reset_both();target("idle_low_soft",21,1,0,0);
        reset_both();target("idle_A4_soft",69,1,15,0);
        reset_both();target("idle_high_hard",108,127,31,0);
        reset_both();target("idle_A4_phase0",69,100,0,0);
        reset_both();target("idle_A4_phase15",69,100,15,0);
        reset_both();target("idle_A4_phase31",69,100,31,0);
        reset_both();target("idle_A4_phase63",69,100,63,0);
        reset_both();common_note(1,48,100);common_note(1,55,100);common_note(1,60,100);
        target("fourth_voice",67,100,0,3);
        reset_both();common_note(1,48,100);common_note(1,55,100);common_note(1,60,100);common_note(1,67,100);
        target("fifth_voice_steal",72,100,31,4);
        reset_both();common_note(1,69,127);target("held_retrigger_soft",69,1,63,1);
        reset_both();common_note(1,69,100);common_note(0,69,0);
        target("release_retrigger",69,90,15,1);
        check(frame_min==1041 && frame_max==1042,"true48kHz cadence with unmodified audio divider");
        check(trials==11 && word_checks>500,"nonempty full path timestamp/decode coverage");
        $fclose(fd);$display("PASS T031 digital latency trials=%0d checks=%0d physical_words=%0d frame_min=%0d frame_max=%0d",trials,checks,word_checks,frame_min,frame_max);$finish;
    end
    initial begin #100000000;$fatal(1,"T031 latency timeout");end
endmodule
