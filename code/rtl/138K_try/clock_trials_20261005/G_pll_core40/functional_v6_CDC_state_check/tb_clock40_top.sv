`timescale 1ns/1ps
module tb_clock40_top;
    reg sys_clk=0,sys_rst_n=0,midi_rx=1;
    reg[1:0]key_n=2'b11;
    always #10 sys_clk=~sys_clk;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx,tmds_clk_p,tmds_clk_n;
    wire[2:0]tmds_data_p,tmds_data_n;
    audio_visual_coexistence_top dut(.*);
    integer checks=0,frames=0,bclk_rises=0,prior_rises=0,accepted=0;
    integer measured_edges=0;
    realtime first_bclk=0,last_bclk=0;
    reg measure=0,prior_din=0;
    task automatic check(input reg ok,input string label);
        checks++;if(ok!==1'b1)$fatal(1,"clock40 integration %s",label);
    endtask
    task automatic byte_midi(input reg[7:0]b);
        midi_rx=0;#32000;
        for(integer k=0;k<8;k++)begin midi_rx=b[k];#32000;end
        midi_rx=1;#32000;
    endtask
    always @(posedge i2s_bclk)begin
        bclk_rises++;
        if(measure)begin
            measured_edges++;
            if(measured_edges==1)first_bclk=$realtime;
            if(measured_edges==257)begin
                last_bclk=$realtime;
                check((last_bclk-first_bclk)/256.0>325.3 && (last_bclk-first_bclk)/256.0<325.8,
                      "BCLK3.072MHz average, not2.4576MHz from old NCO step");
                $display("MEASURE BCLK avg_period_ns=%f",(last_bclk-first_bclk)/256.0);
            end
        end
    end
    always @(posedge dut.core_clk)begin
        if(!dut.rst_sync_n)begin frames=0;prior_rises=bclk_rises;end
        else begin
            if(dut.i2s_frame_tick)begin
                check(bclk_rises-prior_rises==64,"64 BCLK rising edges per stereo frame");
                prior_rises=bclk_rises;frames++;
            end
            if(dut.shared_event_valid && dut.shared_event_ready)accepted++;
        end
        #1;
        if(dut.rst_sync_n && i2s_din!==prior_din)
            check(i2s_bclk==0,"DIN only changes on BCLK low/falling boundary");
        prior_din=i2s_din;
    end
    initial begin
        #200;
        check(pa_en===1,"muted during external reset");
        wait(dut.visual_pll_locked===1);
        repeat(4)@(posedge dut.core_clk);
        @(negedge dut.core_clk);sys_rst_n=1;
        wait(dut.rst_sync_n===1);#100;
        check(dut.CLK_HZ==40000000,"core CLK_HZ40M");
        check(dut.CORE_BCLK_PHASE_STEP==32'd659706977,"recomputed BCLK NCO");
        check(dut.DEBOUNCE_CNT==120000 && dut.DEBOUNCE_CLK_HZ==40000000,"3ms debounce retained");
        check(dut.u_midi_input.u_uart_rx.DIV==1280,"MIDI31250 exact bit divider");
        check(dut.u_midi_input.u_midi_event_parser.CONTROL_INTERVAL==40000,"1kHz MIDI merge retained");
        check(dut.u_uart_status_reporter.u_uart_tx.DIV==347,"UART115200 rederived divider");
        check(dut.u_uart_status_reporter.REPORT_CYCLES==10000000,"STAT250ms cadence retained");
        check(dut.u_visual.MODE_PERIOD_CYCLES==200000000 && dut.u_visual.VIDEO_FRAME_SYS_CYCLES==672000,
              "visual5s and16.8ms diagnostic timers retained");
        measure=1;
        for(integer n=0;n<4;n++)begin byte_midi(8'h90);byte_midi(8'(60+n));byte_midi(8'd100);end
        #100000;
        check(dut.status_active_voice_count==4 && accepted==4,"physical UART MIDI four notes accepted");
        check(dut.u_midi_input.u_midi_event_parser.parser_error_count==0,"no MIDI parser errors");
        check(dut.status_event_overflow==0,"no input/public FIFO overflow");
        check(dut.audio_underrun==0,"four-voice40MHz no underrun");
        check(dut.core_max_processing_cycles>0 && dut.core_max_processing_cycles<64,"processing fits833-cycle audio budget");
        check(dut.u_visual.drop_count==0,"40to25MHz accepted-event CDC no drops");
        // Published geometry updates only at frame_start; inspect accepted state,
        // not the intentionally stale frame snapshot before the first16.8ms frame.
        check($countones(dut.u_visual.u_scene.u_live_state.valid_q)==4,"all MIDI notes reached video through CDC");
        check(frames>180 && measured_edges>257,"nonempty full audio frame evidence");
        $display("MEASURE frames=%0d commits=%0d max_processing_cycles=%0d underrun=%0d",frames,dut.pcm_commit_count,dut.core_max_processing_cycles,dut.audio_underrun);
        // Inject loss of LOCK, not a claim about hardware PLL lock dynamics.
        force dut.visual_pll_locked=1'b0;#1;
        check(pa_en===1 && dut.rst_sync_n===0,"LOCK loss asynchronously mutes and resets");
        repeat(8)@(posedge sys_clk);
        release dut.visual_pll_locked;
        wait(dut.rst_sync_n===1);#100;
        check(pa_en===0 && dut.status_active_voice_count==0,"synchronous recovery clears old voices");
        byte_midi(8'h90);byte_midi(8'd69);byte_midi(8'd100);#100000;
        check(dut.status_active_voice_count==1 && dut.audio_underrun==0,"MIDI/audio restored after LOCK-loss reset");
        check(checks>200,"nonvacuous integration checks");
        $display("PASS full clock40 integration checks=%0d",checks);$finish;
    end
    initial begin #10000000;$fatal(1,"full clock40 simulation timeout");end
endmodule
