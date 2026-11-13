`timescale 1ns/1ps
// SOURCE-only selfcheck; run from project/ with production sources + primitives.
// Override N=16 for the same-source secondary configuration.
module tb_n32_bright_frame_transport;
    import audio_defs_pkg::*;
    parameter integer N=32;
    reg clk=0;
    always #12.5 clk=~clk;
    reg rst_n=0,frame_tick=0,ev_valid=0,config_valid=1;
    performance_event_t ev;
    wire ev_ready,config_ready,commit,pending,request_accept;
    wire signed [23:0] left,right;
    wire [31:0] occupied,releasing,requests,commits,underruns;
    wire [N*8-1:0] notes;
    wire [N*4-1:0] sources,channels;
    integer phase=0,frame_no=0,nonzero=0;
    reg cadence=0;
    m2_eightvoice_bright_frame_core #(.N(N)) dut(
        .clk(clk),.rst_n(rst_n),.frame_tick(frame_tick),
        .event_valid(ev_valid),.event_ready(ev_ready),.event_data(ev),
        .config_valid(config_valid),.config_ready(config_ready),
        .config_enable(1'b0),.config_delay_samples(16'd1),
        .config_dry_gain(15'd16384),.config_wet_gain(15'd0),.config_feedback(15'd0),
        .play_left(left),.play_right(right),.pending_valid(pending),
        .commit_pulse(commit),.request_accept(request_accept),
        .pcm_request_count(requests),.pcm_commit_count(commits),.audio_underrun(underruns),
        .full_occupied(occupied[N-1:0]),.full_releasing(releasing[N-1:0]),
        .full_notes(notes),.full_sources(sources),.full_channels(channels));
    // 48 kHz nominal cadence at 40 MHz: 833,833,834 clocks.
    integer period_count=0;
    always @(negedge clk) begin
        frame_tick=0;
        if(cadence)begin
            if(phase==((period_count%3==2)?833:832))begin
                phase=0;period_count=period_count+1;frame_tick=1;
            end else phase=phase+1;
        end
    end
    always @(posedge clk)if(rst_n)begin
        if(config_valid && request_accept)$fatal(1,"CONFIG_SAMPLE_COLLISION");
        if(frame_tick)begin
            frame_no=frame_no+1;
            if(left!==right)$fatal(1,"STEREO_MISMATCH");
            if(left!=0)nonzero=nonzero+1;
        end
    end
    task automatic send(input performance_event_t e);
        @(negedge clk);ev=e;ev_valid=1;
        do @(posedge clk);while(!ev_ready);
        @(negedge clk);ev_valid=0;
    endtask
    task automatic settle;
        // N32 allocation now performs a 32-lane identity/free scan followed
        // by a 32-lane rank update.  Allow that bounded transaction to retire
        // before inspecting the externally visible slot table.
        repeat(96)@(posedge clk);
    endtask
    task automatic run_timbre(input bit organ);
        performance_event_t program_event;
        program_event='0;program_event.event_type=EVENT_CONTROL_CHANGE;
        program_event.source_id=1;program_event.channel=0;
        program_event.control_id=CTRL_VOICE_SELECT;
        program_event.control_value=organ;
        send(program_event);settle();
        for(integer i=0;i<N;i++)begin
            send(make_note_event(1'b1,4'd1,4'd0,8'(36+i),10'd640));settle();
        end
        if(occupied[N-1:0]!=={N{1'b1}})$fatal(1,"MISSING_HIGH_SLOT");
        if(notes[8*(N-1)+:8]!==8'(35+N))$fatal(1,"HIGH_SLOT_NOTE");
        nonzero=0;
        repeat(256*834)@(posedge clk);
        if(nonzero==0 || commits==0)$fatal(1,"NO_AUDIBLE_PCM");
        send(make_note_event(1'b1,4'd1,4'd0,8'd100,10'd640));settle();
        if($countones(occupied[N-1:0])!=N)$fatal(1,"NPLUS1_COUNT");
        for(integer i=0;i<N;i++)begin
            send(make_note_event(1'b0,4'd1,4'd0,8'(36+i),10'd0));settle();
        end
        send(make_note_event(1'b0,4'd1,4'd0,8'd100,10'd0));settle();
        repeat(6000*834)@(posedge clk);
        if(occupied[N-1:0]!==0)$fatal(1,"RELEASE_TAIL_STUCK");
    endtask
    initial begin
        ev='0;
        repeat(8)@(negedge clk);rst_n=1;cadence=1;
        do @(posedge clk);while(!config_ready);
        @(negedge clk);config_valid=0;
        run_timbre(0);run_timbre(1);
        $display("N32_BRIGHT_FRAME_TRANSPORT_PASS N=%0d",N);$finish;
    end
    initial begin #400000000;$fatal(1,"TIMEOUT");end
endmodule
