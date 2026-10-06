// Test-only subsystem wiring follows sealed L. No PLL/recovery or serial oracle.
// MIDI task is generated verbatim from the previously reviewed 40 MHz TB.
// golden() is generated from the existing renderer geometry reference.
`timescale 1ns/1ps
module tb_joint #(parameter bit OVERFLOW=0);
    import audio_defs_pkg::*;
    reg clk=0, pixel_clk=0, serial_clk=0, rst_n=0, midi_rx=1;
    always #12.5 clk=~clk;
    always #20 pixel_clk=~pixel_clk;
    always #4 serial_clk=~serial_clk;
    reg video_block=0;
    wire audio_gate=1'b1; // only the negative implementation changes this
    wire midi_valid,midi_ready,event_valid,core_ready,button_ready;
    wire ref_midi_valid,ref_midi_ready,ref_valid,ref_ready,ref_button_ready;
    performance_event_t midi_data,event_data,ref_midi_data,ref_data;
    wire [15:0] fifo_level,fifo_high,local_level,local_high,ref_level,ref_high;
    wire [31:0] uart_errors,parser_errors,overflow,voices,clip,underrun,
                frames,requests,commits,latency,ref_voices,ref_clip,ref_under,
                ref_frames,ref_requests,ref_commits,ref_latency;
    wire signed [23:0] play_left,play_right,ref_left,ref_right;
    wire pending,ref_pending,bclk,ws,din,ready,frame_tick;
    wire ref_bclk,ref_ws,ref_din,ref_i2s_ready,ref_tick;
    midi_input #(.CLK_HZ(40_000_000)) u_midi(
        .clk,.rst_n,.midi_rx_async(midi_rx),.event_ready(midi_ready),
        .event_valid(midi_valid),.event_data(midi_data),
        .event_fifo_level(local_level),.event_fifo_high_watermark(local_high),
        .uart_frame_error_count(uart_errors),.parser_error_count(parser_errors),
        .event_fifo_overflow_count(overflow),.midi_rx_busy());
    performance_event_fifo #(.DEPTH(32)) u_fifo(
        .clk,.rst_n,.button_valid(1'b0),.button_ready,.button_data(64'd0),
        .midi_valid,.midi_ready,.midi_data,.event_valid,
        .event_ready(core_ready && audio_gate),.event_data,
        .event_fifo_level(fifo_level),.event_fifo_high_watermark(fifo_high));
    polyphonic_audio_core u_core(
        .clk,.rst_n,.event_valid(event_valid && audio_gate),.event_ready(core_ready),
        .event_data,.frame_tick,.play_left,.play_right,.pending_valid(pending),
        .active_voice_count(voices),.clip_count(clip),.audio_underrun(underrun),
        .audio_frame_count(frames),.pcm_request_count(requests),
        .pcm_commit_count(commits),.max_processing_cycles(latency));
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) u_tx(
        .clk,.rst_n,.valid(1'b1),.pcm_left(play_left),.pcm_right(play_right),
        .bclk,.lrck(ws),.din,.ready,.frame_tick);
    // Independent audio-only path: same real UART, not the visual ready signal.
    midi_input #(.CLK_HZ(40_000_000)) u_ref_midi(
        .clk,.rst_n,.midi_rx_async(midi_rx),.event_ready(ref_midi_ready),
        .event_valid(ref_midi_valid),.event_data(ref_midi_data),
        .event_fifo_level(),.event_fifo_high_watermark(),.uart_frame_error_count(),
        .parser_error_count(),.event_fifo_overflow_count(),.midi_rx_busy());
    performance_event_fifo #(.DEPTH(32)) u_ref_fifo(
        .clk,.rst_n,.button_valid(1'b0),.button_ready(ref_button_ready),.button_data(64'd0),
        .midi_valid(ref_midi_valid),.midi_ready(ref_midi_ready),.midi_data(ref_midi_data),
        .event_valid(ref_valid),.event_ready(ref_ready),.event_data(ref_data),
        .event_fifo_level(ref_level),.event_fifo_high_watermark(ref_high));
    polyphonic_audio_core u_ref_core(
        .clk,.rst_n,.event_valid(ref_valid),.event_ready(ref_ready),.event_data(ref_data),
        .frame_tick(ref_tick),.play_left(ref_left),.play_right(ref_right),.pending_valid(ref_pending),
        .active_voice_count(ref_voices),.clip_count(ref_clip),.audio_underrun(ref_under),
        .audio_frame_count(ref_frames),.pcm_request_count(ref_requests),
        .pcm_commit_count(ref_commits),.max_processing_cycles(ref_latency));
    i2s_tx #(.BCLK_PHASE_STEP(32'd659706977)) u_ref_tx(
        .clk,.rst_n,.valid(1'b1),.pcm_left(ref_left),.pcm_right(ref_right),
        .bclk(ref_bclk),.lrck(ref_ws),.din(ref_din),.ready(ref_i2s_ready),.frame_tick(ref_tick));
    wire sys_done,video_done,video_valid,video_desync,scene_ready;
    wire [15:0] queue_level,queue_peak,x,y;
    wire [31:0] drop_count;
    wire drop_pulse,de,hs,vs,frame_start,line_start,display_mode;
    wire [31:0] current_frame;
    wire [23:0] rgb;
    performance_event_t video_data,scene_data;
    assign scene_data=video_data; // negative implementation maps an actual pitch incorrectly
    visual_event_bridge #(.DEPTH(32)) u_bridge(
        .sys_clk(clk),.video_clk(pixel_clk),.rst_n,
        .accepted_valid(event_valid && core_ready && audio_gate),.accepted_data(event_data),
        .visual_queue_level(queue_level),.visual_queue_high_watermark(queue_peak),
        .visual_drop_count(drop_count),.visual_drop_pulse(drop_pulse),
        .sys_reset_done(sys_done),.video_reset_done(video_done),
        .video_valid,.video_desync,.video_ready(scene_ready && !video_block),.video_data);
    video_scan_timing u_scan(.pixel_clk,.rst_n(video_done),.pixel_x(x),.pixel_y(y),
        .data_enable(de),.hsync(hs),.vsync(vs),.frame_start,.line_start);
    m3_visualizer u_scene(
        .pixel_clk,.video_rst_n(video_done),.pixel_x(x),.pixel_y(y),.data_enable(de),
        .frame_start,.event_valid(video_valid && !video_block),.event_data(scene_data),
        .event_ready(scene_ready),.video_desync,.mode_toggle_pulse(1'b0),
        .score_valid(1'b0),.score_ready(),.score_note_id(16'd0),.score_note_number(7'd0),
        .score_hit_frame(32'd0),.score_duration_valid(1'b0),.score_duration_frames(32'd0),
        .score_velocity(10'd0),.display_mode,.current_frame,
        .rgb_r(rgb[23:16]),.rgb_g(rgb[15:8]),.rgb_b(rgb[7:0]));
    // Explicit RGB/sync boundary stub. No TMDS encoding/display recognition.
    wire [23:0] boundary_rgb;
    wire boundary_de,boundary_hs,boundary_vs;
    dvi_boundary_stub u_boundary(.pixel_clk,.rst_n(video_done),.rgb,.de,.hs,.vs,
        .sample_rgb(boundary_rgb),.sample_de(boundary_de),.sample_hs(boundary_hs),.sample_vs(boundary_vs));
    integer fd,frame_no=0,pixels=0,active=0,hs_low=0,vs_low=0,rgb_checks=0,rgb_errors=0;
    integer row_pixels=0,row_active=0,row_hs=0,row_checks=0;
    reg [31:0] row_hash=32'h811c9dc5;
    integer start_pcm=0,start_under=0,pcm_seen=0;
    realtime last_core=0,last_pixel=0;
    // Aliases for the unchanged integer-geometry reference function.
    localparam W=640,H=480,N=49,BASE=36;
    wire mode=display_mode,desync=u_scene.live_desync_latched;
    wire [7:0] lv=u_scene.live_valid,sv=u_scene.score_slot_valid,
               hit=u_scene.score_slot_hit,miss=u_scene.score_slot_miss;
    wire [55:0] ln=u_scene.live_note_number,sn=u_scene.score_slot_note_number;
    wire [79:0] ly=u_scene.live_y,le=u_scene.live_end_y,
                st=u_scene.score_top_y,se=u_scene.score_end_y,
                lvel=u_scene.live_velocity,svel=u_scene.score_slot_velocity;
    `include "renderer_golden.svh"
    `include "midi_tasks.svh"
    task automatic message(input reg [7:0] status,data1,data2);
        byte_midi(status);byte_midi(data1);byte_midi(data2);
    endtask
    task automatic block_video(input integer duration_ns);
        // Change the test-only ready gate away from the consuming edge.
        // The first diagnostic run intentionally remains archived in runtime:
        // a posedge release had an observer/DUT scheduling race, not a visual fix.
        @(negedge pixel_clk);
        video_block=1;
        $fdisplay(fd,"B %.3f 1 %0d",$realtime,duration_ns);
        #(duration_ns);
        video_block=0;
        $fdisplay(fd,"B %.3f 0 %0d",$realtime,duration_ns);
    endtask
    initial begin
        fd=$fopen("capture.txt","w");if(!fd)$fatal(1,"CAPTURE_OPEN");
        repeat(10)@(negedge clk);rst_n=1;
        wait(frame_no==2);#1000000;
        if(!OVERFLOW)begin
            message(8'h90,60,100);message(8'h90,64,80);
            wait(frame_no==4);#500000;
            fork
                block_video(4000000);
                begin
                    message(8'h90,67,90);message(8'h80,67,0);
                    message(8'hb0,64,127);message(8'h80,60,0);
                end
            join
        end else begin
            fork
                block_video(36000000);
                begin
                    for(integer n=0;n<36;n=n+1)
                        message((n%2==0)?8'h90:8'h80,72,(n%2==0)?8'd100:8'd0);
                end
            join
        end
        wait(frame_no==7);#100;
        if(uart_errors || parser_errors || overflow || fifo_level || local_level)
            $fatal(1,"INPUT_ERRORS");
        $fdisplay(fd,"END %0d %0d %0d %0d %0d",OVERFLOW,commits,underrun,drop_count,queue_peak);
        $fclose(fd);$display("SIM_DONE joint overflow=%0d",OVERFLOW);$finish;
    end
    always @(posedge clk)if(rst_n)begin
        if(last_core!=0 && $realtime-last_core!=25)$fatal(1,"SYSTEM_RATE");
        last_core=$realtime;
        if(event_valid && core_ready && audio_gate)begin
            // Log actual bridge decision after the accepting edge, not a fabricated event.
            $fdisplay(fd,"A %.3f %016h %0d %0d",$realtime,event_data,queue_level,drop_count);
        end
        if(ref_valid && ref_ready)$fdisplay(fd,"R %.3f %016h",$realtime,ref_data);
        if((u_core.u_commit.pcm_valid && u_core.u_commit.pcm_ready) ||
           (u_ref_core.u_commit.pcm_valid && u_ref_core.u_commit.pcm_ready))begin
            pcm_seen=pcm_seen+1;
            $fdisplay(fd,"P %.3f %0d %0d %0d %0d %0d %0d %0d %0d",
                $realtime,u_core.u_commit.pcm_valid && u_core.u_commit.pcm_ready,
                u_ref_core.u_commit.pcm_valid && u_ref_core.u_commit.pcm_ready,
                u_core.u_commit.pcm_req_id,$signed(u_core.u_commit.pcm_left),$signed(u_core.u_commit.pcm_right),
                u_ref_core.u_commit.pcm_req_id,$signed(u_ref_core.u_commit.pcm_left),$signed(u_ref_core.u_commit.pcm_right));
        end
        if(drop_pulse)$fdisplay(fd,"D %.3f %0d %0d",$realtime,drop_count,queue_level);
    end
    always @(posedge pixel_clk)if(video_done)begin
        if(last_pixel!=0 && $realtime-last_pixel!=40)$fatal(1,"PIXEL_RATE");
        last_pixel=$realtime;
        if(video_valid && scene_ready && !video_block)
            $fdisplay(fd,"V %.3f %016h",$realtime,scene_data);
        if(frame_start)begin
            if(frame_no>0)$fdisplay(fd,"C %.3f %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                $realtime,frame_no,pixels,active,hs_low,vs_low,rgb_checks,rgb_errors,
                start_pcm,commits,start_under,underrun);
            frame_no=frame_no+1;pixels=0;active=0;hs_low=0;vs_low=0;rgb_checks=0;rgb_errors=0;
            start_pcm=commits;start_under=underrun;
        end
        if(frame_no>0)begin
            pixels=pixels+1;active=active+de;hs_low=hs_low+!hs;vs_low=vs_low+!vs;
            row_pixels=row_pixels+1;row_active=row_active+de;row_hs=row_hs+!hs;
            rgb_checks=rgb_checks+1;row_checks=row_checks+1;
            if(rgb !== golden())begin
                rgb_errors=rgb_errors+1;
                if(rgb_errors<4)$fdisplay(fd,"X %.3f %0d %0d %0d %06h %06h",$realtime,frame_no,x,y,rgb,golden());
            end
            row_hash=(row_hash ^ {8'd0,rgb})*32'd16777619;
            if(x==799)begin
                $fdisplay(fd,"L %.3f %0d %0d %0d %0d %0d %08h %0d",$realtime,
                    frame_no,y,row_pixels,row_active,row_hs,row_hash,row_checks);
                row_pixels=0;row_active=0;row_hs=0;row_checks=0;row_hash=32'h811c9dc5;
            end
        end
    end
    always @(posedge pixel_clk)if(video_done && frame_start)begin
        #1;
        $fdisplay(fd,"F %.3f %0d %02h %02h %014h %020h %020h %020h %032h %0d %0d %0d",
            $realtime,frame_no,lv,u_scene.live_held,ln,ly,le,lvel,u_scene.key_down,desync,mode,current_frame);
    end
    initial begin #120000000;$fatal(1,"JOINT_TIMEOUT");end
endmodule

// Deliberately no TMDS outputs: record the same RGB/sync boundary as a DVI input.
module dvi_boundary_stub(input pixel_clk,rst_n,input [23:0] rgb,input de,hs,vs,
    output reg [23:0] sample_rgb,output reg sample_de,sample_hs,sample_vs);
    always @(posedge pixel_clk or negedge rst_n)
        if(!rst_n)begin sample_rgb<=0;sample_de<=0;sample_hs<=1;sample_vs<=1;end
        else begin sample_rgb<=rgb;sample_de<=de;sample_hs<=hs;sample_vs<=vs;end
endmodule
