`timescale 1ns/1ps
module tb_r08_control_forwarding;
    import audio_defs_pkg::*;
    logic clk=0,rst_n=0,event_valid=0,request_valid=0;
    always #5 clk=~clk;
    performance_event_t payload='0;
    wire event_ready,request_ready,snapshot_valid;
    wire [31:0] snapshot_id;
    wire [47:0] bends,mods;
    wire [19:0] ranges;
    m2_polyphony_control_snapshot #(.N(4)) dut(
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),.event_data(payload),
        .request_valid(request_valid),.request_ready(request_ready),.request_id(32'd19),
        .slot_occupied(4'b1011),.slot_source_ids(16'h1020),.slot_channels(16'h3033),
        .slot_generations(128'd0),.snapshot_valid(snapshot_valid),.snapshot_ready(1'b1),
        .snapshot_id(snapshot_id),.snapshot_occupied(),.snapshot_sources(),.snapshot_channels(),
        .snapshot_generations(),.snapshot_pitch_bend(bends),.snapshot_modulation(mods),
        .snapshot_pitch_range(ranges),.control_applied(),.invalid_range());
    task automatic send(input [2:0] kind,input [7:0] id,cc,input [11:0] value,input bit request=0);
        @(negedge clk);
        if(!event_ready || (request && !request_ready)) $fatal(1,"control handshake not ready");
        payload.event_type=kind;{payload.source_id,payload.channel}=id;
        payload.control_id=cc;payload.control_value=value;
        event_valid=1;request_valid=request;
    endtask
    initial begin
        repeat(4) @(negedge clk);
        rst_n=1;
        send(EVENT_PITCH_BEND,8'h03,CTRL_PITCH_BEND,12'd147);
        send(EVENT_CONTROL_CHANGE,8'h03,CTRL_MODULATION,12'd713);
        send(EVENT_CONTROL_CHANGE,8'h23,CTRL_PITCH_RANGE,12'd24);
        send(EVENT_CONTROL_CHANGE,8'h03,CTRL_PITCH_RANGE,12'd31); // ignore invalid
        send(EVENT_CONTROL_CHANGE,8'h03,CTRL_PITCH_RANGE,12'd12,1);
        @(negedge clk);event_valid=0;request_valid=0;
        wait(snapshot_valid); #1;
        if(snapshot_id!==19 || bends!=={12'd0,12'd0,12'd0,12'd147} ||
           mods!=={12'd0,12'd0,12'd0,12'd713} ||
           ranges!=={5'd2,5'd2,5'd24,5'd12})
            $fatal(1,"forwarding mismatch %h %h %h",bends,mods,ranges);
        $display("PASS R08_CONTROL_FORWARDING");
        $finish;
    end
    initial begin #5000; $fatal(1,"timeout"); end
endmodule
