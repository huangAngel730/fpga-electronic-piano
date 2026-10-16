`timescale 1ns/1ps
// Simulation-only segmented raw observer. Never changes sampled RTL state.
module m3_r05_public_observer #(
    parameter TRACE_FILE="REAL_CAPTURE.jsonl"
)(
    input wire clk, rst_n, capture_enable, frame_tick, request_accept,
    input wire [31:0] request_id, committed_id,
    input wire commit_pulse,
    input wire signed [23:0] committed_left, committed_right,
    input wire committed_clip, pending_valid,
    input wire signed [23:0] play_left, play_right,
    input wire [31:0] clip_count, audio_underrun,
    input wire i2s_bclk, i2s_ws, i2s_din
);
    integer fd, startup_fd, boundary_fd;
    integer cycle=0, epoch=0, absolute_cycle=0, startup_edges=0;
    integer first_absolute_cycle=0;
    initial begin
        fd=$fopen(TRACE_FILE,"w");
        startup_fd=$fopen("STARTUP_CAPTURE.jsonl","w");
        if(fd==0 || startup_fd==0)$fatal(1,"R05_OBSERVER_FILE_OPEN");
        $fdisplay(fd,"{\"kind\":\"HEADER\",\"schema\":\"M3_R05_PUBLIC_PRE_NBA_V1\",\"clock_hz\":40000000,\"first_valid_observable\":false}");
        $fdisplay(startup_fd,"{\"kind\":\"HEADER\",\"schema\":\"M3_R05_STARTUP_PUBLIC_BINARY_V1\",\"clock_hz\":40000000}");
    end
    always @(negedge rst_n) if($time > 0) begin
        if(!capture_enable) begin
            $fdisplay(startup_fd,"{\"kind\":\"STARTUP_RESET\",\"absolute_cycle\":%0d,\"time_ps\":%0d,\"rst_n_binary\":\"%b\"}",absolute_cycle,longint'($realtime*1000.0),rst_n);
        end else if(cycle > 0) begin
            epoch=epoch+1;
            $fdisplay(fd,"{\"kind\":\"RESET\",\"epoch\":%0d,\"cycle\":%0d,\"time_ns\":%0d}",epoch,cycle,$time);
        end
    end
    always @(posedge clk) begin
        absolute_cycle=absolute_cycle+1;
        if(!capture_enable) begin
            startup_edges=startup_edges+1;
            $fdisplay(startup_fd,"{\"kind\":\"STARTUP_TICK\",\"absolute_cycle\":%0d,\"time_ps\":%0d,\"rst_n\":\"%b\",\"frame_tick\":\"%b\",\"request_accept\":\"%b\",\"request_id\":\"%b\",\"commit\":\"%b\",\"committed_id\":\"%b\",\"left\":\"%b\",\"right\":\"%b\",\"clipped\":\"%b\",\"pending\":\"%b\",\"play_left\":\"%b\",\"play_right\":\"%b\",\"clip_count\":\"%b\",\"underflow\":\"%b\",\"bclk\":\"%b\",\"ws\":\"%b\",\"din\":\"%b\"}",
                absolute_cycle,longint'($realtime*1000.0),rst_n,frame_tick,request_accept,request_id,commit_pulse,
                committed_id,committed_left,committed_right,committed_clip,pending_valid,
                play_left,play_right,clip_count,audio_underrun,i2s_bclk,i2s_ws,i2s_din);
        end else begin
            if ((^{rst_n,frame_tick,request_accept,request_id,commit_pulse,
                committed_id,committed_left,committed_right,committed_clip,pending_valid,
                play_left,play_right,clip_count,audio_underrun,i2s_bclk,i2s_ws,i2s_din}) === 1'bx)
                $fatal(1,"R05_OBSERVER_UNKNOWN_PUBLIC_PORT");
            if(cycle==0) begin
                if(rst_n!==0 || absolute_cycle>64)$fatal(1,"R05_STARTUP_SELECTION_INVALID");
                first_absolute_cycle=absolute_cycle;
                boundary_fd=$fopen("STARTUP_BOUNDARY_RAW.json","w");
                if(boundary_fd==0)$fatal(1,"R05_BOUNDARY_OPEN");
                $fdisplay(boundary_fd,"{\"startup_edges\":%0d,\"main_first_absolute_cycle\":%0d,\"main_first_relative_cycle\":1,\"main_first_time_ps\":%0d,\"main_first_time_ns\":%0d}",startup_edges,absolute_cycle,longint'($realtime*1000.0),$time);
                $fclose(boundary_fd);
            end
            cycle=cycle+1;
            $fdisplay(fd,"{\"kind\":\"TICK\",\"cycle\":%0d,\"epoch\":%0d,\"rst_n\":%0d,\"frame_tick\":%0d,\"request_accept\":%0d,\"request_id\":%0d,\"commit\":%0d,\"committed_id\":%0d,\"left\":%0d,\"right\":%0d,\"clipped\":%0d,\"pending\":%0d,\"play_left\":%0d,\"play_right\":%0d,\"clip_count\":%0d,\"underflow\":%0d,\"bclk\":%0d,\"ws\":%0d,\"din\":%0d,\"first_valid\":null}",
                cycle,epoch,rst_n,frame_tick,request_accept,request_id,commit_pulse,
                committed_id,committed_left,committed_right,committed_clip,pending_valid,
                play_left,play_right,clip_count,audio_underrun,i2s_bclk,i2s_ws,i2s_din);
        end
    end
    final begin
        $fdisplay(fd,"{\"kind\":\"END\",\"cycle\":%0d,\"epoch\":%0d}",cycle,epoch);
        $fdisplay(startup_fd,"{\"kind\":\"END\",\"absolute_edges\":%0d,\"main_first_absolute_cycle\":%0d}",startup_edges,first_absolute_cycle);
        $fclose(fd);
        $fclose(startup_fd);
    end
endmodule
