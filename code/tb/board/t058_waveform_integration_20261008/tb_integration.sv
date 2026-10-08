`timescale 1ns/1ps
// Full top wiring, actual vendor PLL, simulation-only DVI encrypted-IP stub.
// Observe module boundaries and physical audio pins; no internal RAM oracle.
module tb_waveform_integration;
    parameter integer LONG_SCAN=0;
    parameter integer MODE=0; // 0 normal; 1 display pause/reset; 2 boot/PLL-reset
    reg sys_clk=0, sys_rst_n=0, midi_rx=1;
    reg [1:0] key_n=2'b11;
    always #10 sys_clk=~sys_clk;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx,tmds_clk_p,tmds_clk_n;
    wire [2:0] tmds_data_p,tmds_data_n;
    audio_visual_coexistence_top dut(.*);
    wire ref_bck,ref_ws,ref_din,ref_pa,ref_uart,ref_tmds_clk_p,ref_tmds_clk_n;
    wire [2:0] ref_tmds_p,ref_tmds_n;
    reference_audio_visual_top refdut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),
        .midi_rx(midi_rx),.key_n(key_n),.i2s_bclk(ref_bck),.i2s_lrck(ref_ws),
        .i2s_din(ref_din),.pa_en(ref_pa),.uart_tx(ref_uart),
        .tmds_clk_p(ref_tmds_clk_p),.tmds_clk_n(ref_tmds_clk_n),
        .tmds_data_p(ref_tmds_p),.tmds_data_n(ref_tmds_n));
    integer fd,audio_checks=0,audio_frames=0,video_checks=0,video_frames=0;
    integer adopted=0,delivered=0,trace_pixels=0,wave_checks=0,scene_checks=0;
    integer positive_pcm=0,negative_pcm=0,zero_pcm=0,stereo_frames=0;
    integer elapsed_lane=0,pcm_index=0,slot_edges=0,pixel_drop=0;
    string cap;
    // Read the complete raw buffer/play interfaces before the sender's NBA.
    always @(posedge dut.core_clk) if(dut.rst_sync_n && refdut.rst_sync_n) begin
        audio_checks=audio_checks+1;
        if ({dut.buffered_left,dut.buffered_right,dut.pending_valid,
             dut.frame_sample_req,dut.sample_req_id,dut.pcm_valid_q,dut.pcm_ready,
             dut.audio_frame_count,dut.pcm_request_count,dut.pcm_commit_count,
             dut.audio_underrun,dut.status_active_voice_count,dut.status_clip_count,
             dut.shared_event_valid,dut.shared_event_ready,dut.shared_event_data,
             i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx}
          !== {refdut.buffered_left,refdut.buffered_right,refdut.pending_valid,
             refdut.frame_sample_req,refdut.sample_req_id,refdut.pcm_valid_q,refdut.pcm_ready,
             refdut.audio_frame_count,refdut.pcm_request_count,refdut.pcm_commit_count,
             refdut.audio_underrun,refdut.status_active_voice_count,refdut.status_clip_count,
             refdut.shared_event_valid,refdut.shared_event_ready,refdut.shared_event_data,
             ref_bck,ref_ws,ref_din,ref_pa,ref_uart}) $fatal(1,"AUDIO_EQUivalence");
        if(dut.i2s_frame_tick) begin
            audio_frames=audio_frames+1;adopted=adopted+1;
            if(dut.buffered_left>0) positive_pcm=positive_pcm+1;
            else if(dut.buffered_left<0) negative_pcm=negative_pcm+1;
            else zero_pcm=zero_pcm+1;
            $fdisplay(fd,"A %0t %0d %0d %0d %0d %0d %0d",$time,
               audio_frames,$signed(dut.buffered_left),$signed(dut.buffered_right),
               dut.pcm_commit_count,dut.audio_underrun,dut.sample_req_id);
        end
        if(dut.u_visual.u_wave_bridge.observation_dropped)pixel_drop=pixel_drop+1;
    end
    reg was_synchronized=0,prior_ws=0;
    reg [31:0] serial_bits=0;
    integer half_edges=0,serial_halves=0;
    // Shared audio pins are compared every core cycle above; independently
    // count physical complete32edge WS half-slots, rejecting partial startup.
    always @(posedge i2s_bclk) if(dut.rst_sync_n) begin
        if(!was_synchronized)begin
            if(i2s_lrck!=prior_ws)begin was_synchronized=1;half_edges=0;serial_bits=0;prior_ws=i2s_lrck;end
        end else if(i2s_lrck!=prior_ws)begin
            if(half_edges!=32)$fatal(1,"SERIAL_SLOT_COUNT");
            if(serial_bits[31:16]!==0)$fatal(1,"SERIAL_FILLER");
            serial_halves=serial_halves+1;
            if(serial_halves%2==0)stereo_frames=stereo_frames+1;
            prior_ws=i2s_lrck;half_edges=0;serial_bits=0;
        end
        if(was_synchronized)begin serial_bits={serial_bits[30:0],i2s_din};half_edges=half_edges+1;end
    end
    always @(negedge dut.rst_sync_n)begin was_synchronized=0;prior_ws=0;half_edges=0;serial_bits=0;end
    // Independent sample-window oracle is full signed24; no DUTbank hierarchy.
    integer samples[0:2047],pmin[0:511],pmax[0:511],fmin[0:511],fmax[0:511];
    integer used=0,index,j,lo,hi,rawx,rawy;
    reg have_seq=0,pending=0,front=0;
    reg [31:0] last_seq=0;
    reg [26:0] expect0=27'h6000000,expect1=27'h6000000,
                expect2=27'h6000000,expect3=27'h6000000,new_expected;
    reg [23:0] wavecolor,rawscene;
    reg in_box=0;
    always @(posedge dut.u_visual.pixel_clk) begin
        if(!dut.u_visual.waveform_rst_n)begin
            used=0;have_seq=0;pending=0;front=0;
        end else begin
            if(dut.u_visual.wave_restart)begin used=0;have_seq=0;pending=0;front=0;end
            else if(dut.u_visual.frame_start && pending)begin
                for(index=0;index<512;index=index+1)begin fmin[index]=pmin[index];fmax[index]=pmax[index];end
                front=1;pending=0;
            end
            if(dut.u_visual.wave_sample_valid && !dut.u_visual.wave_restart)begin
                delivered=delivered+1;
                if(have_seq && dut.u_visual.wave_sample_seq!=last_seq+32'd1)used=0;
                have_seq=1;last_seq=dut.u_visual.wave_sample_seq;
                samples[used]=$signed(dut.u_visual.wave_sample_left);used=used+1;
                if(used==2048)begin
                    for(index=0;index<512;index=index+1)begin
                        lo=samples[4*index];hi=lo;
                        for(j=1;j<4;j=j+1)begin
                            if(samples[4*index+j]<lo)lo=samples[4*index+j];
                            if(samples[4*index+j]>hi)hi=samples[4*index+j];
                        end
                        pmin[index]=lo;pmax[index]=hi;
                    end
                    used=0;pending=1;
                end
                $fdisplay(fd,"D %0t %0d %0d %0d",$time,last_seq,
                  $signed(dut.u_visual.wave_sample_left),$signed(dut.u_visual.wave_sample_right));
            end
        end
        if(!dut.u_visual.video_reset_done)begin
            expect0=27'h6000000;expect1=expect0;expect2=expect0;expect3=expect0;
        end else begin
            rawx=dut.u_visual.pixel_x;rawy=dut.u_visual.pixel_y;
            rawscene={dut.u_visual.rgb_r,dut.u_visual.rgb_g,dut.u_visual.rgb_b};
            in_box=dut.u_visual.de && rawx>=64 && rawx<=575 && rawy>=64 && rawy<=319;
            wavecolor=24'h081020;
            if(rawy==191)wavecolor=24'h404040;
            if(in_box && front && !dut.u_visual.wave_restart && dut.u_visual.waveform_rst_n)begin
                lo=fmin[rawx-64]>>>16;hi=fmax[rawx-64]>>>16;
                if(rawy>=191-hi && rawy<=191-lo)begin wavecolor=24'h00e0ff;trace_pixels=trace_pixels+1;end
            end
            // During branch reset the waveformmask pipeline is asynchronously0.
            if(in_box && dut.u_visual.waveform_rst_n) rawscene=wavecolor;
            new_expected={dut.u_visual.hs,dut.u_visual.vs,dut.u_visual.de,rawscene};
            expect3=expect2;expect2=expect1;expect1=expect0;expect0=new_expected;
            video_checks=video_checks+1;
            if(in_box)wave_checks=wave_checks+1;else scene_checks=scene_checks+1;
            if(dut.u_visual.frame_start)begin video_frames=video_frames+1;$fdisplay(fd,"V %0t %0d %0d %0d",$time,video_frames,front,delivered);end
        end
        #1;
        if(dut.u_visual.video_reset_done &&
          {dut.u_visual.dvi_hs,dut.u_visual.dvi_vs,dut.u_visual.dvi_de,
           dut.u_visual.dvi_r,dut.u_visual.dvi_g,dut.u_visual.dvi_b}!==expect3)
          $fatal(1,"COMPOSITE_ALIGNMENT actual=%h expected=%h x=%0d y=%0d",{dut.u_visual.dvi_hs,dut.u_visual.dvi_vs,dut.u_visual.dvi_de,dut.u_visual.dvi_r,dut.u_visual.dvi_g,dut.u_visual.dvi_b},expect3,dut.u_visual.pixel_x,dut.u_visual.pixel_y);
    end
    task byte_midi(input [7:0] b);
        integer k;
        begin
            @(negedge sys_clk);midi_rx=0;#32000;
            for(k=0;k<8;k=k+1)begin midi_rx=b[k];#32000;end
            midi_rx=1;#32000;
        end
    endtask
    initial begin
        if(!$value$plusargs("CAPTURE=%s",cap))$fatal(1,"CAPTURE_ARGUMENT");
        fd=$fopen(cap,"w");if(!fd)$fatal(1,"CAPTURE_FILE");
        $fdisplay(fd,"META 1 full_top %0d",MODE);
        #100;sys_rst_n=1;
        wait(dut.rst_sync_n && refdut.rst_sync_n);repeat(20)@(negedge dut.core_clk);
        if(dut.core_clk!==refdut.core_clk)$fatal(1,"PLL_CORE_PHASE");
        // Raw MIDI gives real fourvoice/CC64/PitchMod handling without injected PCM.
        byte_midi(8'h90);byte_midi(8'd60);byte_midi(8'd100);
        byte_midi(8'h90);byte_midi(8'd64);byte_midi(8'd88);
        byte_midi(8'h90);byte_midi(8'd67);byte_midi(8'd72);
        byte_midi(8'h90);byte_midi(8'd72);byte_midi(8'd80);
        byte_midi(8'hb0);byte_midi(8'd64);byte_midi(8'd127);
        if(MODE==1)begin
            wait(audio_frames>=300);@(negedge dut.core_clk);
            $fdisplay(fd,"C %0t pixel_stop",$time);
            force dut.u_visual.pixel_clk=0;#2000000;release dut.u_visual.pixel_clk;
            $fdisplay(fd,"C %0t pixel_resume",$time);
            // Explicit producer-output fault injection on BOTH paths, proving
            // held-frame equivalence/recovery rather than measuring normal underrun.
            @(negedge dut.core_clk);
            force dut.g_polyphonic.u_audio_core.u_commit.pcm_valid=0;
            force refdut.g_polyphonic.u_audio_core.u_commit.pcm_valid=0;
            repeat(3) @(posedge dut.i2s_frame_tick);
            @(negedge dut.core_clk);
            release dut.g_polyphonic.u_audio_core.u_commit.pcm_valid;
            release refdut.g_polyphonic.u_audio_core.u_commit.pcm_valid;
            $fdisplay(fd,"C %0t producer_fault_released",$time);
        end
        if(MODE==2)begin
            wait(audio_frames>=128);@(negedge sys_clk);sys_rst_n=0;#5000;sys_rst_n=1;
            wait(dut.rst_sync_n && refdut.rst_sync_n);repeat(12)@(negedge dut.core_clk);
            byte_midi(8'h90);byte_midi(8'd55);byte_midi(8'd110);
        end
        wait(audio_frames>=384);
        byte_midi(8'h80);byte_midi(8'd60);byte_midi(8'd0);
        byte_midi(8'hb0);byte_midi(8'd64);byte_midi(8'd0);
        if(LONG_SCAN)wait(video_frames>=7);else wait(audio_frames>=640);
        @(negedge dut.u_visual.pixel_clk);
        if(audio_checks<100000 || audio_frames<600 || video_checks<200000 || (LONG_SCAN && trace_pixels<1) || positive_pcm<1 || negative_pcm<1 || stereo_frames<500)
            $fatal(1,"INSUFFICIENT_NONEMPTY_COVERAGE");
        if(MODE==1 && pixel_drop<1)$fatal(1,"PAUSE_DID_NOT_FILL_QUEUE");
        $fdisplay(fd,"END %0d %0d %0d %0d %0d %0d %0d %0d %0d",audio_checks,audio_frames,video_checks,video_frames,delivered,trace_pixels,stereo_frames,pixel_drop,dut.audio_underrun);
        $fclose(fd);$display("PASS FULL_TOP SHORT_EQ_MODE=%0d audio=%0d frames=%0d video=%0d trace=%0d stereo=%0d drops=%0d",MODE,audio_checks,audio_frames,video_checks,trace_pixels,stereo_frames,pixel_drop);$finish;
    end
    initial begin #240000000;$fatal(1,"SIMULATION_TIME_LIMIT");end
endmodule
