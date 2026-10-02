// M2 contract probe. Accelerated LFO phase; not a 5 Hz frequency test.
// FCW reference: A4=39370534; Q15 sine=32767, depth=512 gives 40522165.
// Run against the received module; a failing candidate must exit nonzero.
`timescale 1ns/1ps
module tb_pitch_mod_noteon_contract_review;
    logic clk=0, rst_n=0, enable=0, note_on=0;
    wire [31:0] out_fcw;
    wire valid;
    integer checks=0, failures=0;
    localparam logic [31:0] BASE=32'd39370534, PEAK=32'd40522165;
    pitch_mod_fcw #(.LFO_INC(32'h40000000)) dut (
        .sys_clk(clk), .sys_rst_n(rst_n), .sample_enable(enable),
        .note_on(note_on), .bend(12'sd0), .modulation(12'd4095),
        .pitch_range(5'd2), .base_fcw(BASE), .fcw_out(out_fcw),
        .fcw_valid(valid));
    always #10 clk=~clk;
    task automatic check(input logic ok, input string label);
        checks=checks+1;
        if (ok !== 1'b1) begin
            failures=failures+1;
            $display("FAIL: %s fcw=%0d phase=%08x valid=%b",label,out_fcw,dut.lfo_phase,valid);
        end
    endtask
    task automatic tick(input logic en, input logic on,
                        input logic [31:0] expected_fcw,
                        input logic [31:0] expected_phase,
                        input string label);
        @(negedge clk); enable=en; note_on=on;
        @(posedge clk); #1;
        check(valid === en, {label," valid"});
        check(out_fcw === expected_fcw, {label," FCW"});
        check(dut.lfo_phase === expected_phase, {label," next phase"});
    endtask
    initial begin
        repeat(2) @(negedge clk);
        check(out_fcw === 0,"reset output");
        check(valid === 0,"reset valid");
        rst_n=1;
        tick(0,0,0,0,"idle");
        tick(1,0,BASE,32'h40000000,"first sample");
        tick(0,0,BASE,32'h40000000,"sparse hold");
        tick(1,1,BASE,32'h40000000,"same-edge NoteOn reads zero and advances once");
        tick(1,0,PEAK,32'h80000000,"next sample uses advanced phase");
        tick(0,0,PEAK,32'h80000000,"hold after restart");
        tick(0,1,PEAK,0,"off-sample NoteOn resets phase only");
        tick(0,0,PEAK,0,"idle after off-sample NoteOn");
        tick(1,0,BASE,32'h40000000,"first sample after off-sample NoteOn");
        tick(1,0,PEAK,32'h80000000,"second sample after off-sample NoteOn");
        tick(1,1,BASE,32'h40000000,"retrigger");
        tick(1,1,BASE,32'h40000000,"consecutive retrigger");
        @(negedge clk); #3; rst_n=0; #1;
        check(out_fcw === 0,"asynchronous reset output");
        check(valid === 0,"asynchronous reset valid");
        check(dut.lfo_phase === 0,"asynchronous reset phase");
        @(negedge clk); enable=0; note_on=0; rst_n=1;
        tick(1,0,BASE,32'h40000000,"recovery");
        if(checks < 40) $fatal(1,"empty contract probe");
        if(failures != 0) $fatal(1,"FAIL: noteon contract %0d/%0d",failures,checks);
        $display("PASS: noteon contract %0d checks",checks); $finish;
    end
endmodule
