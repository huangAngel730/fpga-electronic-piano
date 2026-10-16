`timescale 1ns/1ps
// New isolated observer ONLY. All observed signals are public frame-core ports.
// No binding to production/old TB, no algorithm, no hierarchical internal reads.
// rst_n asserts asynchronously; all TICK rows are sampled pre-NBA at posedge.
module m3_r05_public_observer #(
    parameter TRACE_FILE = "r05_public.jsonl"
)(
    input wire clk, rst_n, frame_tick, request_accept,
    input wire [31:0] request_id, committed_id,
    input wire commit_pulse,
    input wire signed [23:0] committed_left, committed_right,
    input wire committed_clip, pending_valid,
    input wire signed [23:0] play_left, play_right,
    input wire [31:0] clip_count, audio_underrun,
    input wire i2s_bclk, i2s_ws, i2s_din
);
    integer fd, cycle=0, epoch=0;
    initial begin
        fd=$fopen(TRACE_FILE,"w");
        if(fd==0)$fatal(1,"R05_OBSERVER_FILE_OPEN");
        $fdisplay(fd,"{\"kind\":\"HEADER\",\"schema\":\"M3_R05_PUBLIC_PRE_NBA_V1\",\"clock_hz\":40000000,\"first_valid_observable\":false}");
    end
    always @(negedge rst_n) if ($time > 0) begin
        epoch=epoch+1;
        $fdisplay(fd,"{\"kind\":\"RESET\",\"epoch\":%0d,\"cycle\":%0d,\"time_ns\":%0d}",epoch,cycle,$time);
    end
    always @(posedge clk) begin
        cycle=cycle+1;
        if ((^{rst_n,frame_tick,request_accept,request_id,commit_pulse,
            committed_id,committed_left,committed_right,committed_clip,pending_valid,
            play_left,play_right,clip_count,audio_underrun,i2s_bclk,i2s_ws,i2s_din}) === 1'bx)
            $fatal(1,"R05_OBSERVER_UNKNOWN_PUBLIC_PORT");
        // No fabricated accept/first-valid/cancel-handshake. frame_tick is
        // the frame fence. The core exposes neither first-valid nor ready.
        $fdisplay(fd,"{\"kind\":\"TICK\",\"cycle\":%0d,\"epoch\":%0d,\"rst_n\":%0d,\"frame_tick\":%0d,\"request_accept\":%0d,\"request_id\":%0d,\"commit\":%0d,\"committed_id\":%0d,\"left\":%0d,\"right\":%0d,\"clipped\":%0d,\"pending\":%0d,\"play_left\":%0d,\"play_right\":%0d,\"clip_count\":%0d,\"underflow\":%0d,\"bclk\":%0d,\"ws\":%0d,\"din\":%0d,\"first_valid\":null}",
            cycle,epoch,rst_n,frame_tick,request_accept,request_id,commit_pulse,
            committed_id,committed_left,committed_right,committed_clip,pending_valid,
            play_left,play_right,clip_count,audio_underrun,i2s_bclk,i2s_ws,i2s_din);
    end
    final begin
        $fdisplay(fd,"{\"kind\":\"END\",\"cycle\":%0d,\"epoch\":%0d}",cycle,epoch);
        $fclose(fd);
    end
endmodule
