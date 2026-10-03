// Simulation only. Frozen 3d6430e full-parser miter plus an independent linear
// selector oracle. Backdoor forces belong ONLY to the stopped-clock boundary
// instance; live DUTs receive identical real byte/ready/reset inputs.
`timescale 1ns / 1ps
module tb_midi_scheduler_equivalence;
    import audio_defs_pkg::*;
    logic clk = 0, rst_n = 0;
    always #10 clk = ~clk;
    logic [7:0] byte_data = 0;
    logic byte_valid = 0, byte_error = 0, ready = 0;
    logic trace_enabled = 0;
    logic test_passed = 0;
    integer trace_cycles = 0, selector_cases = 0;
    integer trace_checks [0:3];
    integer received [0:3], controls [0:3], stalls [0:3];
    integer reset_checks = 0;
    wire [3:0] valid_dut, valid_ref;
    performance_event_t data_dut [0:3], data_ref [0:3];
    wire [15:0] level_dut [0:3], level_ref [0:3];
    wire [15:0] peak_dut [0:3], peak_ref [0:3];
    wire [31:0] overflow_dut [0:3], overflow_ref [0:3];
    wire [31:0] errors_dut [0:3], errors_ref [0:3];

    generate
        for (genvar lane = 0; lane < 4; lane++) begin : g_miter
            localparam integer DEPTH = (lane == 0) ? 1 : ((lane == 1) ? 8 : ((lane == 2) ? 16 : 3));
            localparam integer BURST = (lane == 0) ? 1 : ((lane == 3) ? 3 : 8);
            localparam integer HZ = (lane == 2) ? 50_000_000 : ((lane == 3) ? 1 : 64_000);
            localparam integer INTERVAL = (HZ + 999) / 1000;
            performance_event_t held;
            logic was_stalled = 0;
            integer last_control = -INTERVAL;
            integer lane_cycle = 0;
            midi_event_parser #(.LOCAL_FIFO_DEPTH(DEPTH), .SOURCE_ID(4'(lane+4)),
                .CLK_HZ(HZ), .MAX_DISCRETE_BURST(BURST)) dut (
                .clk(clk), .rst_n(rst_n), .midi_byte(byte_data),
                .midi_byte_valid(byte_valid), .midi_byte_error(byte_error),
                .event_ready(ready), .event_valid(valid_dut[lane]), .event_data(data_dut[lane]),
                .event_fifo_level(level_dut[lane]), .event_fifo_high_watermark(peak_dut[lane]),
                .event_fifo_overflow_count(overflow_dut[lane]), .parser_error_count(errors_dut[lane]));
            midi_event_parser_frozen #(.LOCAL_FIFO_DEPTH(DEPTH), .SOURCE_ID(4'(lane+4)),
                .CLK_HZ(HZ), .MAX_DISCRETE_BURST(BURST)) reference (
                .clk(clk), .rst_n(rst_n), .midi_byte(byte_data),
                .midi_byte_valid(byte_valid), .midi_byte_error(byte_error),
                .event_ready(ready), .event_valid(valid_ref[lane]), .event_data(data_ref[lane]),
                .event_fifo_level(level_ref[lane]), .event_fifo_high_watermark(peak_ref[lane]),
                .event_fifo_overflow_count(overflow_ref[lane]), .parser_error_count(errors_ref[lane]));
            always @(posedge clk) begin
                if (trace_enabled) begin
                    lane_cycle++;
                    if (!rst_n) begin
                        was_stalled = 0;
                        last_control = lane_cycle - INTERVAL;
                    end else begin
                        if (was_stalled && (!valid_dut[lane] || data_dut[lane] !== held))
                            $fatal(1, "stalled payload changed lane=%0d", lane);
                        was_stalled = valid_dut[lane] && !ready;
                        held = data_dut[lane];
                        if (was_stalled) stalls[lane]++;
                        if (valid_dut[lane] && ready) begin
                            received[lane]++;
                            if (data_dut[lane].event_type == EVENT_PITCH_BEND ||
                                (data_dut[lane].event_type == EVENT_CONTROL_CHANGE &&
                                 data_dut[lane].control_id == CTRL_MODULATION)) begin
                                if (lane_cycle - last_control < INTERVAL)
                                    $fatal(1, "rate violated lane=%0d", lane);
                                last_control = lane_cycle;
                                controls[lane]++;
                            end
                        end
                    end
                    #1;
                    if ({valid_dut[lane], data_dut[lane], level_dut[lane], peak_dut[lane],
                         overflow_dut[lane], errors_dut[lane]} !==
                        {valid_ref[lane], data_ref[lane], level_ref[lane], peak_ref[lane],
                         overflow_ref[lane], errors_ref[lane]})
                        $fatal(1, "parser port miter mismatch lane=%0d cycle=%0d", lane, trace_cycles);
                    if ({dut.control_pending, dut.control_locked, dut.locked_event,
                         dut.locked_index, dut.round_robin_index, dut.control_cooldown,
                         dut.discrete_burst_count, dut.mod_sent_valid} !==
                        {reference.control_pending, reference.control_locked, reference.locked_event,
                         reference.locked_index, reference.round_robin_index, reference.control_cooldown,
                         reference.discrete_burst_count, reference.mod_sent_valid})
                        $fatal(1, "transport state miter mismatch lane=%0d cycle=%0d", lane, trace_cycles);
                    trace_checks[lane]++;
                end
            end
        end
    endgenerate
    always @(posedge clk) if (trace_enabled) trace_cycles++;

    logic boundary_clk = 0;
    logic [31:0] fixture_pending = 0;
    logic [4:0] fixture_rr = 0;
    logic fixture_active = 0, fixture_locked = 0;
    logic [4:0] fixture_locked_index = 0;
    performance_event_t fixture_event, fixture_held;
    midi_event_parser boundary (
        .clk(boundary_clk), .rst_n(1'b0), .midi_byte(8'd0), .midi_byte_valid(1'b0),
        .midi_byte_error(1'b0), .event_ready(1'b0), .event_valid(), .event_data(),
        .event_fifo_level(), .event_fifo_high_watermark(),
        .event_fifo_overflow_count(), .parser_error_count());

    generate
        for (genvar value_slot = 0; value_slot < 32; value_slot++) begin : g_boundary_value
            // Distinct old values also detect wrong first/second payload muxes.
            initial begin
                #3;
                force boundary.pending_value[value_slot] = 12'(256 + 17*value_slot);
            end
        end
    endgenerate

    task automatic selector_check;
        logic [31:0] expected_pending;
        logic expected_valid, keep;
        logic [4:0] index, expected_index, updated_index;
        logic [11:0] expected_value;
        expected_pending = fixture_pending;
        updated_index = {fixture_event.channel, fixture_event.control_id == CTRL_MODULATION};
        keep = !(updated_index[0] &&
            ((fixture_locked && fixture_locked_index == updated_index) ?
             fixture_event.control_value == fixture_held.control_value :
             fixture_event.control_value == 0));
        if (fixture_active) expected_pending[updated_index] = keep;
        expected_valid = 0; expected_index = 0; expected_value = 0;
        // Intentionally independent linear oracle, not the candidate tree.
        for (integer offset = 0; offset < 32; offset++) begin
            index = fixture_rr + 5'(offset);
            if (!expected_valid && expected_pending[index]) begin
                expected_valid = 1; expected_index = index;
                expected_value = (fixture_active && updated_index == index) ?
                    fixture_event.control_value : 12'(256 + 17*index);
            end
        end
        #1;
        selector_cases++;
        if ({boundary.selected_valid, boundary.selected_index, boundary.selected_value} !==
            {expected_valid, expected_index, expected_value})
            $fatal(1, "selector oracle mismatch case=%0d rr=%0d pending=%h update=%0d active=%0d got=%b/%0d/%h expected=%b/%0d/%h",
                selector_cases, fixture_rr, fixture_pending, updated_index, fixture_active,
                boundary.selected_valid, boundary.selected_index, boundary.selected_value,
                expected_valid, expected_index, expected_value);
    endtask

    logic [31:0] rng = 32'h7d395aa1;
    task automatic random_next;
        rng = rng ^ (rng << 13); rng = rng ^ (rng >> 17); rng = rng ^ (rng << 5);
    endtask

    task automatic step(input logic [7:0] b, input logic v, input logic e, input logic r);
        @(negedge clk); byte_data = b; byte_valid = v; byte_error = e; ready = r;
        @(posedge clk); #2;
    endtask
    task automatic reset_trace;
        @(negedge clk); rst_n = 0; byte_valid = 0; ready = 0;
        repeat (3) step(0, 0, 0, 0);
        reset_checks++;
        @(negedge clk); rst_n = 1;
    endtask
    task automatic message(input logic [7:0] status, input logic [6:0] a,
                           input logic [6:0] b, input logic r);
        step(status, 1, 0, r); step({1'b0,a}, 1, 0, r);
        if (status[7:4] != 4'hC && status[7:4] != 4'hD) step({1'b0,b}, 1, 0, r);
    endtask

    initial begin
        for (integer lane = 0; lane < 4; lane++) begin
            trace_checks[lane] = 0; received[lane] = 0; controls[lane] = 0; stalls[lane] = 0;
        end
        fixture_event = '0; fixture_held = '0;
        #1; boundary_clk = 1; #1; boundary_clk = 0;
        force boundary.control_pending = fixture_pending;
        force boundary.round_robin_index = fixture_rr;
        force boundary.parsed_event_valid = fixture_active;
        force boundary.parsed_event_data = fixture_event;
        force boundary.mod_sent_valid = 16'hFFFF;
        force boundary.control_locked = fixture_locked;
        force boundary.locked_index = fixture_locked_index;
        force boundary.locked_event = fixture_held;
        #2;
        for (integer rr = 0; rr < 32; rr++) begin
            fixture_rr = 5'(rr);
            for (integer pattern = 0; pattern < 130; pattern++) begin
                if (pattern == 0) fixture_pending = 0;
                else if (pattern == 1) fixture_pending = '1;
                else if (pattern < 34) fixture_pending = 32'd1 << (pattern-2);
                else if (pattern < 66) fixture_pending =
                    (32'd1 << (pattern-34)) | (32'd1 << ((pattern-33)%32));
                else begin random_next(); fixture_pending = rng; end
                for (integer update = 0; update < 32; update++) begin
                    for (integer action = 0; action < 3; action++) begin
                        fixture_active = action != 0;
                        fixture_event = '0;
                        fixture_event.event_type = update[0] ? EVENT_CONTROL_CHANGE : EVENT_PITCH_BEND;
                        fixture_event.channel = 4'(update/2);
                        fixture_event.control_id = update[0] ? CTRL_MODULATION : CTRL_PITCH_BEND;
                        fixture_event.control_value = (action == 2) ? 12'd0 : 12'hA53;
                        selector_check();
                    end
                end
            end
            // In-flight CC1 value differs from acknowledged history. Cancelling
            // against the former, not the latter, must also choose correctly.
            fixture_pending = '1; fixture_locked = 1; fixture_held.control_value = 12'd5;
            for (integer update = 1; update < 32; update += 2) begin
                fixture_locked_index = 5'(update); fixture_active = 1;
                fixture_event = '0; fixture_event.event_type = EVENT_CONTROL_CHANGE;
                fixture_event.channel = 4'(update/2); fixture_event.control_id = CTRL_MODULATION;
                fixture_event.control_value = 5; selector_check();
                fixture_event.control_value = 0; selector_check();
            end
            fixture_locked = 0;
        end
        $display("PASS selector oracle cases=%0d all_rr_starts=32", selector_cases);

        trace_enabled = 1;
        reset_trace();
        for (integer channel = 0; channel < 16; channel++) begin
            message(8'hE0 | 8'(channel), 7'd63, 7'd67, 0);
            message(8'hB0 | 8'(channel), 7'd1, 7'd64, 0);
            message(8'h90 | 8'(channel), 7'(60+channel), 7'd100, 0);
            message(8'hC0 | 8'(channel), 7'(channel*7), 0, 0);
            message(8'hB0 | 8'(channel), 7'd64, 7'd127, 0);
        end
        // Includes 50MHz/1kHz drainage, with immutable stalled events first.
        repeat (256) step(8'hF8, 1, 0, 0);
        repeat (1_650_000) step(0, 0, 0, 1);
        reset_trace();
        // Reproducible mixed byte stream, malformed/status/error/reset cases,
        // rapid control changes, FIFO overflow and successful simultaneous pop/push.
        for (integer iteration = 0; iteration < 12000; iteration++) begin
            random_next();
            case (rng[3:0])
                0,1: message(8'hE0 | {4'd0,rng[7:4]}, rng[14:8], rng[21:15], rng[24]);
                2,3: message(8'hB0 | {4'd0,rng[7:4]}, 1, rng[14:8], rng[24]);
                4,5: message(8'h90 | {4'd0,rng[7:4]}, rng[14:8], rng[21:15], rng[24]);
                6: message(8'h80 | {4'd0,rng[7:4]}, rng[14:8], 64, rng[24]);
                7: message(8'hB0 | {4'd0,rng[7:4]}, 64, rng[14:8], rng[24]);
                8: message(8'hC0 | {4'd0,rng[7:4]}, rng[14:8], 0, rng[24]);
                9: begin step(8'hF2, 1, 0, rng[24]); step(1, 1, 0, rng[24]); step(2, 1, 0, rng[24]); end
                10: begin step(8'hF0, 1, 0, rng[24]); step(3, 1, 0, rng[24]); step(8'hF7, 1, 0, rng[24]); end
                11: step(rng[7:0], 1, 1, rng[24]);
                12: step(8'hF8, 1, 0, rng[24]);
                13: step({1'b0,rng[6:0]}, 1, 0, rng[24]);
                14: message(8'hD0 | {4'd0,rng[7:4]}, rng[14:8], 0, rng[24]);
                15: step(0, 0, 0, rng[24]);
            endcase
            if (iteration % 997 == 0) reset_trace();
        end
        repeat (1_650_000) step(0, 0, 0, 1);
        for (integer lane = 0; lane < 4; lane++) begin
            if (trace_checks[lane] < 3_000_000 || received[lane] < 100 ||
                controls[lane] < 32 || stalls[lane] < 100)
                $fatal(1, "insufficient live trace coverage lane=%0d", lane);
            $display("PASS live miter lane=%0d cycles=%0d events=%0d controls=%0d stalled=%0d",
                lane, trace_checks[lane], received[lane], controls[lane], stalls[lane]);
        end
        if (reset_checks < 10) $fatal(1, "missing reset coverage");
        test_passed = 1;
        $display("PASS tb_midi_scheduler_equivalence selector_cases=%0d cycles=%0d resets=%0d", selector_cases, trace_cycles, reset_checks);
        $finish;
    end
    initial begin #100000000; $fatal(1, "scheduler equivalence timeout"); end
endmodule
