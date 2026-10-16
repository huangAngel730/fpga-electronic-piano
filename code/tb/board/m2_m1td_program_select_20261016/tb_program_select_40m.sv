// R06 frozen MIDI UART + M1TD router: only Program 0/1 timbre selection.
// 40 MHz core clock; 31250 baud MIDI; no PLL, PCM or board-level claim.
`timescale 1ns/1ps
module tb_program_select_40m;
    import audio_defs_pkg::*;
    logic clk=0, rst_n=0, midi_rx=1;
    always #12.5 clk=~clk;
    localparam integer BIT_CYCLES=1280;
    wire midi_valid, midi_ready, shared_valid, shared_ready, dispatch_busy;
    performance_event_t midi_data, shared_data;
    wire [15:0] fifo_level, fifo_peak, shared_level;
    wire [31:0] frame_errors, parse_errors, overflows;
    wire [3:0] slot_on, slot_off, occupied, releasing, timbre;
    wire [39:0] velocity;
    wire [127:0] fcw, generations;
    wire [31:0] notes, active;
    wire [15:0] sources, channels;
    integer programs=0, note_ons=0, checks=0;

    midi_input #(.CLK_HZ(40_000_000), .SOURCE_ID(4'd0)) u_midi (
        .clk(clk),.rst_n(rst_n),.midi_rx_async(midi_rx),
        .event_ready(midi_ready),.event_valid(midi_valid),.event_data(midi_data),
        .event_fifo_level(fifo_level),.event_fifo_high_watermark(fifo_peak),
        .uart_frame_error_count(frame_errors),.parser_error_count(parse_errors),
        .event_fifo_overflow_count(overflows),.midi_rx_busy()
    );
    // Use the same shared event FIFO as the frozen board top; button side idle.
    performance_event_fifo #(.DEPTH(32)) u_shared_fifo (
        .clk(clk),.rst_n(rst_n),.button_valid(1'b0),.button_ready(),
        .button_data('0),.midi_valid(midi_valid),.midi_ready(midi_ready),
        .midi_data(midi_data),.event_valid(shared_valid),
        .event_ready(shared_ready),.event_data(shared_data),
        .event_fifo_level(shared_level),.event_fifo_high_watermark()
    );
    m1td_polyphonic_event_router u_router (
        .clk(clk),.rst_n(rst_n),.sample_owner_ready(1'b1),
        .event_valid(shared_valid),.event_ready(shared_ready),.dispatch_busy(dispatch_busy),
        .event_data(shared_data),.release_done(4'b0),
        .slot_note_on(slot_on),.slot_note_off(slot_off),
        .slot_occupied(occupied),.slot_releasing(releasing),
        .slot_velocity(velocity),.slot_fcw(fcw),.slot_notes(notes),
        .slot_timbre(timbre),.active_voice_count(active),
        .slot_source_ids(sources),.slot_channel_ids(channels),
        .slot_generations(generations)
    );

    always @(posedge clk) if (rst_n && shared_valid && shared_ready) begin
        if (shared_data.event_type==EVENT_CONTROL_CHANGE &&
            shared_data.control_id==CTRL_VOICE_SELECT) programs++;
        if (shared_data.event_type==EVENT_NOTE_ON && shared_data.velocity!=0) note_ons++;
    end
    task automatic check(input logic pass, input string reason);
        checks++;
        if (pass!==1'b1) $fatal(1,"PROGRAM_SELECT_%s",reason);
    endtask
    task automatic send_byte(input logic [7:0] value);
        @(negedge clk); midi_rx=0; repeat(BIT_CYCLES) @(negedge clk);
        for(integer bit_index=0;bit_index<8;bit_index++) begin
            midi_rx=value[bit_index]; repeat(BIT_CYCLES) @(negedge clk);
        end
        midi_rx=1; repeat(BIT_CYCLES) @(negedge clk);
    endtask
    task automatic settle(input integer expected_programs,input integer expected_notes);
        integer remaining;
        remaining=6000;
        while ((programs<expected_programs || note_ons<expected_notes ||
                fifo_level!=0 || shared_level!=0 || midi_valid || shared_valid || dispatch_busy) && remaining>0) begin
            @(negedge clk); remaining--;
        end
        check(remaining>0,"TIMEOUT");
        repeat(6) @(negedge clk);
    endtask
    task automatic send_program(input logic [3:0] channel,input logic [6:0] value);
        integer expected;
        expected=programs+1;
        send_byte({4'hc,channel}); send_byte({1'b0,value});
        settle(expected,note_ons);
    endtask
    task automatic note(input logic [3:0] channel,input logic [6:0] number);
        integer expected;
        expected=note_ons+1;
        send_byte({4'h9,channel}); send_byte({1'b0,number}); send_byte(8'd100);
        settle(programs,expected);
    endtask
    function automatic integer find_note(input logic [3:0] channel,input logic [6:0] number);
        find_note=-1;
        for(integer i=0;i<4;i++)
            if(occupied[i] && channels[4*i+:4]==channel &&
               sources[4*i+:4]==0 && notes[8*i+:8]=={1'b0,number})
                find_note=i;
    endfunction
    task automatic check_note(input logic [3:0] channel,input logic [6:0] number,
                              input logic expected_timbre);
        integer lane;
        lane=find_note(channel,number);
        check(lane>=0,"MISSING_NOTE");
        check(timbre[lane]===expected_timbre,"WRONG_TIMBRE");
    endtask
    initial begin
        repeat(6) @(negedge clk); rst_n=1;
        note(0,60); check_note(0,60,0); // reset default: piano
        send_program(0,1); check_note(0,60,0); // held voice must stay piano
        note(0,62); check_note(0,62,1); // next Note On: triangle
        send_program(0,0); check_note(0,62,1); // held triangle is stable
        note(0,64); check_note(0,64,0);
        send_program(1,1); note(1,67); check_note(1,67,1); // channel isolation
        send_program(0,127); // unsupported program must leave channel 0 unchanged
        note(0,64); check_note(0,64,0);
        check(active==4,"FOUR_VOICES");
        check(frame_errors==0 && parse_errors==0 && overflows==0,"MIDI_ERRORS");
        rst_n=0; repeat(5) @(negedge clk);
        check(occupied==0 && timbre==0,"RESET_SLOTS");
        rst_n=1; repeat(4) @(negedge clk);
        note(0,72); check_note(0,72,0); // reset program defaults to piano
        $display("PASS R06_MIDI_PROGRAM_40M programs=%0d notes=%0d checks=%0d",programs,note_ons,checks);
        $finish;
    end
    initial begin #12000000; $fatal(1,"PROGRAM_SELECT_WATCHDOG"); end
endmodule
