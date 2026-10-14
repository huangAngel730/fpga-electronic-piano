// C v4: real public inputs, public-port observers, PRE_NBA control timeline.
// Generate c_plan_v4.svh from the independently generated JSONL input plan.
`timescale 1ns/1ps
module tb_c_n32_r1_v4;
    localparam integer N=32, SW=5, TW=77;
    GSR GSR(.GSRI(1'b1));
    logic clk=0, rst_n=0, cancel=0, event_valid=0, sample_valid=0;
    logic result_ready=1, inject_valid=0, read_valid=0;
    always #12.5 clk=~clk;
    logic [63:0] event_data=0;
    logic [31:0] sample_id=0;
    logic [TW-1:0] inject_tag=0;
    logic [73:0] inject_context=0;
    logic [SW-1:0] read_slot=0;
    wire event_ready,sample_ready,result_valid,late,clipped,aborted,idle,fault;
    wire [1:0] abort_reason;
    wire [31:0] result_id;
    wire signed [23:0] left,right;
    wire inject_ready,read_ready,read_out_valid;
    wire [73:0] read_context;
    wire [N-1:0] ons,offs,occupied,releasing,frame_occupied;
    wire [N*10-1:0] velocities,frame_velocity;
    wire [N*32-1:0] bases,generations,frame_base,frame_gen;
    wire [N*8-1:0] notes;
    wire [N*4-1:0] sources,channels,frame_sources,frame_channels;
    wire issue_valid,issue_pedal,write_valid,write_accepted,write_injected,publish;
    wire [TW-1:0] issue_tag,write_tag;
    wire [73:0] issue_context,write_context;
    wire [1:0] issue_flags;
    wire [28:0] issue_control;
    wire be_launch,advance,lane_valid;
    wire [SW-1:0] lane_slot;
    wire [1:0] lane_table;
    wire [31:0] lane_phase,lane_fcw;
    wire signed [15:0] lane_wave;
    wire [15:0] lane_env;
    wire signed [23:0] lane_pcm;
    wire [N*16-1:0] live_env;
    wire [N*3-1:0] live_state;
    wire [N*12-1:0] frame_bend,frame_mod;
    wire [N*5-1:0] frame_range;
    wire [3:0] audio_state,router_state;
    wire control_snapshot_valid,control_snapshot_ready;
    wire [31:0] control_snapshot_id;
    wire [N*29-1:0] control_snapshot_value;
    wire [N-1:0] control_snapshot_occupied;
    wire [N*4-1:0] control_snapshot_sources,control_snapshot_channels;
    wire [N*32-1:0] control_snapshot_generations;
    wire control_release_valid,control_release_ready;
    wire [N-1:0] control_release_mask;
    wire [N*32-1:0] control_release_generations;
    wire backend_release_done_valid,backend_release_done_ready;
    wire [SW-1:0] backend_release_done_slot;
    wire [31:0] backend_release_done_generation;
    wire [N-1:0] backend_release_done_mask;
    b_n32_r1_wrapper #(.N(N),.RESPONSE(1)) dut(.*);

    integer cycle=0,op_index=-1,events=0,requests=0,launches=0,advances=0;
    integer lanes=0,outputs=0,cancels=0,aborts=0,writes=0,issues=0,reads=0,firsts=0;
    integer next_sample_cycle=0;
    integer command_index;
    reg [127:0] commands [0:20000];
    // Fixed packed buffers and static tasks avoid dynamic SV-string/task
    // lifetime cleanup paths in the frozen Windows Icarus target.
    reg [4095:0] plan_mem_path;
    logic [31:0] pending_id=0,retired_seen=0;
    logic [SW-1:0] accepted_read_slot=0;
    logic [N*119-1:0] previous_route='x;
    wire [N*119-1:0] route_tuple={ons,offs,occupied,releasing,velocities,bases,notes,sources,channels,generations};
    logic [106:0] previous_drive='x;
    wire [106:0] drive_tuple={rst_n,cancel,event_valid,event_data,sample_valid,sample_id,result_ready,read_valid,read_slot};
    logic [11:0] previous_state='x;
    wire [11:0] state_tuple={audio_state,router_state,idle,event_ready,sample_ready,read_ready};
    logic held=0,seen_result=0;
    logic [81:0] held_tuple;
    wire [81:0] result_tuple={result_id,left,right,late,clipped};

    always @(posedge clk) begin
        cycle=cycle+1;
        if(drive_tuple!==previous_drive) begin
            $display("D %0d %0d %0d %0d %h %0d %h %0d %0d %0d",cycle,rst_n,cancel,
                event_valid,event_data,sample_valid,sample_id,result_ready,read_valid,read_slot);
            previous_drive=drive_tuple;
        end
        if(rst_n) begin
            if(fault) $fatal(1,"C4_PUBLIC_FAULT");
            if(state_tuple!==previous_state) begin
                $display("AS %0d %0d %0d %0d %0d %0d %0d",cycle,audio_state,router_state,idle,
                    event_ready,sample_ready,read_ready);previous_state=state_tuple;
            end
            if(event_valid&&event_ready) begin events=events+1;$display("I %0d %h",cycle,event_data);end
            if(sample_valid&&sample_ready) begin
                requests=requests+1;pending_id=sample_id;$display("J %0d %h",cycle,sample_id);
            end
            if(route_tuple!==previous_route) begin
                $display("U %0d %h %h %h %h %h %h %h %h %h %h",cycle,
                    ons,offs,occupied,releasing,velocities,bases,notes,sources,channels,generations);
                previous_route=route_tuple;
            end
            if(issue_valid) begin issues=issues+1;
                $display("G %0d %h %h %h %h %0d",cycle,issue_tag,issue_context,issue_flags,issue_control,issue_pedal);end
            if(write_valid) begin writes=writes+1;
                $display("W %0d %h %h %0d %0d",cycle,write_tag,write_context,write_accepted,write_injected);end
            if(be_launch) begin launches=launches+1;
                $display("C %0d %h %h %h %h %h %h %h %h %h",cycle,pending_id,frame_occupied,
                    frame_base,frame_bend,frame_mod,frame_range,frame_sources,frame_channels,frame_gen);end
            if(advance) begin advances=advances+1;$display("A %0d %h",cycle,pending_id);end
            if(control_snapshot_valid&&control_snapshot_ready)
                $display("CS %0d %h %h %h %h %h %h",cycle,control_snapshot_id,
                    control_snapshot_occupied,control_snapshot_sources,control_snapshot_channels,
                    control_snapshot_generations,control_snapshot_value);
            if(control_release_valid&&control_release_ready)
                $display("CR %0d %h %h",cycle,control_release_mask,control_release_generations);
            if(backend_release_done_valid&&backend_release_done_ready) begin
                retired_seen=retired_seen | backend_release_done_mask;
                $display("RD %0d %0d %h %h",cycle,backend_release_done_slot,
                    backend_release_done_generation,backend_release_done_mask);
            end
            if(read_valid&&read_ready) begin
                accepted_read_slot=read_slot;$display("RQ %0d %0d",cycle,read_slot);end
            if(read_out_valid) $display("RY %0d %0d %h",cycle,accepted_read_slot,read_context);
            if(read_valid&&!read_ready) $display("RS %0d %0d %0d",cycle,read_slot,audio_state);
            if(cancel) begin cancels=cancels+1;$display("X %0d",cycle);end
            if(aborted) begin aborts=aborts+1;$display("Z %0d %0d",cycle,abort_reason);end
            if(held&&!cancel&&!aborted&&(!result_valid||result_tuple!==held_tuple))
                $fatal(1,"C4_HOLD_PAYLOAD_CHANGED");
            held=result_valid&&!result_ready&&!cancel&&!aborted;held_tuple=result_tuple;
            if(!result_valid) seen_result=0;
            if(result_valid&&!seen_result&&!cancel&&!aborted) begin
                seen_result=1;firsts=firsts+1;$display("F %0d %h %0d %0d %0d",cycle,result_id,left,right,late);end
            if(result_valid&&!cancel&&!aborted) $display("K %0d %h %0d %0d %0d %0d %0d",cycle,result_id,left,right,late,clipped,publish);
            if(publish) begin outputs=outputs+1;$display("P %0d %h %0d %0d %0d",cycle,result_id,left,right,late);end
            #1;
            if(lane_valid) begin lanes=lanes+1;
                $display("L %0d %h %0d %h %0d %h %0d %0d %0d %0d",cycle,pending_id,lane_slot,
                    lane_phase,lane_table,lane_fcw,lane_wave,lane_env,lane_pcm,live_state[3*lane_slot+:3]);end
            if(read_out_valid) begin reads=reads+1;$display("Y %0d %0d %h",cycle,accepted_read_slot,read_context);end
        end
    end

    task next_edge;
        @(negedge clk);
    endtask
    task begin_op(input integer index,input reg [255:0] kind);
        op_index=index;$display("OP %0d %0d BEGIN %0s",cycle,index,kind);
    endtask
    task end_op;
        $display("OP %0d %0d END",cycle,op_index);
    endtask
    task wait_idle;
        while(!idle || !event_ready) next_edge();
    endtask
    task reset_domain;
        $display("RA %0d %0d %0d",cycle,audio_state,router_state);
        rst_n=0;event_valid=0;sample_valid=0;cancel=0;read_valid=0;result_ready=1;
        repeat(4) next_edge();
        $display("R %0d",cycle);previous_route='x;previous_state='x;
        held=0;seen_result=0;retired_seen=0;next_sample_cycle=0;rst_n=1;
        next_edge();
    endtask
    task send_event(input logic [63:0] word_in);
        event_data=word_in;event_valid=1;
        begin : event_handshake
            logic accepted;
            accepted=0;
            while(!accepted) begin @(posedge clk);accepted=event_ready;#2;end
        end
        next_edge();event_valid=0;
        while(!event_ready || router_state!=0) next_edge();
    endtask
    task send_sample(input logic [31:0] id_in,input integer hold_cycles);
        while(cycle<next_sample_cycle) next_edge();
        sample_id=id_in;sample_valid=1;
        begin : sample_handshake
            logic accepted;
            accepted=0;
            while(!accepted) begin @(posedge clk);accepted=sample_ready;#2;end
        end
        // Inputs change on the preceding negedge; the accepting posedge is
        // one edge after this wait target, giving exactly 833 when unstalled.
        next_sample_cycle=cycle+832;
        next_edge();sample_valid=0;
        if(hold_cycles>0) begin
            while(!result_valid) next_edge();
            repeat(hold_cycles) next_edge();
        end
    endtask
    task read_bank(input integer slot);
        read_slot=SW'(slot);read_valid=1;
        begin : read_handshake
            logic accepted;
            accepted=0;
            while(!accepted) begin @(posedge clk);accepted=read_ready;#2;end
        end
        next_edge();read_valid=0;repeat(2) next_edge();
    endtask
    task read_stall(input integer slot,input integer edges);
        read_slot=SW'(slot);read_valid=1;
        repeat(edges) begin
            @(posedge clk);if(read_ready) $fatal(1,"C4_READ_STALL_NOT_OBSERVED");#2;next_edge();
        end
        read_valid=0;
    endtask
    task await_retirement(input integer slot);
        while(!retired_seen[slot] || occupied[slot] || releasing[slot] || !event_ready) next_edge();
        $display("RT %0d %0d %h %h",cycle,slot,occupied,releasing);
    endtask
    task load_commands(input integer count);
        if(!$value$plusargs("C4_PLAN_MEM=%s",plan_mem_path))
            $fatal(1,"C4_PLAN_MEM_PLUSARG_REQUIRED");
        if(count<1 || count>20001) $fatal(1,"C4_PLAN_MEMORY_COUNT");
        $readmemh(plan_mem_path,commands,0,count-1);
        for(integer index=0;index<count;index=index+1)
            if((^commands[index])===1'bx) $fatal(1,"C4_PLAN_MEMORY_UNKNOWN");
    endtask
    task run_command(input integer index);
        reg [127:0] command;
        integer opcode,delay;
        reg [255:0] kind;
        command=commands[index];opcode=command[127:120];delay=command[95:64];
        if(command[119:96]!=0) $fatal(1,"C4_PLAN_MEMORY_RESERVED");
        case(opcode)
            1:kind="note_on"; 2:kind="note_off"; 3:kind="cc64";
            4:kind="control_event"; 5:kind="sample"; 6:kind="read";
            7:kind="read_stall"; 8:kind="await_release_done";
            9:kind="set_result_ready"; 10:kind="reset";
            11:kind="cancel"; 12:kind="wait_idle"; 13:kind="tick";
            default:$fatal(1,"C4_PLAN_MEMORY_OPCODE");
        endcase
        begin_op(index,kind);
        case(opcode)
            1,2,3,4:send_event(command[63:0]);
            5:send_sample(command[31:0],delay);
            6:read_bank(command[4:0]);
            7:read_stall(command[4:0],delay);
            8:await_retirement(command[4:0]);
            9:begin result_ready=command[0];next_edge();end
            10:reset_domain();
            11:begin cancel=1;next_edge();cancel=0;end
            12:wait_idle();
            13:next_edge();
        endcase
        end_op();
    endtask
    initial begin
        $display("B2C 32 1 0");$display("C4 PUBLIC_PORTS PRE_NBA_INPUTS POST_NBA_LANES SAMPLE_INTERVAL_833");
        next_edge();
        `include "c_plan_v4.svh"
        wait_idle();repeat(4) next_edge();
        $display("END %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,
            events,requests,launches,advances,lanes,outputs,cancels,aborts,writes,issues,reads,firsts);
        $finish;
    end
    initial begin #200000000;$fatal(1,"C4_SIM_CYCLE_WATCHDOG");end
endmodule
