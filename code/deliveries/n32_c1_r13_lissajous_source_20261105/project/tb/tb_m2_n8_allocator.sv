`timescale 1ns/1ps
module tb_m2_n8_allocator;
    logic clk=0,rst_n=0,note_on=0,note_off=0;
    logic [3:0] source_id=0,channel_id=0;
    logic [7:0] midi_note=0;
    logic [7:0] release_done=0;
    wire [2:0] allocated_slot,release_slot;
    wire slot_valid,release_target_valid;
    integer n;
    always #5 clk=~clk;

    m2_polyphony_voice_allocator #(.N(8)) dut(
        .sys_clk(clk),.sys_rst_n(rst_n),.note_on(note_on),.note_off(note_off),
        .source_id(source_id),.channel_id(channel_id),.midi_note(midi_note),
        .release_done(release_done),.allocated_slot(allocated_slot),
        .slot_valid(slot_valid),.release_slot(release_slot),
        .release_target_valid(release_target_valid));

    task automatic add_note(input [7:0] note,input [2:0] expected);
        begin
            @(negedge clk);midi_note=note;note_on=1;
            @(posedge clk);#1;
            if(!slot_valid || allocated_slot!==expected)
                $fatal(1,"ALLOC note=%0d expected=%0d got=%0d valid=%0b",
                    note,expected,allocated_slot,slot_valid);
            @(negedge clk);note_on=0;
        end
    endtask

    initial begin
        repeat(3) @(posedge clk);rst_n<=1;
        for(n=0;n<8;n=n+1) add_note(8'd60+n,n[2:0]);
        // With all slots occupied, the ninth distinct note steals oldest slot0.
        add_note(8'd72,3'd0);
        // Retriggering an existing identity reuses its slot rather than
        // consuming/stealing another slot.
        add_note(8'd64,3'd4);
        $display("PASS N8_ALLOCATE_AND_STEAL");
        $finish;
    end
endmodule
