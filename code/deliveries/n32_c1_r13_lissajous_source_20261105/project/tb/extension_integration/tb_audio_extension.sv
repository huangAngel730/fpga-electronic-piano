`timescale 1ns/1ps
module tb_audio_extension;
    import audio_defs_pkg::*;
    reg clk50=0, rst_n=0;
    always #10 clk50=~clk50;
    reg [1:0] keys=2'b11;
    reg midi=1;
    wire core_clk, ready, ev_valid, ev_ready;
    performance_event_t ev_data;
    reg score_valid=0;
    performance_event_t score_data;
    wire dut_bclk,dut_lrck,dut_din,dut_pa;
    wire ref_bclk,ref_lrck,ref_din,ref_pa;
    wire [63:0] ref_event_data;
    wire ref_event_valid,ref_event_ready;
    wire [31:0] ref_underrun;
    reg equivalent=1;
    integer cycles=0, compared=0, score_accepted=0,human_accepted=0,stage=0;
    integer saw_nonzero=0, notes_on=0, notes_off=0;
    m3_pro_audio_core_r10 #(.DEBOUNCE_CNT(2),.DEBOUNCE_CLK_HZ(1000)) dut (
        .sys_clk(clk50),.sys_rst_n(rst_n),.key_n(keys),.midi_rx(midi),
        .i2s_bclk(dut_bclk),.i2s_lrck(dut_lrck),.i2s_din(dut_din),.pa_en(dut_pa),
        .score_event_valid(score_valid),.score_event_ready(ready),.score_event_data(score_data),
        .obs_core_clk(core_clk),.obs_event_valid(ev_valid),.obs_event_ready(ev_ready),
        .obs_event_data(ev_data)
    );
    m3_pro_audio_core_baseline #(.DEBOUNCE_CNT(2),.DEBOUNCE_CLK_HZ(1000)) reference (
        .sys_clk(clk50),.sys_rst_n(rst_n),.key_n(keys),.midi_rx(midi),
        .i2s_bclk(ref_bclk),.i2s_lrck(ref_lrck),.i2s_din(ref_din),.pa_en(ref_pa),
        .obs_event_valid(ref_event_valid),.obs_event_ready(ref_event_ready),
        .obs_event_data(ref_event_data)
    );
    task automatic send_score(input [2:0] kind,input [6:0] note_number,input [3:0] channel=0);
        begin
            @(negedge core_clk);
            score_data='0;score_data.event_type=kind;
            score_data.source_id=4'd14;score_data.channel=channel;
            score_data.note_number=note_number;score_data.velocity=10'd800;
            score_data.expression=10'd1023;score_valid=1;
            do @(posedge core_clk); while(!ready);
            @(negedge core_clk);score_valid=0;
        end
    endtask
    always @(posedge core_clk) begin
        cycles=cycles+1;
        if(ev_valid && ev_ready) begin
            if(ev_data.source_id==14 && ev_data.event_type==EVENT_ALL_NOTES_OFF)
                $fatal(1,"score cleanup escaped into baseline global panic");
            if(ev_data.source_id==14)score_accepted=score_accepted+1;
            else if(ev_data.source_id==0 || ev_data.source_id==1)human_accepted=human_accepted+1;
            else $fatal(1,"unexpected source");
            if(ev_data.event_type==EVENT_NOTE_ON) notes_on=notes_on+1;
            if(ev_data.event_type==EVENT_NOTE_OFF) notes_off=notes_off+1;
        end
        #1;
        if(equivalent && rst_n && dut.obs_rst_n) begin
            compared=compared+1;
            if({dut_bclk,dut_lrck,dut_din,dut_pa} !== {ref_bclk,ref_lrck,ref_din,ref_pa})
                $fatal(1,"baseline serial audio changed without score cycle=%0d",cycles);
            if({ev_valid,ev_ready,ev_data} !== {ref_event_valid,ref_event_ready,ref_event_data})
                $fatal(1,"baseline human handshake changed cycle=%0d",cycles);
            if(dut.obs_commit && (dut.obs_commit_left!=0 || dut.obs_commit_right!=0)) saw_nonzero=1;
        end
        if(!rst_n && dut_pa!==1'b1)$fatal(1,"core reset must disable PA");
    end
    initial begin
        score_data='0;
        repeat(20)@(negedge clk50);rst_n=1;
        repeat(400)@(negedge core_clk);keys=2'b10;
        repeat(50000)@(negedge core_clk);keys=2'b00;
        repeat(50000)@(negedge core_clk);keys=2'b11;
        repeat(50000)@(negedge core_clk);
        if(compared<100000 || !saw_nonzero || human_accepted!=4 || notes_on!=2 || notes_off!=2)
            $fatal(1,"insufficient real audio/key coverage compared=%0d nonzero=%0d human=%0d",compared,saw_nonzero,human_accepted);
        $display("PASS BASELINE_AUDIO_EQUIVALENCE cycles=%0d human_events=%0d",compared,human_accepted);
        equivalent=0;stage=1;
        fork
            begin
                repeat(32)begin send_score(EVENT_NOTE_ON,7'd60);send_score(EVENT_NOTE_OFF,7'd60);end
            end
            begin
                repeat(8)begin
                    @(negedge core_clk);keys=2'b10;
                    repeat(100)@(negedge core_clk);keys=2'b11;
                    repeat(100)@(negedge core_clk);
                end
            end
        join
        repeat(2000)@(negedge core_clk);
        if(score_accepted!=64 || human_accepted!=20)$fatal(1,"arbitration loss score=%0d human=%0d",score_accepted,human_accepted);
        keys=2'b10;
        repeat(2000)@(negedge core_clk);
        send_score(EVENT_NOTE_ON,7'd60,4'd3);
        repeat(2000)@(negedge core_clk);
        send_score(EVENT_NOTE_ON,7'd64,4'd9);
        repeat(2000)@(negedge core_clk);
        send_score(EVENT_ALL_NOTES_OFF,7'd0);
        begin : idle_ready_check
            integer idle_wait;
            idle_wait=0;
            while(!ready && idle_wait<5000)begin @(negedge core_clk);idle_wait=idle_wait+1;end
            if(!ready)$fatal(1,"STOP cannot observe consumer idle after score valid drops");
        end
        begin : scoped_release_check
            integer human_held;
            human_held=0;
            for(integer i=0;i<4;i=i+1)begin
                if(dut.obs_occupied_mask[i] && !dut.obs_releasing_mask[i])begin
                    if(dut.obs_slot_sources[4*i+:4]==14)$fatal(1,"source14 still held after scoped stop");
                    if(dut.obs_slot_sources[4*i+:4]==1)human_held=human_held+1;
                end
            end
            if(human_held!=1)$fatal(1,"score cleanup released independent human note");
            if(score_accepted!=68)$fatal(1,"missing multichannel scoped NoteOffs count=%0d",score_accepted);
            $display("PASS SCOPED_SCORE_STOP channels=3,9 human_held=%0d",human_held);
        end
        rst_n=0;#1;if(dut_pa!==1'b1)$fatal(1,"async PLL/reset mute changed");
        $display("PASS EXTERNAL_SCORE_ARBITRATION score=%0d human=%0d",score_accepted,human_accepted);
        $display("INTEGRATION_AUDIO_TEST_COMPLETE");$finish;
    end
    reg stalled=0;
    reg [63:0] stalled_data;
    always @(posedge core_clk) begin
        if(!rst_n)stalled=0;
        else begin
            if(stalled && (!ev_valid || ev_data!==stalled_data))$fatal(1,"valid/data changed under audio stall");
            stalled=ev_valid&&!ev_ready;stalled_data=ev_data;
        end
    end
    initial begin #10000000;$fatal(1,"test watchdog");end
endmodule
