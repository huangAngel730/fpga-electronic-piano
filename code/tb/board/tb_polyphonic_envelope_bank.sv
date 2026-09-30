`timescale 1ns/1ps
module tb_polyphonic_envelope_bank;
    import audio_defs_pkg::*;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,event_valid=0,frame_tick=0,sample_req=0,result_ready=0;
    logic [63:0] event_data=0;
    logic [31:0] sample_req_id=0;
    wire event_ready,calc_ready,result_valid;
    wire [31:0] result_req_id,active_voice_count;
    wire [63:0] result_envelopes,result_waves;
    wire [127:0] result_fcw;
    wire [3:0] result_occupied;
    wire [11:0] result_states;
    polyphonic_envelope_bank dut(.*);
    integer checks=0,requests=0,ticks=0,results=0,previous,delta,saved_ticks;
    logic [63:0] captured,saved_waves;
    logic [31:0] expected_phase0=0,saved_phase0;
    logic signed [15:0] golden_wave [0:1023];
    string wavetable_path;
    task automatic check(input logic ok,input string label);
        checks++;if(ok!==1'b1)$fatal(1,"Envelope bank %s ticks=%0d requests=%0d result_id=%0d",label,ticks,requests,result_req_id);
    endtask
    always @(posedge clk) begin
        if(!rst_n) expected_phase0=0;
        else if(dut.lane_tick) begin
            ticks++;
            expected_phase0=expected_phase0+dut.slot_fcw[31:0];
        end
    end
    task automatic send(input logic [2:0] kind,input logic [3:0] src,ch,input logic [6:0] note,input logic [9:0] vel);
        performance_event_t e;
        e='0;e.event_type=kind;e.source_id=src;e.channel=ch;e.note_number=note;e.velocity=vel;
        wait(event_ready);@(negedge clk);event_data=e;event_valid=1;
        @(negedge clk);event_valid=0;
        wait(event_ready);repeat(5)@(negedge clk);
    endtask
    task automatic launch;
        wait(calc_ready);@(negedge clk);sample_req_id++;requests++;
        sample_req=1;@(negedge clk);sample_req=0;
    endtask
    task automatic consume;
        @(negedge clk);result_ready=1;@(negedge clk);result_ready=0;
        check(!result_valid,"successful result handshake clears valid");
    endtask
    task automatic sample_once;
        launch();wait(result_valid);@(negedge clk);
        check(result_req_id==sample_req_id,"snapshot belongs to requested generation");
        captured=result_envelopes;
        check(result_waves[15:0]===golden_wave[expected_phase0[31:22]],"DDS phase advances once and snapshot matches independent ROM lookup");
        results++;consume();
    endtask
    initial begin
        if(!$value$plusargs("WAVETABLE_PATH=%s",wavetable_path))$fatal(1,"WAVETABLE_PATH required");
        $readmemh(wavetable_path,golden_wave);
        repeat(4)@(negedge clk);
        check(!result_valid && active_voice_count==0 && result_envelopes==0,"reset silence");
        rst_n=1;
        for(integer i=0;i<4;i++)send(EVENT_NOTE_ON,0,0,60+i,1023);
        check(active_voice_count==4,"four simultaneous occupied envelopes");
        previous=0;
        for(integer n=0;n<240;n++)begin
            sample_once();
            check(captured[15:0]==captured[31:16] && captured[31:16]==captured[47:32] && captured[47:32]==captured[63:48],"all full-velocity lanes advance once together");
            delta=$signed({1'b0,captured[15:0]})-previous;
            check(delta>=0 && delta<=138,"attack per-sample bound");previous=captured[15:0];
        end
        check(captured==64'h7fff7fff7fff7fff,"all peaks are exactly 32767 at sample240");
        check(ticks==240,"exactly one ADSR tick per sample generation");
        launch();wait(result_valid);@(negedge clk);captured=result_envelopes;saved_waves=result_waves;saved_phase0=expected_phase0;saved_ticks=ticks;
        repeat(12)@(negedge clk);
        check(result_valid && result_envelopes==captured && result_waves==saved_waves && expected_phase0==saved_phase0 && ticks==saved_ticks,"held result stable and no extra sample advancement");
        check(!event_ready,"held sample backpressures events");consume();results++;
        // Off only the first identity; release tail remains until envelope IDLE.
        send(EVENT_NOTE_OFF,0,0,60,0);check(active_voice_count==4,"Note Off retains Release tail");
        for(integer n=0;n<4800;n++)sample_once();
        check(captured[15:0]==0 && active_voice_count==3,"completed Release frees exactly one slot");
        check(captured[31:16]>0 && captured[47:32]>0,"other held envelopes survive Release");
        send(EVENT_NOTE_ON,0,0,61,1);previous=dut.envelopes[31:16];
        sample_once();delta=previous-$signed({1'b0,captured[31:16]});
        check(delta>=0 && delta<=138,"high to low retrigger keeps current level and descends smoothly");
        for(integer n=1;n<240;n++)sample_once();
        check(captured[31:16]==6553,"light velocity target exact after240 samples");
        // Cancel before ADVANCE: no algorithm tick or exposed result.
        saved_ticks=ticks;launch();@(negedge clk);frame_tick=1;
        @(negedge clk);frame_tick=0;repeat(15)@(negedge clk);
        check(!result_valid && ticks==saved_ticks,"cancel pending request before advancement");
        // Cancel a held, already computed result; it must not leak to new ID.
        launch();wait(result_valid);@(negedge clk);frame_tick=1;
        @(negedge clk);frame_tick=0;check(!result_valid,"frame boundary expires held result");
        sample_once();check(result_req_id==sample_req_id,"next generation replaces discarded result");
        // Global panic also crosses source/channel identities.
        send(EVENT_NOTE_ON,2,3,65,1023);check(active_voice_count==4,"reuse freed slot for another source");
        send(EVENT_ALL_NOTES_OFF,0,0,0,0);
        for(integer n=0;n<4800;n++)sample_once();
        check(active_voice_count==0 && captured==0,"all sources retire after global Release");
        // A frame request can arrive after event acceptance but before slot dispatch.
        begin
            performance_event_t e;
            e='0;e.event_type=EVENT_NOTE_ON;e.note_number=72;e.velocity=1023;
            wait(event_ready);@(negedge clk);event_data=e;event_valid=1;
            @(negedge clk);event_valid=0;
            check(dut.dispatch_busy,"event is still in flight before frame request");
            launch();wait(result_valid);@(negedge clk);
            check(result_envelopes[15:0]>0 && result_occupied==1 && result_req_id==sample_req_id,
                  "request waits for event dispatch and gain ROM load before advancing");
            consume();results++;
        end
        launch();wait(result_valid);@(negedge clk);rst_n=0;repeat(3)@(negedge clk);
        check(!result_valid && result_envelopes==0 && result_waves==0 && result_req_id==0 && active_voice_count==0,"reset clears held generation and lifecycle");
        $display("PASS polyphonic_envelope_bank checks=%0d requests=%0d ticks=%0d results=%0d",checks,requests,ticks,results);$finish;
    end
    initial begin #100_000_000;$fatal(1,"Envelope bank timeout");end
endmodule