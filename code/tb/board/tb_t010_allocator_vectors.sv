// T010 compare independent Python oracle to public allocator ports only.
`timescale 1ns/1ps
module tb_t010_allocator_vectors;
    reg sys_clk=0, sys_rst_n=1, note_on=0, note_off=0;
    reg [3:0] source_id=0,channel_id=0,release_done=0;
    reg [7:0] midi_note=0;
    wire [1:0] allocated_slot, release_slot;
    wire slot_valid, release_target_valid;
    integer file, read_count, count=0;
    integer rst_v,on_v,off_v,src_v,ch_v,note_v,done_v,alloc_v,slot_v,rel_v,rel_slot_v;
    string path;
    voice_allocator_4 dut(.*);
    always #10 sys_clk=~sys_clk;
    initial begin
        if(!$value$plusargs("VECTORS=%s",path))$fatal(1,"Missing +VECTORS=...");
        file=$fopen(path,"r");
        if(!file)$fatal(1,"Cannot read T010 oracle vectors");
        while(!$feof(file))begin
            read_count=$fscanf(file,"%d %d %d %d %d %d %d %d %d %d %d\n",
                rst_v,on_v,off_v,src_v,ch_v,note_v,done_v,alloc_v,slot_v,rel_v,rel_slot_v);
            if(read_count==11)begin
                @(negedge sys_clk);
                sys_rst_n=rst_v[0];note_on=on_v[0];note_off=off_v[0];
                source_id=src_v[3:0];channel_id=ch_v[3:0];midi_note=note_v[7:0];
                release_done=done_v[3:0];
                @(posedge sys_clk);#1;
                if(slot_valid!==alloc_v[0] ||
                   (alloc_v!=0 && allocated_slot!==slot_v[1:0]) ||
                   release_target_valid!==rel_v[0] ||
                   (rel_v!=0 && release_slot!==rel_slot_v[1:0]))
                    $fatal(1,"FAIL T010 oracle row=%0d exp=%0d/%0d %0d/%0d got=%0d/%0d %0d/%0d",
                        count,alloc_v,slot_v,rel_v,rel_slot_v,
                        slot_valid,allocated_slot,release_target_valid,release_slot);
                count++;
            end else if(read_count!= -1)$fatal(1,"Malformed vector row=%0d fields=%0d",count,read_count);
        end
        $fclose(file);
        if(count<1000)$fatal(1,"Too few vectors: %0d",count);
        $display("PASS T010 oracle vectors=%0d",count);
        $finish;
    end
    initial begin #1000000;$fatal(1,"T010 oracle timeout");end
endmodule
