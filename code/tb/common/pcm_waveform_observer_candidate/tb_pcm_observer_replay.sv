`timescale 1ns/1ps
module tb_pcm_observer_replay;
    parameter integer DEPTH=32;
    parameter [31:0] FIRST_SEQ=0;
    reg audio_clk=0,pixel_clk=0,audio_run=1,pixel_run=1;
    reg audio_rst_n=0,display_rst_n=0,frame_load=0;
    reg signed [23:0] play_left=0,play_right=0;
    always #12.5 if(audio_run) audio_clk=~audio_clk; else audio_clk=0;
    initial begin #7; forever begin #20; if(pixel_run)pixel_clk=~pixel_clk;else pixel_clk=0;end end
    integer fd, branch_epoch=0, audio_epoch=0;
    reg [31:0] ordinal=FIRST_SEQ;
    integer adopts=0, observations=0, outputs=0, restarts=0;
    wire seen_valid, enqueued, dropped, src_done, dst_done;
    wire [31:0] seen_seq, drop_count;
    wire signed [23:0] seen_left, seen_right;
    wire [15:0] level;
    wire wave_rst, restart, out_valid;
    wire [31:0] out_seq;
    wire signed [23:0] out_left, out_right;
    pcm_waveform_observer_bridge #(.DEPTH(DEPTH), .FIRST_SEQ(FIRST_SEQ)) dut (
        .audio_clk(audio_clk), .pixel_clk(pixel_clk),
        .audio_rst_n(audio_rst_n), .display_rst_n(display_rst_n),
        .audio_frame_load(frame_load), .audio_play_left(play_left),
        .audio_play_right(play_right), .waveform_rst_n(wave_rst),
        .stream_restart(restart), .sample_valid(out_valid),
        .sample_seq(out_seq), .sample_left(out_left), .sample_right(out_right),
        .observed_valid(seen_valid), .observed_seq(seen_seq),
        .observed_left(seen_left), .observed_right(seen_right),
        .observation_enqueued(enqueued), .observation_dropped(dropped),
        .observation_queue_level(level), .observation_drop_count(drop_count),
        .source_reset_done(src_done), .pixel_reset_done(dst_done)
    );
    always @(posedge audio_clk) if (fd && audio_rst_n) begin
        if (frame_load) begin
            $fdisplay(fd,"A %0t %0d %0d %0d %0d %0d",$time,
                branch_epoch,audio_epoch,ordinal,$signed(play_left),$signed(play_right));
            ordinal=ordinal+1; adopts=adopts+1;
        end
        if (seen_valid) begin
            $fdisplay(fd,"O %0t %0d %0d %0d %0d %0d %0d %0d",$time,
                branch_epoch,audio_epoch,seen_seq,$signed(seen_left),$signed(seen_right),enqueued,dropped);
            observations=observations+1;
        end
    end
    always @(posedge pixel_clk) if (fd) begin
        if (restart) begin
            $fdisplay(fd,"R %0t %0d %0d",$time,branch_epoch,audio_epoch);
            restarts=restarts+1;
        end
        if (out_valid) begin
            $fdisplay(fd,"D %0t %0d %0d %0d %0d %0d",$time,
                branch_epoch,audio_epoch,out_seq,$signed(out_left),$signed(out_right));
            outputs=outputs+1;
        end
        if (restart && out_valid) $fatal(1,"restart and valid overlap");
        if (!wave_rst && out_valid) $fatal(1,"valid during waveform reset");
    end
    task automatic reset_branch(input integer kind);
        begin
            branch_epoch=branch_epoch+1;
            if (kind==2) begin audio_epoch=audio_epoch+1; ordinal=FIRST_SEQ; audio_rst_n=0; end
            else display_rst_n=0;
            $fdisplay(fd,"Z %0t %0d %0d %0d",$time,branch_epoch,audio_epoch,kind);
            repeat(8) @(negedge audio_clk);
            if(kind==2) audio_rst_n=1; else display_rst_n=1;
        end
    endtask
    initial begin #300000000; $fatal(1,"HARNESS_TIMEOUT"); end

    integer vf,ret,index,count,left_value,right_value,cycles,record_index;
    string capture_path,vector_path;
    initial begin
        if(!$value$plusargs("CAPTURE=%s",capture_path) || !$value$plusargs("VECTORS=%s",vector_path)
           || !$value$plusargs("COUNT=%d",count)) $fatal(1,"missing arguments");
        fd=$fopen(capture_path,"w"); vf=$fopen(vector_path,"r");
        if(!fd || !vf || count<1) $fatal(1,"files/count");
        $fdisplay(fd,"META 1 replay %0d %0d %0d",DEPTH,FIRST_SEQ,count);
        $fdisplay(fd,"Z %0t 0 0 0",$time);
        repeat(8) @(negedge audio_clk);audio_rst_n=1;display_rst_n=1;
        repeat(20) @(negedge audio_clk);
        for(index=0;index<count;index=index+1) begin
            ret=$fscanf(vf,"%d %d %d %d\n",record_index,left_value,right_value,cycles);
            if(ret!=4 || record_index!=index || cycles<1) $fatal(1,"vector format");
            if(count>300 && index==100) begin pixel_run=0;$fdisplay(fd,"C %0t pixel_stop",$time);end
            if(count>300 && index==180) begin pixel_run=1;$fdisplay(fd,"C %0t pixel_resume",$time);end
            if(count>300 && index==count/3) reset_branch(1);
            if(count>300 && index==count/2) reset_branch(2);
            if(count>300 && index==count/4) begin
                audio_run=0;$fdisplay(fd,"C %0t audio_stop",$time);
                #7000;audio_run=1;$fdisplay(fd,"C %0t audio_resume",$time);
                @(negedge audio_clk);
            end
            $fdisplay(fd,"I %0t %0d %0d %0d %0d",$time,index,left_value,right_value,cycles);
            play_left=left_value;play_right=right_value;frame_load=1;
            @(negedge audio_clk);frame_load=0;
            repeat(cycles-1) @(negedge audio_clk);
        end
        $fclose(vf);pixel_run=1;
        repeat(2400) @(negedge audio_clk);
        $fdisplay(fd,"STAT %0t %0d %0d %0d",$time,branch_epoch,level,drop_count);
        $fdisplay(fd,"END %0d %0d %0d %0d",adopts,observations,outputs,restarts);
        $fclose(fd);fd=0;
        $display("HARNESS COMPLETE replay input=%0d",count);$finish;
    end
endmodule
