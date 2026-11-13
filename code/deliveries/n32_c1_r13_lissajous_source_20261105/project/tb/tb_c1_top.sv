`timescale 1ns/1ps
module tb_c1_top;
    reg clk50=0,reset_n=0,midi=1;
    always #10 clk50=~clk50;
    pro_audio_minimal_top dut(
        .sys_clk_50m(clk50),.sys_rst_n(reset_n),.key_n(2'b11),.midi_rx(midi),
        .i2s_bclk(),.i2s_lrck(),.i2s_din(),.pa_en(),.uart_tx(),
        .ble_uart_rx(1'b1),.ble_uart_tx(),.tmds_clk_p(),.tmds_clk_n(),
        .tmds_data_p(),.tmds_data_n());
    wire clk=dut.core_clk;
`define C1_BRIDGE dut.u_score_visual.u_display.u_waveform_overlay.u_shared_waveform.u_bridge
`define C1_WAVE dut.u_score_visual.u_display.u_waveform_overlay.u_shared_waveform.u_renderer
`define C1_SPEC dut.u_score_visual.u_display.u_waveform_overlay.u_shared_spectrum
`define C1_TX dut.u_audio.u_i2s_tx
c1_pcm_checker u_c1_pcm_checker (
    .core_clk(clk), .pixel_clk(dut.pixel_clk),
    .tx_rst_n(`C1_TX.rst_n), .tx_frame(`C1_TX.frame_tick), .tx_valid(`C1_TX.valid),
    .tx_left(`C1_TX.pcm_left), .tx_right(`C1_TX.pcm_right),
    .tx_adopted_left(`C1_TX.sample_left), .tx_adopted_right(`C1_TX.sample_right),
    .observer_rst_n(`C1_BRIDGE.observer_reset_done),
    .observer_frame(`C1_BRIDGE.audio_frame_load),
    .observer_in_left(`C1_BRIDGE.audio_play_left), .observer_in_right(`C1_BRIDGE.audio_play_right),
    .observer_valid(`C1_BRIDGE.observed_valid), .observer_seq(`C1_BRIDGE.observed_seq),
    .observer_left(`C1_BRIDGE.observed_left), .observer_right(`C1_BRIDGE.observed_right),
    .spectrum_valid(`C1_SPEC.sample_valid), .spectrum_seq(`C1_SPEC.sample_seq), .spectrum_left(`C1_SPEC.pcm_mono),
    .waveform_rst_n(`C1_WAVE.pixel_rst_n), .waveform_valid(`C1_WAVE.sample_valid),
    .waveform_seq(`C1_WAVE.sample_seq), .waveform_left(`C1_WAVE.sample_left), .waveform_right(`C1_WAVE.sample_right)
);

    `define C1 dut.u_audio.g_polyphonic
    `define FX `C1.u_audio_core.u_n8_core.g_c1_fx.post
    integer frames=0, commits=0, max_cycles=0, stereo=0, missed=0;
    `define OVERLAY dut.u_score_visual.u_display.u_waveform_overlay
    integer waveform_pixels=0,spectrum_pixels=0,lissajous_pixels=0;
    integer li_frames=0,li_packets=0,li_points=0,li_restarts=0,li_mask_pixels=0;
    integer title_pixels=0, title_anchor_pixels=0;
    integer min_li_x=640, max_li_x=0, min_li_y=480, max_li_y=0;
    always @(posedge dut.pixel_clk) begin
        if(`OVERLAY.lissajous_title_aligned) begin
            if(`OVERLAY.page_aligned!==3'd4 || !`OVERLAY.out_de ||
               `OVERLAY.x_pipe[4]<16 || `OVERLAY.x_pipe[4]>=272 ||
               `OVERLAY.y_pipe[4]<24 || `OVERLAY.y_pipe[4]>=38 ||
               {`OVERLAY.rgb_r,`OVERLAY.rgb_g,`OVERLAY.rgb_b}!==24'hd6f7ff)
                $fatal(1,"title is not aligned with its HDMI page or coordinates");
            title_pixels++;
            if(`OVERLAY.x_pipe[4]==16 && `OVERLAY.y_pipe[4]==24) title_anchor_pixels++;
        end
        if(`OVERLAY.page_for_pixel==3'd4) begin
            if(`OVERLAY.frame_start) li_frames++;
            if(`OVERLAY.lissajous_sample_valid) li_packets++;
            if(`OVERLAY.u_lissajous.point_valid) li_points++;
            if(`OVERLAY.u_lissajous.point_restart) li_restarts++;
        end
        if(`OVERLAY.page_aligned==3'd4 && `OVERLAY.lissajous_mask_aligned) li_mask_pixels++;
        if(`OVERLAY.page_aligned==2 && `OVERLAY.waveform_mask_aligned) waveform_pixels++;
        if(`OVERLAY.page_aligned==3 && `OVERLAY.spectrum_mask_aligned) spectrum_pixels++;
        if(`OVERLAY.page_aligned==3'd4 && `OVERLAY.lissajous_trace_aligned && `OVERLAY.out_de) begin
            if({`OVERLAY.rgb_r,`OVERLAY.rgb_g,`OVERLAY.rgb_b}!==`OVERLAY.lissajous_rgb_aligned)
                $fatal(1,"Lissajous pixels not selected on final HDMI raster");
            lissajous_pixels++;
            if(`OVERLAY.x_pipe[4]<min_li_x) min_li_x=int'(`OVERLAY.x_pipe[4]);
            if(`OVERLAY.x_pipe[4]>max_li_x) max_li_x=int'(`OVERLAY.x_pipe[4]);
            if(`OVERLAY.y_pipe[4]<min_li_y) min_li_y=int'(`OVERLAY.y_pipe[4]);
            if(`OVERLAY.y_pipe[4]>max_li_y) max_li_y=int'(`OVERLAY.y_pipe[4]);
        end
    end
    integer seen[0:4]='{default:0};
    integer modes[0:4]='{default:0};
    integer underrun_at_start=0;
    bit layer_check=0;
    bit [4:0] layer_heard='0;
    integer simultaneous_layer_frames=0;
    integer cycle_count=0, request_cycle=-1;
    function automatic signed [23:0] gain55(input logic signed [23:0] x);
        longint signed p;
        p=longint'(x)*1773;
        gain55=p<0 ? 24'(-(((-p)+2048)>>>12)) : 24'((p+2048)>>>12);
    endfunction
    always @(posedge clk) if(dut.core_rst_n) begin
        cycle_count++;
        if(`C1.m1_request_accept) request_cycle=cycle_count;
        if(`C1.m1_commit) begin
            if(request_cycle<0) $fatal(1,"commit without request");
            commits++;
            if(cycle_count-request_cycle>max_cycles)
                max_cycles=cycle_count-request_cycle;
            request_cycle=-1;
        end
        if(`FX.go)begin
            if(`FX.selected_q!=0) seen[`FX.timbre_q]++;
            if(`FX.dry_q!=0) modes[`FX.mode_q]++;
        end
        if(layer_check && `FX.go) begin
            if(`FX.piano!=0) layer_heard[0]=1;
            if(`FX.organ!=0) layer_heard[1]=1;
            if(`FX.snare!=0) layer_heard[2]=1;
            if(`FX.sax!=0) layer_heard[3]=1;
            if(`FX.guitar!=0) layer_heard[4]=1;
            if(`FX.piano!=0 && `FX.organ!=0 && `FX.snare!=0 && `FX.sax!=0 && `FX.guitar!=0)
                simultaneous_layer_frames++;
        end
        if(dut.sample_tick) begin
            frames++;
            if(frames>4 && !dut.u_audio.pending_valid) missed++;
            if({dut.adopted_pcm_left,dut.adopted_pcm_right} !==
               {gain55(dut.u_audio.buffered_left),gain55(dut.u_audio.buffered_right)})
                $fatal(1,"fixed gain or frame alignment failure frame %0d",frames);
            if(dut.adopted_pcm_left!=dut.adopted_pcm_right) stereo++;
        end
    end
    task automatic uart(input [7:0] b);
        @(negedge clk); midi=0;
        repeat(1280) @(negedge clk);
        for(integer k=0;k<8;k++) begin
            midi=b[k]; repeat(1280) @(negedge clk);
        end
        midi=1; repeat(1280) @(negedge clk);
    endtask
    task automatic wait_frames(input integer n);
        integer goal;
        goal=frames+n;
        while(frames<goal) @(negedge clk);
    endtask
    task automatic cc(input [6:0] ccnum, value);
        uart(8'hb0); uart({1'b0,ccnum}); uart({1'b0,value});
        wait_frames(2);
    endtask
    task automatic note(input [6:0] key,vel);
        uart(8'h90);uart({1'b0,key});uart({1'b0,vel});
        wait_frames(2);
    endtask
    task automatic select_mode(input [6:0] k1,input [2:0] expected);
        cc(7,k1);
        if(`C1.fx_mode!==expected) $fatal(1,"K1 boundary %d",k1);
    endtask
    task automatic select_voice(input [6:0] k2,input [2:0] expected);
        cc(91,k2);
        if(`C1.selected_timbre!==expected) $fatal(1,"K2 voice %d",k2);
    endtask
    initial begin
        repeat(30) @(negedge clk);
        reset_n=1; wait(dut.core_rst_n); wait_frames(6);
        underrun_at_start=dut.u_audio.audio_underrun;
        // One real MIDI NoteOn must excite all five independent stems.
        select_voice(127,4); select_mode(76,2); wait_frames(260);
        layer_check=1;
        note(60,96); wait_frames(180);
        layer_check=0;
        if(layer_heard!==5'b11111 || simultaneous_layer_frames==0)
            $fatal(1,"one-key ensemble stems missing: %b",layer_heard);
        $display("PASS R11_ONE_KEY_FIVE_STEMS mask=%b same_frame=%0d",layer_heard,simultaneous_layer_frames);
        note(60,0);
        select_mode(0,0); select_mode(25,0); select_voice(25,0); note(60,96); wait_frames(25);
        select_mode(26,1); wait_frames(1000);
        select_mode(50,1);
        select_voice(26,1); note(64,95); wait_frames(300);
        select_voice(51,2); note(38,100); wait_frames(300);
        select_voice(76,3); note(65,94); wait_frames(300);
        select_voice(101,4); note(69,96); wait_frames(300);
        select_mode(51,3); wait_frames(260); select_mode(75,3);
        select_mode(76,2); wait_frames(340);
        if(`FX.dry_q==0) $fatal(1,"no ensemble signal");
        cc(71,61);
        if(dut.extension_page_select!==1) $fatal(1,"K3 did not select falling page");
        cc(74,40);
        if(dut.extension_page_select!==2) $fatal(1,"K4 did not select waveform page");
        wait_frames(900);
        cc(74,41);
        if(dut.extension_page_select!==3) $fatal(1,"K4 did not select spectrum page");
        wait_frames(900);
        cc(74,81);
        if(dut.extension_page_select!==4) $fatal(1,"K4 did not select Lissajous");
        wait_frames(3200);
        if(lissajous_pixels==0 || `OVERLAY.lissajous_published_frames==0)
            $fatal(1,"no live PCM Lissajous raster frames=%0d packets=%0d points=%0d restarts=%0d published=%0d mask=%0d traces=%0d state=%0d clear=%0d count=%0d",
                   li_frames,li_packets,li_points,li_restarts,`OVERLAY.lissajous_published_frames,
                   li_mask_pixels,lissajous_pixels,`OVERLAY.u_lissajous.u_plot.state,
                   `OVERLAY.u_lissajous.u_plot.clear_address,`OVERLAY.u_lissajous.u_plot.point_count);
        $display("PASS R12_LISSAJOUS_HDMI published=%0d trace_pixels=%0d",
                 `OVERLAY.lissajous_published_frames,lissajous_pixels);
        if(title_pixels==0 || title_anchor_pixels==0 ||
           max_li_x-min_li_x<12 || max_li_y-min_li_y<12 ||
           min_li_x<=192 || max_li_x>=447 || min_li_y<=112 || max_li_y>=367)
            $fatal(1,"title/trace coverage invalid x=%0d..%0d y=%0d..%0d",min_li_x,max_li_x,min_li_y,max_li_y);
        $display("PASS R13_LISSAJOUS_TITLE_ZOOM title=%0d anchors=%0d trace_box=%0dx%0d",
                 title_pixels,title_anchor_pixels,max_li_x-min_li_x+1,max_li_y-min_li_y+1);
        cc(71,0);
        wait_frames(900);
        if(`OVERLAY.page_aligned!==3'd0) $fatal(1,"K3 did not return to rising page");
        select_mode(100,2);
        select_mode(101,4); wait_frames(260); select_mode(127,4); wait_frames(120);
        note(60,0); note(64,0); note(65,0); note(69,0);
        foreach(seen[i]) if(seen[i]==0) $fatal(1,"missing timbre %d",i);
        foreach(modes[i]) if(modes[i]==0) $fatal(1,"missing mode %d",i);
        if(stereo==0 || missed!=0 || dut.u_audio.audio_underrun!=underrun_at_start || max_cycles<=0 || max_cycles>=833)
            $fatal(1,"frame continuity stereo=%d missed=%d underrun=%d max=%d",
                stereo,missed,dut.u_audio.audio_underrun,max_cycles);
        if(`OVERLAY.spectrum_complete_count==0 || waveform_pixels==0 || spectrum_pixels==0)
            $fatal(1,"display output absent fft=%d wave_pixels=%d spectrum_pixels=%d",
                `OVERLAY.spectrum_complete_count,waveform_pixels,spectrum_pixels);
        $display("PASS C1_RENDER fft_windows=%0d wave_pixels=%0d spectrum_pixels=%0d",
            `OVERLAY.spectrum_complete_count,waveform_pixels,spectrum_pixels);
        $display("PASS C1_TOP frames=%0d commits=%0d max_compute=%0d missed=%0d stereo=%0d seen=%p modes=%p",
            frames,commits,max_cycles,missed,stereo,seen,modes);
        $finish;
    end
    initial begin #280000000; $fatal(1,"top test time limit"); end
endmodule
