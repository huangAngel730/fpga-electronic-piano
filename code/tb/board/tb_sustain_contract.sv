// M2 contract gate for M3 sustain controller; source files are never rewritten.
`timescale 1ns/1ps
module tb_sustain_contract;
    reg clk=0;always #10 clk=~clk;
    reg rst_n=0,cmd_valid=0,release_ready=0;
    reg [2:0] cmd_type=0;
    reg [1:0] cmd_slot=0;
    reg [3:0] cmd_source_id=0,cmd_channel=0;
    reg [6:0] cmd_note_number=0;
    reg [11:0] cmd_control_value=0;
    reg [31:0] cmd_generation=0;
    wire cmd_ready,release_valid;
    wire [3:0] release_mask,occupied_mask,key_down_mask,deferred_mask,releasing_mask;
    wire [127:0] release_generations;
    sustain_controller dut(.*);
    integer fd,count=0,code;
    integer ri,vi,acki,ti,si,sourcei,channeli,notei,valuei;
    reg [31:0] geni,g0,g1,g2,g3;
    integer ready_expected,valid_expected,release_expected;
    integer occupied_expected,key_expected,deferred_expected,releasing_expected;
    string vector_path;
    initial begin
        if(!$value$plusargs("VECTORS=%s",vector_path))$fatal(1,"VECTORS required");
        fd=$fopen(vector_path,"r");if(!fd)$fatal(1,"Cannot open vector file");
        while(!$feof(fd))begin
            code=$fscanf(fd,"%d %d %d %d %d %d %d %d %d %h %d %d %d %h %h %h %h %d %d %d %d\n",
                ri,vi,acki,ti,si,sourcei,channeli,notei,valuei,geni,
                ready_expected,valid_expected,release_expected,g0,g1,g2,g3,
                occupied_expected,key_expected,deferred_expected,releasing_expected);
            if(code!=21)$fatal(1,"Malformed vector%0d columns%0d",count+1,code);
            @(negedge clk);
            rst_n=ri;cmd_valid=vi;release_ready=acki;
            cmd_type=ti;cmd_slot=si;cmd_source_id=sourcei;cmd_channel=channeli;
            cmd_note_number=notei;cmd_control_value=valuei;cmd_generation=geni;
            @(posedge clk);#1;
            count++;
            if(cmd_ready!==ready_expected[0] || release_valid!==valid_expected[0] ||
               release_mask!==release_expected[3:0] || release_generations!=={g3,g2,g1,g0} ||
               occupied_mask!==occupied_expected[3:0] || key_down_mask!==key_expected[3:0] ||
               deferred_mask!==deferred_expected[3:0] || releasing_mask!==releasing_expected[3:0])
                $fatal(1,"Sustain contract row%0d expected ready/valid/mask=%0d/%0d/%h actual=%b/%b/%h occupied/key/deferred/releasing=%b/%b/%b/%b",
                    count,ready_expected,valid_expected,release_expected,cmd_ready,release_valid,release_mask,
                    occupied_mask,key_down_mask,deferred_mask,releasing_mask);
        end
        $fclose(fd);
        if(count<3000)$fatal(1,"Insufficient vector coverage%0d",count);
        $display("PASS sustain contract vectors=%0d",count);$finish;
    end
    initial begin #1000000;$fatal(1,"Sustain contract timeout");end
endmodule