// M2 cycle-by-cycle reference vectors, normal accepted-event port only.
`timescale 1ns/1ps
module tb_performance_control_state;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,accepted_valid=0,sample_capture=0;
    logic [63:0] accepted_data=0;
    logic [3:0] slot_occupied=0;
    logic [15:0] slot_source_ids=0,slot_channels=0;
    logic [127:0] slot_generations=0;
    logic [31:0] sample_id=0;
    wire [47:0] slot_pitch_bend,slot_modulation,snapshot_pitch_bend,snapshot_modulation;
    wire [19:0] slot_pitch_range,snapshot_pitch_range;
    wire snapshot_valid,control_applied,invalid_range;
    wire [31:0] snapshot_id;
    wire [3:0] snapshot_occupied;
    wire [15:0] snapshot_sources,snapshot_channels;
    wire [127:0] snapshot_generations;
    performance_control_state dut(.*);
    integer fd,count=0,checks=0,n;
    string vectors;
    logic reset_input,event_input,capture_input;
    logic [63:0] data_input;
    logic [3:0] occupied_input,expect_occupied;
    logic [15:0] source_input,channel_input,expect_sources,expect_channels;
    logic [127:0] generation_input,expect_generations;
    logic [31:0] id_input,expect_id;
    logic [47:0] expect_pitch,expect_mod,expect_snap_pitch,expect_snap_mod;
    logic [19:0] expect_range,expect_snap_range;
    logic expect_valid,expect_applied,expect_invalid;
    task automatic check(input logic ok,input string name);
        checks++;if(ok!==1'b1)$fatal(1,"Control state vector=%0d %s",count,name);
    endtask
    initial begin
        if(!$value$plusargs("VECTORS=%s",vectors))$fatal(1,"VECTORS required");
        fd=$fopen(vectors,"r");if(!fd)$fatal(1,"Cannot open vectors");
        while(!$feof(fd))begin
            n=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                reset_input,event_input,data_input,occupied_input,source_input,channel_input,
                generation_input,capture_input,id_input,expect_pitch,expect_mod,expect_range,
                expect_valid,expect_id,expect_occupied,expect_sources,expect_channels,
                expect_generations,expect_snap_pitch,expect_snap_mod,expect_snap_range,
                expect_applied,expect_invalid);
            if(n==-1)break;
            if(n!=23)$fatal(1,"Malformed vector fields=%0d",n);
            @(negedge clk);rst_n=reset_input;accepted_valid=event_input;accepted_data=data_input;
            slot_occupied=occupied_input;slot_source_ids=source_input;slot_channels=channel_input;
            slot_generations=generation_input;sample_capture=capture_input;sample_id=id_input;
            @(posedge clk);#1;count++;
            check(slot_pitch_bend===expect_pitch,"live signed pitch values");
            check(slot_modulation===expect_mod,"live modulation values");
            check(slot_pitch_range===expect_range,"live pitch ranges");
            check(snapshot_valid===expect_valid && snapshot_id===expect_id,"snapshot valid/id");
            check(snapshot_occupied===expect_occupied && snapshot_sources===expect_sources && snapshot_channels===expect_channels,"captured identity");
            check(snapshot_generations===expect_generations,"captured generation");
            check(snapshot_pitch_bend===expect_snap_pitch && snapshot_modulation===expect_snap_mod && snapshot_pitch_range===expect_snap_range,"atomic snapshot controls");
            check(control_applied===expect_applied && invalid_range===expect_invalid,"update/reject pulses");
        end
        check(count>5000,"nonempty directed/exhaustive/random vectors");
        // Assert reset between clock edges and check before the next posedge.
        @(negedge clk);#2;rst_n=0;#1;
        check(snapshot_valid===0 && snapshot_pitch_bend===0 && snapshot_modulation===0,"async reset snapshot clear");
        check(slot_pitch_bend===0 && slot_modulation===0 && slot_pitch_range=={4{5'd2}},"async reset neutral query");
        $display("PASS performance_control_state vectors=%0d checks=%0d",count,checks);
        $finish;
    end
    initial begin #10000000;$fatal(1,"Control state timeout");end
endmodule
