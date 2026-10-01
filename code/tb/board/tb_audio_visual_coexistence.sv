// Real 50MHz / 48kHz / DIN 31250 input. Compare new diagnostic audio
// cycle-for-cycle against unchanged e5eb025 formal top. PHY is a wiring model.
`timescale 1ns/1ps
module tb_audio_visual_coexistence #(parameter bit SMALL_RASTER=0);
    logic sys_clk=0;always #10 sys_clk=~sys_clk;
    logic sys_rst_n=0,midi_rx=1;
    logic [1:0] key_n=2'b11;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx;
    wire r_i2s_bclk,r_i2s_lrck,r_i2s_din,r_pa_en,r_uart_tx;
    wire tmds_clk_p,tmds_clk_n;
    wire [2:0] tmds_data_p,tmds_data_n;
    audio_visual_coexistence_top dut(.*);
    electronic_piano_top reference_top(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),
        .key_n(key_n),.midi_rx(midi_rx),.i2s_bclk(r_i2s_bclk),.i2s_lrck(r_i2s_lrck),
        .i2s_din(r_i2s_din),.pa_en(r_pa_en),.uart_tx(r_uart_tx));
    // Only display control cadence is shortened to exercise both modes.
    // Audio, MIDI, pixel and serial clocks are production rates.
    defparam dut.u_visual.MODE_PERIOD_CYCLES=SMALL_RASTER ? 10000 : 600000;
    // Optional short-display integration run; audio/MIDI clocks remain real.
    // The physical build always uses the unmodified default 640x480 raster.
    defparam dut.u_visual.u_scan.H_ACTIVE=SMALL_RASTER ? 64 : 640;
    defparam dut.u_visual.u_scan.H_FRONT=SMALL_RASTER ? 4 : 16;
    defparam dut.u_visual.u_scan.H_SYNC=SMALL_RASTER ? 8 : 96;
    defparam dut.u_visual.u_scan.H_BACK=SMALL_RASTER ? 4 : 48;
    defparam dut.u_visual.u_scan.V_ACTIVE=SMALL_RASTER ? 48 : 480;
    defparam dut.u_visual.u_scan.V_FRONT=SMALL_RASTER ? 4 : 10;
    defparam dut.u_visual.u_scan.V_SYNC=2;
    defparam dut.u_visual.u_scan.V_BACK=SMALL_RASTER ? 10 : 33;
    integer audio_cycles=0,pcm_frames=0,nonzero_frames=0;
    integer sent=0,received=0,mode_changes=0,video_pixels=0,checks=0;
    integer min_frame_cycles=2000000000,max_frame_cycles=0,last_frame=0;
    integer max_voices=0;
    logic prior_mode=0;
    logic [63:0] expected[0:127];
    task automatic check(input logic ok,input string description);
        begin checks++;if(ok!==1'b1)$fatal(1,"coexistence: %s",description);end
    endtask
    always @(posedge sys_clk) begin
        #1;
        audio_cycles++;
        if ({i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx,dut.buffered_left,dut.buffered_right,
              dut.audio_underrun,dut.status_active_voice_count,dut.pcm_commit_count,
              dut.core_max_processing_cycles} !==
            {r_i2s_bclk,r_i2s_lrck,r_i2s_din,r_pa_en,r_uart_tx,reference_top.buffered_left,
              reference_top.buffered_right,reference_top.audio_underrun,
              reference_top.status_active_voice_count,reference_top.pcm_commit_count,
              reference_top.core_max_processing_cycles})
            $fatal(1,"audio changed due to display at cycle %0d",audio_cycles);
        if(dut.rst_sync_n && dut.i2s_frame_tick)begin
            pcm_frames++;
            if(dut.buffered_left!=0)nonzero_frames++;
            if(last_frame!=0)begin
                if(audio_cycles-last_frame<min_frame_cycles)min_frame_cycles=audio_cycles-last_frame;
                if(audio_cycles-last_frame>max_frame_cycles)max_frame_cycles=audio_cycles-last_frame;
            end
            last_frame=audio_cycles;
        end
        if(dut.status_active_voice_count>max_voices)max_voices=dut.status_active_voice_count;
    end
    // Exact once-only display payloads within each shared visual-reset epoch.
    always @(posedge sys_clk or negedge dut.u_visual.visual_rst_n) begin
        if(!dut.u_visual.visual_rst_n)sent=0;
        else if(dut.u_visual.sys_reset_done && dut.shared_event_valid && dut.shared_event_ready)begin
            if(sent>=128)$fatal(1,"display scoreboard overflow");
            expected[sent]=dut.shared_event_data;sent++;
        end
    end
    always @(posedge dut.u_visual.pixel_clk or negedge dut.u_visual.visual_rst_n) begin
        if(!dut.u_visual.visual_rst_n)begin received=0;prior_mode=0;end
        else if(dut.u_visual.video_reset_done)begin
            if(dut.u_visual.video_valid && dut.u_visual.video_ready)begin
                if(received>=sent || dut.u_visual.video_data!==expected[received])
                    $fatal(1,"display duplicate/reorder/corrupt payload");
                received++;
            end
            if(dut.u_visual.display_mode!=prior_mode)mode_changes++;
            prior_mode=dut.u_visual.display_mode;
            if(dut.u_visual.de)video_pixels++;
        end
    end
    task automatic byte_in(input logic [7:0] value);
        @(negedge sys_clk);midi_rx=0;repeat(1600)@(negedge sys_clk);
        for(integer bit_id=0;bit_id<8;bit_id++)begin midi_rx=value[bit_id];repeat(1600)@(negedge sys_clk);end
        midi_rx=1;repeat(1600)@(negedge sys_clk);
    endtask
    task automatic message(input logic [7:0] status_byte,data1,data2);
        byte_in(status_byte);byte_in(data1);byte_in(data2);
        repeat(100)@(negedge sys_clk);
    endtask
    initial begin
        repeat(20)@(negedge sys_clk);sys_rst_n=1;
        repeat(200)@(negedge sys_clk);
        for(integer n=60;n<64;n++)message(8'h90,8'(n),8'd100);
        check(dut.status_active_voice_count==4,"four real MIDI voices active");
        message(8'hb0,8'd64,8'd127);
        for(integer n=60;n<64;n++)message(8'h80,8'(n),0);
        #1000000;
        check(dut.status_active_voice_count==4,"CC64 keeps four released keys occupied");
        check(dut.audio_underrun==0,"no underrun with active display");
        // Freeze only video clocks. Audio reference must remain bit-identical.
        dut.u_visual.u_video_pll.clock_run=0;
        #1000000;
        check(dut.status_active_voice_count==4 && dut.audio_underrun==0,"audio survives video clock stop");
        // PLL loss asserts the same reset on both visual domains; flush queued
        // data even with destination stopped. Never resets the audio core.
        dut.u_visual.u_video_pll.lock=0;
        #1000000;
        check(!dut.u_visual.video_valid && !dut.u_visual.sys_reset_done,"PLL loss flushes display");
        check(dut.status_active_voice_count==4 && dut.audio_underrun==0,"audio survives PLL loss");
        dut.u_visual.u_video_pll.clock_run=1;dut.u_visual.u_video_pll.lock=1;
        #1000000;
        check(received==0,"no old display events replay after PLL reset");
        message(8'hb0,8'd64,0);
        // At least two complete production 640x480 frames after PLL recovery.
        #(SMALL_RASTER ? 4000000 : 36000000);
        check(pcm_frames>(SMALL_RASTER ? 600 : 1800) && nonzero_frames>(SMALL_RASTER ? 500 : 1200),"production PCM nonvacuous");
        check(min_frame_cycles==1041 && max_frame_cycles==1042,"actual 48kHz cadence");
        check(max_voices==4 && dut.audio_underrun==0,"four voices, no audio underflow");
        check(dut.event_fifo_level==0 && dut.status_event_overflow==0,"input FIFO drains");
        check(dut.u_visual.drop_count==0 && sent==received && sent>0,"accepted event display epoch delivered");
        check(mode_changes>=2 && video_pixels>(SMALL_RASTER ? 64*48 : 640*480),"both modes and real raster exercised");
        check(dut.u_visual.control_sys_done && dut.u_visual.control_video_done,"control bridge recovered");
        $display("PASS coexistence small_raster=%0d checks=%0d audio_cycles=%0d pcm_frames=%0d nonzero_frames=%0d frame_min/max=%0d/%0d modes=%0d video_pixels=%0d received=%0d",SMALL_RASTER,checks,audio_cycles,pcm_frames,nonzero_frames,min_frame_cycles,max_frame_cycles,mode_changes,video_pixels,received);
        $finish;
    end
    initial begin #80000000;$fatal(1,"coexistence timeout");end
endmodule
