`timescale 1ns/1ps
// Exact integrated display_probe plus all old animation, scan and new CDC/wave.
// PCM stimulus is original sealed A replay, not live synth or invented MIDI PCM.
module tb_display_integration;
    parameter integer MODE=0;
    reg ref_clk=0,sys_rst_n=0,audio_rst_n=0,frame_load=0;
    always #10 ref_clk=~ref_clk;
    wire core_clk;
    reg signed [23:0] play_left=0,play_right=0;
    wire tmds_clk_p,tmds_clk_n,pll_locked;
    wire [2:0]tmds_p,tmds_n;
    audio_visual_display_probe #(.SYS_CLK_HZ(40000000)) dut(
        .sys_clk(core_clk),.sys_rst_n(sys_rst_n),.ref_clk(ref_clk),.core_clk(core_clk),
        .wave_audio_rst_n(audio_rst_n),.wave_frame_load(frame_load),
        .wave_play_left(play_left),.wave_play_right(play_right),
        .accepted_valid(1'b0),.accepted_data(64'd0),
        .tmds_clk_p(tmds_clk_p),.tmds_clk_n(tmds_clk_n),
        .tmds_data_p(tmds_p),.tmds_data_n(tmds_n),.visual_pll_locked(pll_locked));
    integer fd,vf,ret,count,idx,vector_idx,left_value,right_value,cycles;
    integer video_checks=0,video_frames=0,delivered=0,trace_pixels=0,wave_checks=0,scene_checks=0,loads=0;
    string cap,vectors;
    // Independent sample-window oracle is full signed24; no DUTbank hierarchy.
    integer samples[0:2047],pmin[0:511],pmax[0:511],fmin[0:511],fmax[0:511];
    integer used=0,index,j,lo,hi,rawx,rawy;
    reg have_seq=0,pending=0,front=0;
    reg [31:0] last_seq=0;
    reg [26:0] expect0=27'h6000000,expect1=27'h6000000,
                expect2=27'h6000000,expect3=27'h6000000,new_expected;
    reg [23:0] wavecolor,rawscene;
    reg in_box=0;
    always @(posedge dut.pixel_clk) begin
        if(!dut.waveform_rst_n)begin
            used=0;have_seq=0;pending=0;front=0;
        end else begin
            if(dut.wave_restart)begin used=0;have_seq=0;pending=0;front=0;end
            else if(dut.frame_start && pending)begin
                for(index=0;index<512;index=index+1)begin fmin[index]=pmin[index];fmax[index]=pmax[index];end
                front=1;pending=0;
            end
            if(dut.wave_sample_valid && !dut.wave_restart)begin
                delivered=delivered+1;
                if(have_seq && dut.wave_sample_seq!=last_seq+32'd1)used=0;
                have_seq=1;last_seq=dut.wave_sample_seq;
                samples[used]=$signed(dut.wave_sample_left);used=used+1;
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
                  $signed(dut.wave_sample_left),$signed(dut.wave_sample_right));
            end
        end
        if(!dut.video_reset_done)begin
            expect0=27'h6000000;expect1=expect0;expect2=expect0;expect3=expect0;
        end else begin
            rawx=dut.pixel_x;rawy=dut.pixel_y;
            rawscene={dut.rgb_r,dut.rgb_g,dut.rgb_b};
            in_box=dut.de && rawx>=64 && rawx<=575 && rawy>=64 && rawy<=319;
            wavecolor=24'h081020;
            if(rawy==191)wavecolor=24'h404040;
            if(in_box && front && !dut.wave_restart && dut.waveform_rst_n)begin
                lo=fmin[rawx-64]>>>16;hi=fmax[rawx-64]>>>16;
                if(rawy>=191-hi && rawy<=191-lo)begin wavecolor=24'h00e0ff;trace_pixels=trace_pixels+1;end
            end
            // During branch reset the waveformmask pipeline is asynchronously0.
            if(in_box && dut.waveform_rst_n) rawscene=wavecolor;
            new_expected={dut.hs,dut.vs,dut.de,rawscene};
            expect3=expect2;expect2=expect1;expect1=expect0;expect0=new_expected;
            video_checks=video_checks+1;
            if(in_box)wave_checks=wave_checks+1;else scene_checks=scene_checks+1;
            if(dut.frame_start)begin video_frames=video_frames+1;$fdisplay(fd,"V %0t %0d %0d %0d",$time,video_frames,front,delivered);end
        end
        #1;
        if(dut.video_reset_done &&
          {dut.dvi_hs,dut.dvi_vs,dut.dvi_de,
           dut.dvi_r,dut.dvi_g,dut.dvi_b}!==expect3)
          $fatal(1,"COMPOSITE_ALIGNMENT actual=%h expected=%h x=%0d y=%0d",{dut.dvi_hs,dut.dvi_vs,dut.dvi_de,dut.dvi_r,dut.dvi_g,dut.dvi_b},expect3,dut.pixel_x,dut.pixel_y);
    end

    initial begin
        if(!$value$plusargs("CAPTURE=%s",cap)||!$value$plusargs("VECTORS=%s",vectors)||!$value$plusargs("COUNT=%d",count))$fatal(1,"ARGS");
        fd=$fopen(cap,"w");vf=$fopen(vectors,"r");if(!fd||!vf)$fatal(1,"FILES");
        $fdisplay(fd,"META 1 integrated_display %0d %0d",MODE,count);
        #100;sys_rst_n=1;wait(pll_locked);repeat(6)@(negedge core_clk);audio_rst_n=1;
        repeat(20)@(negedge core_clk);
        for(idx=0;idx<count;idx=idx+1)begin
            ret=$fscanf(vf,"%d %d %d %d\n",vector_idx,left_value,right_value,cycles);
            if(ret!=4||vector_idx!=idx||cycles<1)$fatal(1,"VECTOR_FORMAT");
            play_left=left_value;play_right=right_value;frame_load=1;loads=loads+1;
            $fdisplay(fd,"A %0t %0d %0d %0d",$time,idx,left_value,right_value);
            @(negedge core_clk);frame_load=0;
            repeat(cycles-1)@(negedge core_clk);
        end
        $fclose(vf);
        wait(video_frames>=9);@(negedge dut.pixel_clk);
        if(video_checks<3360000||trace_pixels<1||delivered!=count||wave_checks<1||scene_checks<1)$fatal(1,"COVERAGE");
        $fdisplay(fd,"END %0d %0d %0d %0d %0d %0d %0d",video_checks,video_frames,loads,delivered,trace_pixels,scene_checks,wave_checks);
        $fclose(fd);$display("PASS INTEGRATED_DISPLAY video=%0d frames=%0d samples=%0d trace=%0d",video_checks,video_frames,delivered,trace_pixels);$finish;
    end
    initial begin #200000000;$fatal(1,"DISPLAY_SIMTIME_LIMIT");end
endmodule
