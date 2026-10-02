// Isolated scheduler test with EXPLICIT router stub, not allocator/CC64 proof.
// Uses actual formal ADSR and both actual oscillator modules.
`timescale 1ns/1ps
module tb_v3_bank_latency;
    logic clk=0;
    always #10 clk=~clk;
    logic rst_n=0,event_valid=0,frame_tick=0,sample_req=0,result_ready=0;
    logic [63:0] event_data=0;
    logic [31:0] request_id=0;
    wire event_ready,calc_ready,result_valid;
    wire [31:0] result_id,active;
    wire [63:0] envelopes,waves;
    wire [127:0] fcw;
    wire [3:0] occupied;
    wire [11:0] states;
    logic signed [15:0] expected [0:2047];
    integer advanced=0, checked=0, timeout_count, n;
    logic [63:0] held_waves;
    polyphonic_envelope_bank #(.PIANO_TIMBRE_ENABLE(1),
        .WAVE_ROM_FILE("source/baseline/piano_band_4x256_8191.mem")) dut (
        .clk(clk),.rst_n(rst_n),.event_valid(event_valid),.event_ready(event_ready),
        .event_data(event_data),.frame_tick(frame_tick),.sample_req(sample_req),
        .sample_req_id(request_id),.calc_ready(calc_ready),.result_valid(result_valid),
        .result_ready(result_ready),.result_req_id(result_id),.result_envelopes(envelopes),
        .result_waves(waves),.result_fcw(fcw),.result_occupied(occupied),
        .result_states(states),.active_voice_count(active)
    );
    always @(posedge clk) if(rst_n && dut.lane_tick) advanced=advanced+1;
    task automatic request;
        begin
            @(negedge clk);sample_req=1;request_id=request_id+1;
            @(negedge clk);sample_req=0;
        end
    endtask
    initial begin
        $readmemh("design/model_results/osc_note36.mem",expected);
        repeat(5) @(negedge clk);rst_n=1;
        @(negedge clk);event_valid=1;
        @(negedge clk);event_valid=0;
        repeat(8) @(negedge clk);
        for(n=0;n<128;n=n+1) begin
            request();
            if(n==20) begin
                timeout_count=0;
                while(!dut.lane_tick) begin
                    @(negedge clk);timeout_count=timeout_count+1;
                    if(timeout_count>100) $fatal(1,"cancel precondition timeout");
                end
                repeat(5) @(negedge clk);frame_tick=1;
                @(negedge clk);frame_tick=0;
                if(result_valid) $fatal(1,"cancel did not discard result");
                request(); // must wait guard internally, no second early tick
            end
            timeout_count=0;
            while(!result_valid) begin
                @(negedge clk);timeout_count=timeout_count+1;
                if(timeout_count>150) $fatal(1,"result timeout");
            end
            if(result_id!==request_id) $fatal(1,"stale result ID");
            if($signed(waves[15:0])!==expected[advanced-1])
                $fatal(1,"old/wrong sample advanced=%0d wave=%0d expected=%0d",advanced,$signed(waves[15:0]),expected[advanced-1]);
            held_waves=waves;
            repeat(5) begin
                @(negedge clk);
                if(!result_valid || waves!==held_waves) $fatal(1,"backpressure instability");
            end
            result_ready=1;
            @(negedge clk);result_ready=0;
            checked=checked+1;
        end
        if(advanced!=129 || checked!=128) $fatal(1,"advance/commit count");
        @(negedge clk);rst_n=0;
        @(negedge clk);if(result_valid) $fatal(1,"reset result_valid");
        $display("PASS V3 bank latency: 128 exact committed waves, 129 advances, one cancel, ID, backpressure, reset; ROUTER STUB ONLY");
        $finish;
    end
    initial begin #10000000;$fatal(1,"bank TB timeout");end
endmodule

module polyphonic_event_router (
    input logic clk,rst_n,sample_owner_ready,event_valid,
    output wire event_ready,
    input logic [63:0] event_data,
    input logic [3:0] release_done,
    output wire dispatch_busy,
    output logic [3:0] slot_note_on,
    output wire [3:0] slot_note_off,slot_occupied,slot_releasing,
    output wire [39:0] slot_velocity,
    output wire [127:0] slot_fcw,
    output wire [31:0] slot_notes,active_voice_count
);
    assign event_ready=sample_owner_ready;
    assign dispatch_busy=0;
    assign slot_note_off=0;
    assign slot_occupied=1;
    assign slot_releasing=0;
    assign slot_velocity={4{10'd900}};
    assign slot_fcw={4{32'd5852464}};
    assign slot_notes={4{8'd36}};
    assign active_voice_count=1;
    always_ff @(posedge clk or negedge rst_n)
        if(!rst_n) slot_note_on<=0;
        else slot_note_on<=event_valid && event_ready ? 4'b0001 : 4'b0000;
endmodule
