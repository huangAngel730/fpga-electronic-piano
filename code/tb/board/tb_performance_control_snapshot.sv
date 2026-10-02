// M2 transaction-oracle and original parallel-bank comparison.
// Never change original RTL or force a control state. Every accepted request
// must publish exactly E+4; valid payload stays immutable until handshake.
`timescale 1ns/1ps
module tb_performance_control_snapshot;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,event_valid=0,request_valid=0,snapshot_ready=0;
    logic [63:0] event_data=0;
    logic [31:0] request_id=0;
    logic [3:0] slot_occupied=0;
    logic [15:0] slot_source_ids=0,slot_channels=0;
    logic [127:0] slot_generations=0;
    wire event_ready,request_ready,snapshot_valid,control_applied,invalid_range;
    wire [31:0] snapshot_id;
    wire [3:0] snapshot_occupied;
    wire [15:0] snapshot_sources,snapshot_channels;
    wire [127:0] snapshot_generations;
    wire [47:0] snapshot_pitch_bend,snapshot_modulation;
    wire [19:0] snapshot_pitch_range;
    performance_control_snapshot dut(.*);
    wire [47:0] ref_pitch,ref_mod;
    wire [19:0] ref_range;
    wire ref_valid,ref_applied,ref_invalid;
    wire [31:0] ref_id;
    wire [3:0] ref_occupied;
    wire [15:0] ref_sources,ref_channels;
    wire [127:0] ref_generations;
    performance_control_state reference_bank(
        .clk(clk),.rst_n(rst_n),.accepted_valid(event_valid&&event_ready),.accepted_data(event_data),
        .slot_occupied(slot_occupied),.slot_source_ids(slot_source_ids),.slot_channels(slot_channels),
        .slot_generations(slot_generations),.sample_capture(request_valid&&request_ready),.sample_id(request_id),
        .slot_pitch_bend(),.slot_modulation(),.slot_pitch_range(),.snapshot_valid(ref_valid),
        .snapshot_id(ref_id),.snapshot_occupied(ref_occupied),.snapshot_sources(ref_sources),
        .snapshot_channels(ref_channels),.snapshot_generations(ref_generations),
        .snapshot_pitch_bend(ref_pitch),.snapshot_modulation(ref_mod),.snapshot_pitch_range(ref_range),
        .control_applied(ref_applied),.invalid_range(ref_invalid));
    wire [311:0] payload={snapshot_id,snapshot_occupied,snapshot_sources,snapshot_channels,
        snapshot_generations,snapshot_pitch_bend,snapshot_modulation,snapshot_pitch_range};
    wire [311:0] ref_payload={ref_id,ref_occupied,ref_sources,ref_channels,ref_generations,ref_pitch,ref_mod,ref_range};
    integer fd,n,count=0,checks=0,requests=0,results=0,accepted_controls=0;
    integer outstanding_age=0;
    logic outstanding=0,held_last=0;
    logic [311:0] held_payload=0;
    string vectors;
    logic v_reset,v_event,v_request,v_ready;
    logic [63:0] v_data;
    logic [31:0] v_id;
    logic [3:0] v_occupied;
    logic [15:0] v_sources,v_channels;
    logic [127:0] v_generations;
    logic e_event_ready,e_request_ready,e_valid,e_applied,e_invalid;
    logic [311:0] e_payload;
    task automatic check(input logic ok,input string name);
        checks++;if(ok!==1'b1)$fatal(1,"Serialized controls vector=%0d %s",count,name);
    endtask
    initial begin
        if(!$value$plusargs("VECTORS=%s",vectors))$fatal(1,"VECTORS missing");
        fd=$fopen(vectors,"r");if(!fd)$fatal(1,"Cannot open vectors");
        while(!$feof(fd))begin
            n=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                v_reset,v_event,v_data,v_request,v_id,v_occupied,v_sources,v_channels,v_generations,v_ready,
                e_event_ready,e_request_ready,e_valid,e_payload,e_applied,e_invalid);
            if(n==-1)break;if(n!=16)$fatal(1,"Bad vector fields=%0d",n);
            @(negedge clk);rst_n=v_reset;event_valid=v_event;event_data=v_data;
            request_valid=v_request;request_id=v_id;slot_occupied=v_occupied;
            slot_source_ids=v_sources;slot_channels=v_channels;slot_generations=v_generations;snapshot_ready=v_ready;
            @(posedge clk);
            if(!rst_n)begin outstanding=0;outstanding_age=0;held_last=0;end
            else begin
                if(outstanding)outstanding_age++;
                if(request_valid&&request_ready)begin
                    check(!outstanding,"no second concurrent request");outstanding=1;outstanding_age=0;requests++;
                end
                if(snapshot_valid&&snapshot_ready)results++;
                if(held_last)check(snapshot_valid && payload===held_payload,"backpressured payload never changes before ACK");
                held_last=snapshot_valid&&!snapshot_ready;held_payload=payload;
                if(event_valid&&event_ready)accepted_controls++;
            end
            #1;count++;
            check(event_ready===e_event_ready && request_ready===e_request_ready,"ready/busy protocol");
            check(snapshot_valid===e_valid,"valid schedule");
            check(control_applied===e_applied && invalid_range===e_invalid,"accepted update/reject pulses");
            check(control_applied===ref_applied && invalid_range===ref_invalid,"same control semantics as parallel reference");
            if(snapshot_valid)begin
                check(payload===e_payload,"independent transactional reference");
                check(ref_valid && payload===ref_payload,"whole snapshot equivalent to original bank at accepted request");
            end
            if(outstanding)begin
                if(outstanding_age<4)check(!snapshot_valid,"not early output");
                else begin
                    check(outstanding_age==4 && snapshot_valid,"bounded exact E+4 result");outstanding=0;
                end
            end
            if(!rst_n)check(snapshot_valid==0 && snapshot_pitch_bend==0 && snapshot_modulation==0 && snapshot_pitch_range=={4{5'd2}},"reset defaults");
        end
        check(count>16000 && requests>500 && results>500,"nonempty state/control/snapshot exercise");
        @(negedge clk);#2;rst_n=0;#1;
        check(!snapshot_valid && !event_ready && !request_ready,"async reset without next clock");
        $display("PASS performance_control_snapshot vectors=%0d checks=%0d requests=%0d results=%0d event_handshakes=%0d",count,checks,requests,results,accepted_controls);
        $finish;
    end
    initial begin #5000000;$fatal(1,"Serialized control test timeout");end
endmodule
