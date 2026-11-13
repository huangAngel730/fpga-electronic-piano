`timescale 1ns/1ps
module tb_pro_score_audio_adapter_n8;
    import audio_defs_pkg::*;
    logic clk=0,rst_n=0,in_valid=0,out_ready=1,consumer_idle=1;
    performance_event_t in_data;
    wire in_ready,out_valid;
    performance_event_t out_data;
    logic [7:0] occupied,releasing;
    logic [31:0] sources,channels;
    logic [63:0] notes;
    integer count;
    logic seen60,seen67;
    always #5 clk=~clk;

    pro_score_audio_adapter #(.SLOT_COUNT(8)) dut(
        .clk(clk),.rst_n(rst_n),.in_valid(in_valid),.in_ready(in_ready),
        .in_data(in_data),.out_valid(out_valid),.out_ready(out_ready),
        .consumer_idle(consumer_idle),.out_data(out_data),.occupied(occupied),
        .releasing(releasing),.sources(sources),.channels(channels),.notes(notes));

    always @(posedge clk) if(rst_n && out_valid && out_ready) begin
        if(out_data.event_type!==EVENT_NOTE_OFF || out_data.source_id!==4'd14)
            $fatal(1,"BAD_CLEANUP_EVENT");
        count<=count+1;
        if(out_data.note_number==7'd60) seen60<=1;
        if(out_data.note_number==7'd67) seen67<=1;
    end

    initial begin
        occupied='0;releasing='0;sources='0;channels='0;notes='0;
        count=0;seen60=0;seen67=0;in_data='0;
        repeat(3) @(posedge clk);rst_n<=1;
        // Score voices deliberately occupy upper-half slots 4 and 7. Slot 6
        // belongs to the human source and must not be released.
        occupied[4]=1;occupied[6]=1;occupied[7]=1;
        sources[4*4+:4]=4'd14;channels[4*4+:4]=4'd2;notes[8*4+:8]=8'd60;
        sources[4*6+:4]=4'd0; channels[4*6+:4]=4'd1;notes[8*6+:8]=8'd64;
        sources[4*7+:4]=4'd14;channels[4*7+:4]=4'd3;notes[8*7+:8]=8'd67;
        @(posedge clk);in_data<=make_all_notes_off(4'd14);in_valid<=1;
        fork
            begin
                while(!in_ready) @(posedge clk);
                @(posedge clk);in_valid<=0;
            end
            begin
                repeat(80) @(posedge clk);
                $fatal(1,"N8_CLEANUP_TIMEOUT");
            end
        join_any
        disable fork;
        repeat(3) @(posedge clk);
        if(count!=2 || !seen60 || !seen67) $fatal(1,"N8_CLEANUP_MISMATCH");
        $display("PASS N8_SCORE_CLEANUP count=%0d",count);
        $finish;
    end
endmodule
