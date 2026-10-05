// M2 T024 formal-top input/FIFO/core/physical PT8211 pin integration.
// HDL evidence: direct source analysis and simulation, no CodeGraph HDL index.
// FAST_AUDIO only changes local TB audio timing to shorten Release waits.
// Real 50MHz / 31250 8N1 MIDI remains unchanged in both runs. No force/stubs.
`timescale 1ns/1ps
module tb_t024_midi_polyphonic_path #(
    parameter integer FAST_AUDIO=1
);
    logic sys_clk=0;always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0,midi_rx=1;
    logic [1:0] key_n=2'b11;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx;
    electronic_piano_top dut(.*);
    // Keep defparam at top scope: Icarus ignores this override in a generate.
    defparam dut.u_i2s_tx.ACC_BITS=FAST_AUDIO ? 8 : 32;
    defparam dut.u_i2s_tx.BCLK_PHASE_STEP=FAST_AUDIO ? 32'd255 : 32'd527765581;
    localparam integer BIT_CYCLES=1600;
    integer checks=0,half_checks=0,nonzero_halves=0,midi_bytes=0;
    integer accepted_notes=0,accepted_offs=0,frames=0;
    integer last_frame_cycle=0,cycle_count=0,min_frame_cycles=2000000000,max_frame_cycles=0;
    logic ws_seen=0,ws_previous=0;
    logic [31:0] serial_word=0;
    integer half_edges=0,halves=0;
    logic signed [15:0] pcm_expected_left=0,pcm_expected_right=0,half_expected=0;
    bit negative_data;
    wire [3:0] occupied=dut.g_polyphonic.u_audio_core.u_bank.slot_occupied;
    wire [3:0] releasing=dut.g_polyphonic.u_audio_core.u_bank.slot_releasing;
    wire [31:0] notes=dut.g_polyphonic.u_audio_core.u_bank.slot_notes;
    wire [39:0] velocities=dut.g_polyphonic.u_audio_core.u_bank.slot_velocity;
    wire [15:0] channels=dut.g_polyphonic.u_audio_core.u_bank.u_events.slot_channels;
    function automatic logic signed [15:0] dac_value(input logic signed [23:0] value);
        logic signed [24:0] shifted;
        shifted=($signed({value[23],value})+25'sd128)>>>8;
        if(shifted>32767)dac_value=16'sh7fff;
        else if(shifted < -32768)dac_value=16'sh8000;
        else dac_value=shifted[15:0];
    endfunction
    task automatic check(input logic ok,input string label_text);
        checks++;
        if(ok!==1'b1)$fatal(1,"T024 top %s count=%0d occupied=%b releasing=%b notes=%h channels=%h",label_text,dut.status_active_voice_count,occupied,releasing,notes,channels);
    endtask
    always @(posedge sys_clk) begin
        cycle_count++;
        if(!dut.rst_sync_n)begin
            pcm_expected_left=0;pcm_expected_right=0;frames=0;last_frame_cycle=0;
        end else if(dut.i2s_frame_tick)begin
            pcm_expected_left=dac_value(dut.buffered_left);
            pcm_expected_right=dac_value(dut.buffered_right);
            if(last_frame_cycle!=0)begin
                if(cycle_count-last_frame_cycle<min_frame_cycles)min_frame_cycles=cycle_count-last_frame_cycle;
                if(cycle_count-last_frame_cycle>max_frame_cycles)max_frame_cycles=cycle_count-last_frame_cycle;
            end
            last_frame_cycle=cycle_count;frames++;
        end
    end
    always @(posedge sys_clk) if(dut.rst_sync_n) begin
        if(dut.shared_event_valid && dut.shared_event_ready)begin
            if(dut.shared_event_data.event_type==audio_defs_pkg::EVENT_NOTE_ON)accepted_notes++;
            if(dut.shared_event_data.event_type==audio_defs_pkg::EVENT_NOTE_OFF)accepted_offs++;
        end
    end
    // Decoder uses only BCLK/WS/DIN. PCM oracle samples formal buffer input at
    // frame acceptance; channel expected values are held across each WS word.
    always @(posedge i2s_bclk or negedge sys_rst_n)begin
        if(!sys_rst_n)begin
            ws_seen=0;serial_word=0;half_edges=0;halves=0;half_expected=0;
        end else if(dut.rst_sync_n)begin
            if(!ws_seen)begin ws_seen=1;ws_previous=i2s_lrck;end
            if(i2s_lrck!==ws_previous)begin
                if(halves>=3)begin
                    half_checks++;
                    if(half_edges!=32)$fatal(1,"PT8211 WS word has %0d edges",half_edges);
                    if(serial_word[15:0] !== (negative_data ? (half_expected^16'h0001) : half_expected))
                        $fatal(1,"PT8211 PCM mismatch WS=%b got=%h expected=%h",ws_previous,serial_word[15:0],half_expected);
                    if(serial_word[15:0]!=0)nonzero_halves++;
                end
                halves++;half_edges=0;serial_word=0;ws_previous=i2s_lrck;
                half_expected=i2s_lrck ? pcm_expected_left : pcm_expected_right;
            end
            serial_word={serial_word[30:0],i2s_din};half_edges++;
        end
    end
    task automatic settle;
        wait(dut.event_fifo_level==0 && !dut.shared_event_valid && !dut.g_polyphonic.u_audio_core.u_bank.dispatch_busy);
        repeat(100)@(negedge sys_clk);
    endtask
    task automatic byte_in(input logic [7:0] value);
        @(negedge sys_clk);midi_rx=0;repeat(BIT_CYCLES)@(negedge sys_clk);
        for(integer i=0;i<8;i++)begin midi_rx=value[i];repeat(BIT_CYCLES)@(negedge sys_clk);end
        midi_rx=1;repeat(BIT_CYCLES)@(negedge sys_clk);midi_bytes++;
    endtask
    task automatic note(input logic [7:0] status,input logic [6:0] number,velocity);
        byte_in(status);byte_in({1'b0,number});byte_in({1'b0,velocity});settle();
    endtask
    task automatic wait_frames(input integer count);
        integer target;
        target=frames+count;wait(frames>=target);repeat(50)@(negedge sys_clk);
    endtask
    task automatic reset_top;
        @(negedge sys_clk);sys_rst_n=0;midi_rx=1;
        repeat(6)@(negedge sys_clk);
        check(pa_en==1 && dut.status_active_voice_count==0 && dut.buffered_left==0 && dut.buffered_right==0,"reset silence/clear voices");
        sys_rst_n=1;repeat(100)@(negedge sys_clk);
    endtask
    initial begin
        negative_data=$test$plusargs("NEGATIVE_DATA");
        $display("INFO T024 run fast=%0d negative=%0d",FAST_AUDIO,negative_data);
        $fflush();
        reset_top();
        note(8'h90,60,100);
        check(dut.status_active_voice_count==1 && occupied==1 && notes[7:0]==60,"first real MIDI note");
        check(velocities[9:0]==audio_defs_pkg::midi_velocity_to_10bit(7'd100),"raw velocity mapped through formal parser");
        // Running status plus interleaved MIDI realtime byte.
        byte_in(62);byte_in(8'hf8);byte_in(90);settle();
        check(dut.status_active_voice_count==2 && notes[15:8]==62,"running status realtime insertion preserves second note");
        wait_frames(300);
        if(!FAST_AUDIO)begin
            note(8'h90,64,80);note(8'h90,67,70);wait_frames(300);
            check(dut.status_active_voice_count==4 && occupied==15 && notes==32'h43403e3c,"four voices at true sample rate");
            check(min_frame_cycles==1041 && max_frame_cycles==1042,"actual 48kHz frame cadence at 50MHz");
            check(half_checks>500 && nonzero_halves>50,"real-rate decoded audio not vacuous");
        end else begin
            check(min_frame_cycles==128 && max_frame_cycles==129,"accelerated cadence actually applied");
            $display("INFO four-note lifecycle begins t=%0t",$time);$fflush();
            note(8'h90,64,80);note(8'h90,67,70);
            check(dut.status_active_voice_count==4 && occupied==15 && notes==32'h43403e3c,"four physical MIDI notes reach four slots");
            note(8'h90,60,110);
            check(dut.status_active_voice_count==4 && notes==32'h43403e3c,"held same-note retrigger retains slot");
            check(velocities[9:0]==audio_defs_pkg::midi_velocity_to_10bit(7'd110),"retrigger velocity updated");
            note(8'h90,69,120);
            check(notes==32'h4340453c && dut.status_active_voice_count==4,"fifth note steals oldest slot after retrigger");
            note(8'h80,62,0);
            check(releasing==0 && dut.status_active_voice_count==4,"stale stolen Note Off cannot release replacement");
            note(8'h81,60,0);
            check(releasing==0,"different channel Note Off isolated");
            note(8'h80,60,0);check(releasing==1 && occupied==15,"Note Off keeps Release tail occupied");
            note(8'h90,60,1);
            check(releasing==0 && notes[7:0]==60 && occupied==15,"Release retrigger preserves same slot");
            note(8'h90,69,0);
            check(releasing==2 && occupied==15,"velocity zero reaches matching Note Off");
            wait_frames(4802);
            check(dut.status_active_voice_count==3 && occupied==13,"Release completion retires only target");
            $display("INFO steal/retrigger/first release passed t=%0t",$time);$fflush();
            note(8'h91,60,85);
            check(occupied==15 && notes[15:8]==60 && channels[7:4]==1,"same pitch on second MIDI channel allocated independently");
            note(8'h80,60,0);
            check(occupied==15 && releasing==1 && channels[7:4]==1 && notes[15:8]==60,"channel zero release does not kill channel one");
            $display("INFO cross-channel release passed t=%0t",$time);$fflush();
            note(8'h81,60,0);note(8'h80,64,0);note(8'h80,67,0);wait_frames(4802);
            check(dut.status_active_voice_count==0 && dut.buffered_left==0 && dut.buffered_right==0,"all four identities release to exact silence");
            note(8'h90,72,127);wait_frames(250);
            check(nonzero_halves>100,"decoded active audio exists before reset");
            // Reset while a MIDI byte is only partly transmitted.
            @(negedge sys_clk);midi_rx=0;repeat(400)@(negedge sys_clk);
            reset_top();wait_frames(10);
            check(dut.status_active_voice_count==0 && dut.buffered_left==0 && dut.event_fifo_high_watermark==0,"reset cancels partial MIDI and stale PCM");
            note(8'h90,65,75);wait_frames(250);
            check(dut.status_active_voice_count==1 && notes[7:0]==65,"fresh MIDI recovers after reset");
        end
        check(dut.midi_event_overflow==0 && dut.status_event_overflow==0 && dut.audio_underrun==0 && dut.status_clip_count==0,"no input drop clip or underrun");
        check(dut.u_midi_input.uart_frame_error_count==0 && dut.u_midi_input.parser_error_count==0,"valid 8N1 messages parsed cleanly");
        check(dut.event_fifo_level==0 && dut.event_fifo_high_watermark>0,"real common FIFO exercised and drained");
        check(half_checks>100 && nonzero_halves>50 && accepted_notes>=2,"PCM and events observed non-vacuously");
        $display("PASS tb_t024_midi_polyphonic_path fast=%0d checks=%0d halves=%0d nonzero=%0d bytes=%0d note_on=%0d note_off=%0d frame_min=%0d frame_max=%0d",FAST_AUDIO,checks,half_checks,nonzero_halves,midi_bytes,accepted_notes,accepted_offs,min_frame_cycles,max_frame_cycles);
        $finish;
    end
    initial begin #300000000;$fatal(1,"T024 physical MIDI top timeout");end
endmodule
