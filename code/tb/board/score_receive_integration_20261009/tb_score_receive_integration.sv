`timescale 1ns/1ps
module tb_score_receive_integration;
    parameter integer NEGATIVE_STOP=0;
    reg sys_clk=0,sys_rst_n=0,midi_rx=1,score_uart_rx=1;
    reg [1:0] key_n=2'b11;
    always #10 sys_clk=~sys_clk;
    wire i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx,score_uart_tx,tmds_clk_p,tmds_clk_n;
    wire [2:0] tmds_data_p,tmds_data_n;
    audio_visual_coexistence_top dut(.*);
    wire ref_bclk,ref_lrck,ref_din,ref_pa,ref_uart,ref_cp,ref_cn;
    wire [2:0] ref_dp,ref_dn;
    reference_audio_visual_top refdut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.key_n(key_n),.midi_rx(midi_rx),.i2s_bclk(ref_bclk),.i2s_lrck(ref_lrck),.i2s_din(ref_din),.pa_en(ref_pa),.uart_tx(ref_uart),.tmds_clk_p(ref_cp),.tmds_clk_n(ref_cn),.tmds_data_p(ref_dp),.tmds_data_n(ref_dn));
    integer audio_checks=0,pixel_checks=0,frames=0,nonzero=0,commits=0;
    integer packets=0,current_case=-1,fd=0,pfd=0,dp=0,total=0,b,n;
    integer rxbytes=0,txbytes=0,ret,size,i,k,wait_cycles;
    reg [7:0] rawbyte,bytes[0:141];
    string operation,plan,capture;
    localparam integer BIT_NS=8675;
    always @(posedge dut.core_clk) begin
        if(dut.rst_sync_n && refdut.rst_sync_n) begin
            audio_checks=audio_checks+1;
            if({dut.buffered_left,dut.buffered_right,dut.pending_valid,dut.frame_sample_req,dut.sample_req_id,dut.pcm_valid_q,dut.pcm_ready,dut.audio_frame_count,dut.pcm_request_count,dut.pcm_commit_count,dut.audio_underrun,dut.status_active_voice_count,dut.status_clip_count,dut.shared_event_valid,dut.shared_event_ready,dut.shared_event_data,i2s_bclk,i2s_lrck,i2s_din,pa_en,uart_tx}
               !=={refdut.buffered_left,refdut.buffered_right,refdut.pending_valid,refdut.frame_sample_req,refdut.sample_req_id,refdut.pcm_valid_q,refdut.pcm_ready,refdut.audio_frame_count,refdut.pcm_request_count,refdut.pcm_commit_count,refdut.audio_underrun,refdut.status_active_voice_count,refdut.status_clip_count,refdut.shared_event_valid,refdut.shared_event_ready,refdut.shared_event_data,ref_bclk,ref_lrck,ref_din,ref_pa,ref_uart})
                $fatal(1,"UPLOAD_AUDIO_OR_STAT_CHANGED");
            if(dut.i2s_frame_tick) begin frames=frames+1;if(dut.buffered_left!=0)nonzero=nonzero+1;end
            if(dut.score_commit_pulse)commits=commits+1;
        end
    end
    always @(posedge dut.u_visual.pixel_clk) if(dut.u_visual.video_reset_done && refdut.u_visual.video_reset_done) begin
        pixel_checks=pixel_checks+1;
        if({dut.u_visual.dvi_hs,dut.u_visual.dvi_vs,dut.u_visual.dvi_de,dut.u_visual.dvi_r,dut.u_visual.dvi_g,dut.u_visual.dvi_b,dut.u_visual.wave_sample_valid,dut.u_visual.wave_sample_seq,dut.u_visual.wave_sample_left,dut.u_visual.wave_restart}
           !=={refdut.u_visual.dvi_hs,refdut.u_visual.dvi_vs,refdut.u_visual.dvi_de,refdut.u_visual.dvi_r,refdut.u_visual.dvi_g,refdut.u_visual.dvi_b,refdut.u_visual.wave_sample_valid,refdut.u_visual.wave_sample_seq,refdut.u_visual.wave_sample_left,refdut.u_visual.wave_restart})
            $fatal(1,"UPLOAD_WAVE_OR_VIDEO_CHANGED");
    end
    initial forever begin
        @(negedge score_uart_tx);
        if(dut.rst_sync_n) begin
            #(BIT_NS*1.5);rawbyte=0;
            for(b=0;b<8;b=b+1) begin rawbyte[b]=score_uart_tx;#(BIT_NS);end
            if(score_uart_tx!==1)$fatal(1,"SCORE_TX_STOPBIT");
            bytes[dp]=rawbyte;dp=dp+1;txbytes=txbytes+1;
            if(dp==12)total=14+{bytes[11],bytes[10]};
            if(dp>142 || total>142)$fatal(1,"SCORE_TX_LENGTH");
            if(total && dp==total)begin
                $fwrite(fd,"TX %0d ",current_case);
                for(n=0;n<total;n=n+1)$fwrite(fd,"%02x",bytes[n]);
                $fwrite(fd,"\n");packets=packets+1;dp=0;total=0;
                if(NEGATIVE_STOP)begin $fdisplay(fd,"NEGATIVE_STOP first_serial_reply");$fclose(fd);$display("NEGATIVE_FIRST_REPLY_CAPTURED");$finish;end
            end
        end
    end
    task send_byte(input[7:0]value);
        integer j;
        begin score_uart_rx=0;#(BIT_NS);for(j=0;j<8;j=j+1)begin score_uart_rx=value[j];#(BIT_NS);end score_uart_rx=1;#(BIT_NS);rxbytes=rxbytes+1;end
    endtask
    task midi_byte(input[7:0]value);
        integer j;
        begin @(negedge dut.core_clk);midi_rx=0;#32000;for(j=0;j<8;j=j+1)begin midi_rx=value[j];#32000;end midi_rx=1;#32000;end
    endtask
    integer before_packets;
    initial begin
        if(!$value$plusargs("PLAN=%s",plan)||!$value$plusargs("CAPTURE=%s",capture))$fatal(1,"FILEARGS");
        pfd=$fopen(plan,"r");fd=$fopen(capture,"w");if(!pfd||!fd)$fatal(1,"OPEN");
        $fdisplay(fd,"META exact_score_uart_fulltop nominalPLL DVIstub");
        #100;sys_rst_n=1;wait(dut.rst_sync_n&&refdut.rst_sync_n);
        midi_byte(8'h90);midi_byte(8'd60);midi_byte(8'd100);
        midi_byte(8'h90);midi_byte(8'd64);midi_byte(8'd88);
        while(!$feof(pfd))begin
            ret=$fscanf(pfd,"%s %d %d",operation,current_case,size);
            if(ret!=3)begin if(!$feof(pfd))$fatal(1,"PLANBAD");end
            else begin
                $fdisplay(fd,"CASE %0d %s",current_case,operation);before_packets=packets;
                if(operation=="R")begin
                    if(commits!=1)$fatal(1,"ATOMIC_COMMIT_DUPLICATE");
                    sys_rst_n=0;#1000;sys_rst_n=1;wait(dut.rst_sync_n&&refdut.rst_sync_n);repeat(20)@(negedge dut.core_clk);commits=0;dp=0;total=0;
                end else if(operation=="S")begin
                    $fwrite(fd,"RX %0d ",current_case);
                    for(i=0;i<size;i=i+1)begin ret=$fscanf(pfd,"%h",rawbyte);if(ret!=1)$fatal(1,"BYTEBAD");$fwrite(fd,"%02x",rawbyte);send_byte(rawbyte);end
                    $fwrite(fd,"\n");wait_cycles=0;
                    while(packets==before_packets && wait_cycles<400000)begin @(negedge dut.core_clk);wait_cycles=wait_cycles+1;end
                    if(packets!=before_packets+1)$fatal(1,"MISSING_OR_DUPLICATE_RESPONSE");
                    #(BIT_NS);$fdisplay(fd,"PUBLIC %0d %0d %0d %0d %0d",current_case,dut.score_committed_valid,dut.score_committed_count,dut.score_committed_id,commits);
                end else $fatal(1,"UNKNOWN_OP");
            end
        end
        repeat(4000)@(negedge dut.core_clk);
        if(frames<800||nonzero<100||audio_checks<600000||pixel_checks<200000)$fatal(1,"SHORT_COVERAGE");
        $fdisplay(fd,"END %0d %0d %0d %0d %0d %0d %0d",audio_checks,pixel_checks,frames,nonzero,packets,rxbytes,txbytes);
        $fclose(fd);$fclose(pfd);$display("HARNESS_COMPLETE_SCORE_AUDIO_EQ checks=%0d packets=%0d",audio_checks,packets);$finish;
    end
    initial begin #160000000;$fatal(1,"GLOBAL_SIM_TIME_LIMIT");end
endmodule
