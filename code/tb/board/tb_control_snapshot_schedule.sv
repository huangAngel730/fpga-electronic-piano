// M2 sequential candidate + actual M3 parser at50MHz control scheduling.
// Audio requests use1041/1042 system-cycle cadence. This is not audio/FCW.
`timescale 1ns/1ps
module tb_control_snapshot_schedule;
    import audio_defs_pkg::*;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,midi_byte_valid=0;
    logic [7:0] midi_byte=0;
    wire event_valid,event_ready;
    performance_event_t event_data;
    wire [15:0] fifo_level,fifo_peak;
    wire [31:0] parser_errors,overflows;
    midi_event_parser #(.SOURCE_ID(5),.CLK_HZ(50000000)) parser(
        .clk(clk),.rst_n(rst_n),.midi_byte(midi_byte),.midi_byte_valid(midi_byte_valid),
        .midi_byte_error(1'b0),.event_valid(event_valid),.event_ready(event_ready),.event_data(event_data),
        .event_fifo_level(fifo_level),.event_fifo_high_watermark(fifo_peak),
        .event_fifo_overflow_count(overflows),.parser_error_count(parser_errors));
    logic request_valid=0,snapshot_ready=0;
    logic [31:0] request_id=0;
    logic [3:0] slot_occupied=15;
    logic [15:0] slot_source_ids=16'h5655,slot_channels=16'h2232;
    logic [127:0] slot_generations=128'h40000000030000000200000001000000;
    wire request_ready,snapshot_valid,control_applied,invalid_range;
    wire [31:0] snapshot_id;
    wire [3:0] snapshot_occupied;
    wire [15:0] snapshot_sources,snapshot_channels;
    wire [127:0] snapshot_generations;
    wire [47:0] snapshot_pitch_bend,snapshot_modulation;
    wire [19:0] snapshot_pitch_range;
    performance_control_snapshot dut(.*);
    wire ref_valid,ref_applied,ref_invalid;
    wire [31:0] ref_id;
    wire [3:0] ref_occupied;
    wire [15:0] ref_sources,ref_channels;
    wire [127:0] ref_generations;
    wire [47:0] ref_pitch,ref_mod;
    wire [19:0] ref_range;
    performance_control_state original(
        .clk(clk),.rst_n(rst_n),.accepted_valid(event_valid&&event_ready),.accepted_data(event_data),
        .slot_occupied(slot_occupied),.slot_source_ids(slot_source_ids),.slot_channels(slot_channels),
        .slot_generations(slot_generations),.sample_capture(request_valid&&request_ready),.sample_id(request_id),
        .slot_pitch_bend(),.slot_modulation(),.slot_pitch_range(),.snapshot_valid(ref_valid),
        .snapshot_id(ref_id),.snapshot_occupied(ref_occupied),.snapshot_sources(ref_sources),.snapshot_channels(ref_channels),
        .snapshot_generations(ref_generations),.snapshot_pitch_bend(ref_pitch),.snapshot_modulation(ref_mod),
        .snapshot_pitch_range(ref_range),.control_applied(ref_applied),.invalid_range(ref_invalid));
    wire [311:0] payload={snapshot_id,snapshot_occupied,snapshot_sources,snapshot_channels,
                         snapshot_generations,snapshot_pitch_bend,snapshot_modulation,snapshot_pitch_range};
    wire [311:0] expected={ref_id,ref_occupied,ref_sources,ref_channels,ref_generations,ref_pitch,ref_mod,ref_range};
    integer frame_counter=0,period=1041,cycles=0,checks=0,requests=0,consumed=0,controls=0,notes=0;
    integer accepted_cycle=0,ack_cycle=0,max_valid_latency=0,max_consume_latency=0,low_ready_run=0,max_low_ready=0;
    logic calculating=0,hold_valid=0;
    logic [311:0] hold_payload;
    logic prior_blocked=0;
    performance_event_t blocked_data;
    task automatic check(input logic ok,input string message);
        checks++;if(ok!==1'b1)$fatal(1,"Snapshot schedule %s cycle=%0d id=%0d",message,cycles,snapshot_id);
    endtask
    always @(negedge clk)begin
        if(!rst_n)begin request_valid=0;request_id=0;frame_counter=0;period=1041;snapshot_ready=0;end
        else begin
            request_valid=frame_counter==period-1;
            if(request_valid)begin
                check(request_ready,"snapshot preparation leaves next48kHz request ready");
                request_id++;frame_counter=0;period=period==1041 ? 1042 : 1041;
            end else frame_counter++;
            snapshot_ready=snapshot_valid && cycles>=ack_cycle;
        end
    end
    always @(posedge clk)begin
        cycles++;
        if(!rst_n)begin calculating=0;hold_valid=0;prior_blocked=0;low_ready_run=0;end
        else begin
            if(prior_blocked)check(event_valid && event_data===blocked_data,"M3 presented event stable during4-cycle backpressure");
            prior_blocked=event_valid&&!event_ready;blocked_data=event_data;
            if(!event_ready)begin low_ready_run++;if(low_ready_run>max_low_ready)max_low_ready=low_ready_run;end
            else low_ready_run=0;
            if(event_valid&&event_ready)begin
                if(event_data.event_type==EVENT_PITCH_BEND ||
                   (event_data.event_type==EVENT_CONTROL_CHANGE && event_data.control_id==CTRL_MODULATION))controls++;
                else notes++;
            end
            if(request_valid&&request_ready)begin
                check(!calculating && !snapshot_valid,"all previous snapshot work finished before next request");
                requests++;accepted_cycle=cycles;calculating=1;ack_cycle=cycles+12;
            end
            if(hold_valid)check(snapshot_valid && payload===hold_payload,"result hold while model algorithm delays ready");
            hold_valid=snapshot_valid&&!snapshot_ready;hold_payload=payload;
            if(snapshot_valid&&snapshot_ready)begin
                consumed++;if(cycles-accepted_cycle>max_consume_latency)max_consume_latency=cycles-accepted_cycle;
            end
        end
        #1;
        check(control_applied===ref_applied && invalid_range===ref_invalid,"accepted control semantics unchanged");
        if(snapshot_valid)check(ref_valid && payload===expected,"sample-wide payload matches original at request");
        if(calculating && snapshot_valid)begin
            check(cycles-accepted_cycle==4,"exact4 clocks of preparation at real sample cadence");
            if(cycles-accepted_cycle>max_valid_latency)max_valid_latency=cycles-accepted_cycle;
            calculating=0;
        end
    end
    task automatic byte_in(input logic [7:0] value);
        @(negedge clk);midi_byte=value;midi_byte_valid=1;
        @(negedge clk);midi_byte_valid=0;repeat(2)@(negedge clk);
    endtask
    task automatic message(input logic [7:0] status,a,b);
        byte_in(status);byte_in(a);byte_in(b);
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        message(8'he2,127,127);message(8'he2,0,0);
        message(8'hb2,1,127);message(8'he3,0,64);message(8'hb3,1,64);
        message(8'h92,60,100);message(8'hb2,64,127);message(8'h82,60,0);
        repeat(210000)@(negedge clk);
        check(controls>=4 && notes==3,"real continuous/discrete output exercised");
        check(consumed>190 && requests==consumed,"no missed48kHz requests/results");
        check(max_valid_latency==4 && max_consume_latency<=14,"bounded preparation and explicit consumer wait");
        check(max_low_ready==4,"control backpressure exactly4 sysclk cycles");
        check(fifo_level==0 && overflows==0 && parser_errors==0,"clean input queue after throttle");
        // Rebind a physical voice slot without changing the stored source state.
        @(negedge clk);slot_source_ids[3:0]=6;slot_generations[31:0]=32'd99;
        repeat(1100)@(negedge clk);
        check(snapshot_sources[3:0]==6 && snapshot_generations[31:0]==99 && snapshot_pitch_bend[11:0]==0 && snapshot_modulation[11:0]==0,"slot steal/rebind neutral source observed");
        rst_n=0;#1;check(!snapshot_valid && !request_ready && !event_ready,"reset flushes pending/held snapshot");
        repeat(4)@(negedge clk);rst_n=1;repeat(1500)@(negedge clk);
        check(snapshot_pitch_bend==0 && snapshot_modulation==0 && snapshot_pitch_range=={4{5'd2}},"no old control after reset");
        $display("PASS control_snapshot_schedule checks=%0d requests=%0d consumed=%0d controls=%0d discrete=%0d valid_latency=%0d consume_latency=%0d event_stall=%0d",checks,requests,consumed,controls,notes,max_valid_latency,max_consume_latency,max_low_ready);
        $finish;
    end
    initial begin #10000000;$fatal(1,"Snapshot real-rate schedule timeout");end
endmodule
