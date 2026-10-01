// M2 parser/control-state hookup test ONLY; no formal FCW/LFO integration.
// Actual accepted handshake tap; PCM request cadence1041/1042 at50MHz.
`timescale 1ns/1ps
module tb_midi_controls_state_link;
    import audio_defs_pkg::*;
    logic clk=0;always #10 clk=~clk;
    logic rst_n=0,midi_byte_valid=0,event_ready=0;
    logic [7:0] midi_byte=0;
    wire event_valid;
    performance_event_t event_data;
    wire [15:0] level,peak;
    wire [31:0] overflows,errors;
    midi_event_parser #(.SOURCE_ID(5),.CLK_HZ(50000000)) parser(
        .clk(clk),.rst_n(rst_n),.midi_byte(midi_byte),.midi_byte_valid(midi_byte_valid),
        .midi_byte_error(1'b0),.event_ready(event_ready),.event_valid(event_valid),
        .event_data(event_data),.event_fifo_level(level),.event_fifo_high_watermark(peak),
        .event_fifo_overflow_count(overflows),.parser_error_count(errors));
    wire accepted_valid=event_valid && event_ready;
    logic [3:0] occupied=15;
    logic [15:0] sources=16'h5655,channels=16'h2232;
    logic [127:0] generations=128'h00000004000000030000000200000001;
    logic sample_capture=0;
    logic [31:0] sample_id=0;
    wire [47:0] pitch,mod,snap_pitch,snap_mod;
    wire [19:0] ranges,snap_ranges;
    wire snapshot_valid,applied,invalid_range;
    wire [31:0] snap_id;
    wire [3:0] snap_occupied;
    wire [15:0] snap_sources,snap_channels;
    wire [127:0] snap_generations;
    performance_control_state state_bank(.clk(clk),.rst_n(rst_n),
        .accepted_valid(accepted_valid),.accepted_data(event_data),
        .slot_occupied(occupied),.slot_source_ids(sources),.slot_channels(channels),
        .slot_generations(generations),.sample_capture(sample_capture),.sample_id(sample_id),
        .slot_pitch_bend(pitch),.slot_modulation(mod),.slot_pitch_range(ranges),
        .snapshot_valid(snapshot_valid),.snapshot_id(snap_id),.snapshot_occupied(snap_occupied),
        .snapshot_sources(snap_sources),.snapshot_channels(snap_channels),
        .snapshot_generations(snap_generations),.snapshot_pitch_bend(snap_pitch),
        .snapshot_modulation(snap_mod),.snapshot_pitch_range(snap_ranges),
        .control_applied(applied),.invalid_range(invalid_range));
    integer counter=0,frame_wait=1041,checks=0,frames=0,controls=0,discrete=0;
    logic [11:0] oracle_pitch[0:255],oracle_mod[0:255];
    logic [47:0] expected_pitch=0,expected_mod=0;
    logic [19:0] expected_ranges={4{5'd2}};
    logic expected_valid=0;
    logic [31:0] expected_id=0;
    logic [3:0] expected_occupied=0;
    logic [15:0] expected_sources=0,expected_channels=0;
    logic [127:0] expected_generations=0;
    performance_event_t blocked_event;
    logic blocked=0;
    task automatic check(input logic ok,input string message);
        checks++;if(ok!==1'b1)$fatal(1,"MIDI/state link %s frame=%0d controls=%0d",message,frames,controls);
    endtask
    // This request generator is a TB only stand-in for formal frame_sample_req.
    always @(negedge clk)begin
        if(!rst_n)begin counter=0;frame_wait=1041;sample_capture=0;sample_id=0;end
        else begin
            sample_capture=counter==frame_wait-1;
            if(sample_capture)begin counter=0;sample_id++;frame_wait=frame_wait==1041?1042:1041;end
            else counter++;
        end
    end
    always @(posedge clk)begin
        if(!rst_n)begin
            for(integer i=0;i<256;i++)begin oracle_pitch[i]=0;oracle_mod[i]=0;end
            expected_pitch=0;expected_mod=0;expected_valid=0;expected_id=0;
            expected_occupied=0;expected_sources=0;expected_channels=0;expected_generations=0;blocked=0;
        end else begin
            if(blocked)check(event_valid && event_data===blocked_event,"presented event immutable until successful handshake");
            blocked=event_valid && !event_ready;blocked_event=event_data;
            if(accepted_valid)begin
                check(event_data.source_id==5,"source identity preserved");
                if(event_data.event_type==EVENT_PITCH_BEND)begin
                    oracle_pitch[{event_data.source_id,event_data.channel}]=event_data.control_value;controls++;
                end else if(event_data.event_type==EVENT_CONTROL_CHANGE && event_data.control_id==CTRL_MODULATION)begin
                    oracle_mod[{event_data.source_id,event_data.channel}]=event_data.control_value;controls++;
                end else discrete++;
            end
            if(sample_capture)begin
                frames++;expected_valid=1;expected_id=sample_id;expected_occupied=occupied;
                expected_sources=sources;expected_channels=channels;expected_generations=generations;
                for(integer lane=0;lane<4;lane++)begin
                    expected_pitch[12*lane+:12]=occupied[lane]?oracle_pitch[{sources[4*lane+:4],channels[4*lane+:4]}]:0;
                    expected_mod[12*lane+:12]=occupied[lane]?oracle_mod[{sources[4*lane+:4],channels[4*lane+:4]}]:0;
                end
            end
        end
        #1;
        check(snapshot_valid===expected_valid && snap_id===expected_id,"per-request snapshot valid and id");
        check(snap_pitch===expected_pitch && snap_mod===expected_mod && snap_ranges===expected_ranges,"snapshot accepted controls only");
        check(snap_occupied===expected_occupied && snap_sources===expected_sources && snap_channels===expected_channels && snap_generations===expected_generations,"snapshot slot tags stable including pre-steal generation");
        for(integer lane=0;lane<4;lane++)begin
            check(pitch[12*lane+:12]==(rst_n && occupied[lane]?oracle_pitch[{sources[4*lane+:4],channels[4*lane+:4]}]:0),"live pitch query by identity");
            check(mod[12*lane+:12]==(rst_n && occupied[lane]?oracle_mod[{sources[4*lane+:4],channels[4*lane+:4]}]:0),"live modulation query by identity");
        end
        check(ranges=={4{5'd2}} && !invalid_range,"parser does not invent pitch-range event");
    end
    task automatic byte_in(input logic [7:0] value);
        @(negedge clk);midi_byte=value;midi_byte_valid=1;
        @(negedge clk);midi_byte_valid=0;repeat(2)@(negedge clk);
    endtask
    task automatic message(input logic [7:0] status,data1,data2);
        byte_in(status);byte_in(data1);byte_in(data2);
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        message(8'he2,127,127);repeat(4)@(negedge clk);
        check(event_valid && event_data.control_value==2047,"pitch presented but not acknowledged");
        message(8'he2,0,0);message(8'h92,60,100);message(8'hb2,64,127);
        repeat(2000)@(negedge clk);
        check(pitch==0 && snap_pitch==0 && controls==0,"unaccepted presented/pending controls cannot write state");
        event_ready=1;repeat(4)@(negedge clk);
        check(pitch[11:0]==2047 && pitch[47:36]==2047 && pitch[35:24]==0,"accepted first pitch affects matching source/channel slots only");
        repeat(51000)@(negedge clk);
        check($signed(pitch[11:0])==-2048 && controls==2 && discrete==2,"latest pitch arrives after discrete Note/CC64 without dropped discrete messages");
        message(8'hb2,1,127);message(8'he3,0,64);repeat(105000)@(negedge clk);
        check(mod[11:0]==4095 && mod[47:36]==4095 && mod[35:24]==0 && mod[23:12]==0,"mod query source/channel isolated");
        check(pitch[23:12]==0,"pitch center exactly zero");
        @(negedge clk);sources[3:0]=6;generations[31:0]=99;
        check(snap_generations[31:0]==1,"old generation snapshot remains until next request");
        repeat(1100)@(negedge clk);
        check(pitch[11:0]==0 && snap_pitch[11:0]==0 && snap_generations[31:0]==99,"stolen lane rebinds to new identity at next sample");
        // Query occupied held/Release state is an M2 router contract; no LFO.
        message(8'hb2,1,127);repeat(51000)@(negedge clk);
        check(controls==4,"duplicate CC1 not emitted after delivery");
        event_ready=0;message(8'he2,127,127);repeat(4)@(negedge clk);
        rst_n=0;repeat(4)@(negedge clk);rst_n=1;event_ready=1;repeat(2000)@(negedge clk);
        check(!event_valid && pitch==0 && mod==0 && snap_pitch==0 && snap_mod==0,"reset flushes parser pending/locked and M2 accepted state");
        check(overflows==0 && errors==0 && level==0,"clean parser counters and FIFO");
        check(frames>100 && controls==4 && discrete==2,"nonvacuous real-rate sampling");
        $display("PASS midi_controls_state_link checks=%0d frames=%0d controls=%0d discrete=%0d",checks,frames,controls,discrete);$finish;
    end
    initial begin #10000000;$fatal(1,"MIDI control state link timeout");end
endmodule
