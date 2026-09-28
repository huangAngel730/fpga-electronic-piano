// M2 T010 public-port acceptance review. Does NOT patch M1 source.
// Can run on original RTL with a compatible simulator, or on a generic
// Yosys/read_slang elaborated netlist. No internal slot register peeking.
`timescale 1ns/1ps
module tb_t010_allocator_review;
    reg sys_clk=0,sys_rst_n=1,note_on=0,note_off=0;
`ifdef T010_RELEASE_VECTOR
    reg [3:0] release_done=0;
`else
    reg release_done=0;
`endif
    reg [3:0] source_id=0,channel_id=0;
    reg [7:0] midi_note=0;
    wire [1:0] allocated_slot,release_slot;
    wire slot_valid,release_target_valid;
    integer checks=0;
    string scenario;
    voice_allocator_4 dut(.*);
    always #10 sys_clk=~sys_clk;

    task automatic check(input logic condition,input string detail);
        checks=checks+1;
        if(condition!==1'b1)
            $fatal(1,"FAIL T010 %s: %s checks=%0d allocated=%0d release=%0d",
                   scenario,detail,checks,allocated_slot,release_slot);
    endtask
    task automatic reset_dut;
        #1;sys_rst_n=0;note_on=0;note_off=0;release_done=0;
        repeat(3) @(negedge sys_clk);
        check(!slot_valid && !release_target_valid,"reset clears event output validity");
        sys_rst_n=1;
        @(negedge sys_clk);
    endtask
    task automatic on(input integer src,ch,note,expected_slot);
        @(negedge sys_clk);
        source_id=src;channel_id=ch;midi_note=note;note_on=1;
        @(posedge sys_clk);#1;
        check(slot_valid && allocated_slot==expected_slot,"Note On target slot");
        @(negedge sys_clk);note_on=0;
    endtask
    task automatic off(input integer src,ch,note,expected_slot);
        @(negedge sys_clk);
        source_id=src;channel_id=ch;midi_note=note;note_off=1;
        @(posedge sys_clk);#1;
        if(expected_slot<0)check(!release_target_valid,"unmatched Note Off ignored");
        else check(release_target_valid && release_slot==expected_slot,"Note Off identity/slot");
        @(negedge sys_clk);note_off=0;
    endtask
    task automatic done(input integer slot_index);
`ifdef T010_RELEASE_VECTOR
        @(negedge sys_clk);release_done=4'b0001 << slot_index;
`else
        @(negedge sys_clk);release_done=1;
`endif
        @(posedge sys_clk);#1;
        check(!slot_valid && !release_target_valid,"completion is not a Note event");
        @(negedge sys_clk);release_done=0;
    endtask
    task automatic fill;
        on(0,0,60,0);on(0,0,61,1);on(0,0,62,2);on(0,0,63,3);
    endtask

    initial begin
        if(!$value$plusargs("CASE=%s",scenario))$fatal(1,"Need +CASE=<name>");
        reset_dut();
        if(scenario=="baseline")begin
            fill();
            on(0,0,61,1);
            on(0,0,64,0); // oldest after refreshing slot1
            @(posedge sys_clk);#1;
            check(!slot_valid,"slot_valid is one cycle");
            reset_dut();on(0,0,70,0);
        end else if(scenario=="identity")begin
            on(0,0,60,0);on(1,0,60,1);on(0,1,60,2);
            off(0,1,60,2);off(2,0,60,-1);
            on(1,0,60,1);on(0,0,60,0);
        end else if(scenario=="release_retrigger")begin
            on(0,0,60,0);off(0,0,60,0);
            // Frozen requirement: same source/channel/note retriggers same
            // still-sounding Release voice, not a second slot.
            on(0,0,60,0);
        end else if(scenario=="release_isolation")begin
            fill();off(0,0,61,1);off(0,0,63,3);
            // Fixture: only voice1 has finished its Release; voice3 has not.
            // Completion identifies slot1 only; slot3 must remain in Release.
            // With correct per-voice completion, only slot1 becomes free.
            done(1);on(0,0,64,1);
            // Existing LRU policy: if there is no other idle slot, steal oldest
            // slot0. If completion wrongly cleared slot3, new note takes 3.
            on(0,0,65,0);
        end else if(scenario=="age_wrap")begin
            fill();
            // 4 initial allocations + 5 refreshes = 9 events. The refreshed
            // slot0 is NEWEST. Slot1 must be the oldest, across 3-bit rollover.
            repeat(5) on(0,0,60,0);
            on(0,0,64,1);
        end else if(scenario=="single_release")begin
            fill();off(0,0,61,1);done(1);on(0,0,64,1);
        end else $fatal(1,"Unknown scenario %s",scenario);
        $display("PASS T010 %s checks=%0d",scenario,checks);
        $finish;
    end
    initial begin #1000000;$fatal(1,"T010 review timeout");end
endmodule
