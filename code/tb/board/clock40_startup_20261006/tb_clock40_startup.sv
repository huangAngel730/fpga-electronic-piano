`timescale 1ns/1ps
// M2 new startup coverage only. Vendor PLL is real digital simulation model.
// LOCK/core-clock faults are explicit TB injections, not hardware assertions.
module tb_clock40_startup;
    parameter integer SCENARIO=0;
    reg sys_clk=0;
    reg sys_rst_n=(SCENARIO==0);
    reg midi_rx=1;
    reg [1:0]key_n=2'b11;
    always #10 sys_clk=~sys_clk;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx,tmds_clk_p,tmds_clk_n;
    wire [2:0]tmds_data_p,tmds_data_n;
    audio_visual_coexistence_top dut(.*);
    integer checks=0,ready_edges=0,boot_count=0,accepted=0,actual_core_edges=0;
    integer commits=0,frames=0,nonzero_samples=0;
    integer record_fd,loss_count=0,accepted_before_loss=0;
    bit was_released=0,monitor=0,finished=0;
    realtime guard_changed=0;
    initial begin
        record_fd=$fopen("startup.capture","w");
        if(!record_fd)$fatal(1,"missing startup capture file");
        $fdisplay(record_fd,"META scenario=%0d source=L_guard065 core=40 sample=48k realPLL=1 DVIstub=1",SCENARIO);
        #1;monitor=1;
    end
    task automatic check(input reg ok,input string label);
        begin checks++;if(ok!==1'b1)$fatal(1,"startup scenario=%0d %s t=%0t",SCENARIO,label,$time);end
    endtask
    // Immediate guard and mute conditions do not require any core edge.
    always @(dut.core_async_rst_n)begin
        guard_changed=$realtime;
        if(!dut.core_async_rst_n)begin ready_edges=0;was_released=0;end
    end
    always @(posedge sys_clk)begin
        if(monitor && (sys_rst_n===0 || dut.visual_pll_locked===0))begin
            #1;
            check(pa_en===1,"direct mute while no valid PLL/core clock");
            // At t0 a permanently-low async input may not create an event in
            // digital simulation before any core edge. The direct PA guard
            // must nevertheless remain known/muted. After clock initialization
            // or a prior successful boot, sync reset assertion is mandatory.
            if(actual_core_edges>0 || boot_count>0)
                check(dut.rst_sync_n===0,"asynchronous reset during invalid LOCK");
        end
    end
    always @(posedge dut.core_clk)begin
        if(monitor)begin
            actual_core_edges++;
            if(dut.core_async_rst_n===1)ready_edges++;
            else ready_edges=0;
            if(dut.rst_sync_n===1)begin
                if(dut.shared_event_valid && dut.shared_event_ready)begin
                    accepted++;
                    $fdisplay(record_fd,"EVENT t=%0t data=%016h",$time,dut.shared_event_data);
                end
                if(dut.i2s_frame_tick)frames++;
                if(dut.g_polyphonic.u_audio_core.actual_commit)begin
                    commits++;
                    if(dut.g_polyphonic.u_audio_core.u_commit.pcm_left!=0)nonzero_samples++;
                    $fdisplay(record_fd,"PCM t=%0t id=%0d left=%06h right=%06h",$time,
                        dut.g_polyphonic.u_audio_core.u_commit.pcm_req_id,
                        dut.g_polyphonic.u_audio_core.u_commit.pcm_left,
                        dut.g_polyphonic.u_audio_core.u_commit.pcm_right);
                end
            end
            #1;
            if(dut.core_async_rst_n===1 && ready_edges<2)
                check(dut.rst_sync_n===0 && pa_en===1,"reset/mute cannot release before second core edge");
            if(dut.core_async_rst_n===1 && ready_edges>=2)
                check(dut.rst_sync_n===1,"two-stage reset release by second core edge");
            if(dut.rst_sync_n===1 && !was_released)begin
                boot_count++;was_released=1;
                $fdisplay(record_fd,"BOOT t=%0t edges=%0d",$time,ready_edges);
            end
        end
    end
    task automatic wait_ready;
        begin
            wait(dut.rst_sync_n===1);
            repeat(12)@(negedge dut.core_clk);
            check(pa_en===0,"amplifier enabled after safe release");
            check(!$isunknown({dut.status_active_voice_count,dut.audio_underrun,dut.shared_event_valid}),"initialized public state no X");
            check(dut.status_active_voice_count==0,"boot clears old voices");
            check(dut.u_visual.u_scene.u_live_state.valid_q===0,"CDC accepted-note state flushed at safe boot");
            check(dut.u_visual.queue_level===0 && dut.u_visual.drop_count===0,"CDC transport empty without dropped old events");
        end
    endtask
    task automatic byte_midi(input reg[7:0]b);
        begin
            @(negedge sys_clk);midi_rx=0;#32000;
            for(integer k=0;k<8;k++)begin midi_rx=b[k];#32000;end
            midi_rx=1;#32000;
        end
    endtask
    task automatic message(input reg[7:0]s,a,b);
        begin byte_midi(s);byte_midi(a);byte_midi(b);end
    endtask
    task automatic new_note_and_pcm(input reg[6:0]note);
        integer start_commits,start_accepted,start_nonzero;
        begin
            start_accepted=accepted;
            message(8'h90,{1'b0,note},8'd100);
            #5000;
            check(accepted==start_accepted+1 && dut.status_active_voice_count==1,"new complete NoteOn accepted after boot/recovery");
            start_commits=commits;start_nonzero=nonzero_samples;
            wait(commits-start_commits>=16);
            check(nonzero_samples>start_nonzero && dut.audio_underrun==0,"at least16 new PCM frames with real sounding voice and no underrun");
            message(8'h80,{1'b0,note},0);#5000;
            check(accepted==start_accepted+2,"NoteOff recovered transport accepted");
        end
    endtask
    initial begin
        if(SCENARIO==0)begin
            // No user reset, initial high. LOCK initially low in vendor model.
            #2;
            check(sys_rst_n===1 && dut.visual_pll_locked===0 && pa_en===1,"autopower initial-high external reset and mute");
            wait_ready();new_note_and_pcm(69);
            check(boot_count==1,"automatic boot without reset press");
        end else if(SCENARIO==1)begin
            // Release external reset well before lock; never wait for lock first.
            #103;sys_rst_n=1;#1;
            check(dut.visual_pll_locked===0 && pa_en===1,"early external reset release remains muted until LOCK");
            wait_ready();new_note_and_pcm(64);
            check(boot_count==1,"early-release boot exactly once");
        end else if(SCENARIO==2)begin
            #103;sys_rst_n=1;wait_ready();
            // Build real sounding, pedal-held voice and incomplete MIDI message.
            message(8'hB0,64,127);
            message(8'h90,60,100);
            message(8'h80,60,0);#5000;
            check(dut.status_active_voice_count==1 && |dut.g_polyphonic.u_audio_core.u_bank.u_events.u_sustain.pedal_down,
                  "real sustain/voice state exists before loss");
            byte_midi(8'h90);byte_midi(8'd67);#2000;
            check(dut.u_midi_input.u_midi_event_parser.channel_data_pending===1,"actual MIDI half message before loss");
            accepted_before_loss=accepted;
            // During computation, freeze core low BEFORE forcing LOCK low.
            wait(dut.g_polyphonic.u_audio_core.u_bank.phase==4);
            @(negedge dut.core_clk);#2;
            force dut.core_clk=1'b0;
            force dut.u_visual.pll_lock=1'b0;
            loss_count++;#1;
            check(dut.core_async_rst_n===0 && dut.rst_sync_n===0 && pa_en===1,"LOCK loss with stopped core async reset/direct mute");
            check(dut.g_polyphonic.u_audio_core.u_bank.result_valid===0,"stale pending result invalid immediately on loss");
            repeat(8)@(negedge sys_clk);
            check(pa_en===1 && dut.status_active_voice_count===0,"stopped-clock loss clears voices and stays muted");
            check(dut.g_polyphonic.u_audio_core.u_bank.u_events.u_sustain.pedal_down===0,"pedal cleared without core edge");
            // LOCK high while clock is still absent must NOT release sync reset.
            release dut.u_visual.pll_lock;
            #1;check(dut.visual_pll_locked===1 && pa_en===1 && dut.rst_sync_n===0,"LOCK regained cannot bypass stopped-core synchronizer");
            repeat(5)@(negedge sys_clk);
            check(pa_en===1 && dut.rst_sync_n===0,"no-clock recovery still muted");
            release dut.core_clk;
            wait_ready();
            check(dut.u_midi_input.u_midi_event_parser.channel_data_pending===0,"MIDI half message cleared after clock resumes");
            check(dut.g_polyphonic.u_audio_core.u_bank.u_events.u_sustain.pedal_down===0,"no pedal residue after recovery");
            check(dut.event_fifo_level===0,"old queued event cleared");
            check(accepted==accepted_before_loss,"no stale half message replay");
            new_note_and_pcm(72);
            check(boot_count==2 && loss_count==1,"single loss and second safe boot covered");
        end else $fatal(1,"unknown startup scenario");
        check(checks>30 && commits>=16 && accepted>=2,"nonempty essential startup coverage");
        $fdisplay(record_fd,"END scenario=%0d checks=%0d boots=%0d accepted=%0d commits=%0d frames=%0d loss=%0d",SCENARIO,checks,boot_count,accepted,commits,frames,loss_count);
        $fclose(record_fd);finished=1;
        $display("PASS essential startup scenario=%0d checks=%0d boots=%0d accepted=%0d commits=%0d loss=%0d",SCENARIO,checks,boot_count,accepted,commits,loss_count);
        $finish;
    end
    initial begin #10000000;$fatal(1,"startup scenario wall simulation bound");end
endmodule
