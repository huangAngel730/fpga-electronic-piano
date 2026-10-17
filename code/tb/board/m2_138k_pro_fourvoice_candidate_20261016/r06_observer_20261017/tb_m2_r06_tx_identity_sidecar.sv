// M2 R6-2 candidate unit self-check. NOT RUN: exact HDL admission pending.
// Compile inputs: frozen pcm_result_hold.sv, frozen pcm_frame_buffer.sv,
// m2_r06_tx_identity_sidecar.sv and this file. No board/PLL/ROM required.
// This manually drives a request window. It does not claim to test the
// adapter's dispatched gate, actual I2S pins, physical timing or a Pro board.
// No production hierarchy reads or hierarchical state writes are used.
`timescale 1ns/1ps
module tb_m2_r06_tx_identity_sidecar;
    logic clk = 1'b0;
    logic rst_n = 1'b1;
    logic frame_tick = 1'b0;
    logic result_valid = 1'b0;
    logic [31:0] result_id = 32'd0;
    logic [1:0] result_clip_mask = 2'b00;
    logic signed [23:0] result_left = 24'sd0;
    logic signed [23:0] result_right = 24'sd0;
    logic inject_frame_commit = 1'b0;

    wire result_ready, pcm_valid, pcm_ready, pcm_clip_any;
    wire [31:0] pcm_req_id;
    wire signed [23:0] pcm_left, pcm_right;
    wire sample_req, pending_valid;
    wire [31:0] sample_req_id;
    wire signed [23:0] play_left, play_right;
    wire [31:0] frame_count, request_count, commit_count, underrun_count;
    wire actual_commit = pcm_valid && pcm_ready;
    wire observed_commit = actual_commit || inject_frame_commit;

    pcm_result_hold u_result_hold (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick),
        .calc_ready(1'b1), .current_req_id(sample_req_id),
        .result_valid(result_valid), .result_ready(result_ready),
        .result_req_id(result_id), .result_left(result_left),
        .result_right(result_right), .result_clip_any(|result_clip_mask),
        .pcm_valid(pcm_valid), .pcm_ready(pcm_ready),
        .pcm_req_id(pcm_req_id), .pcm_left(pcm_left),
        .pcm_right(pcm_right), .pcm_clip_any(pcm_clip_any)
    );

    pcm_frame_buffer u_frame_buffer (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick),
        .calc_ready(1'b1), .sample_req(sample_req),
        .sample_req_id(sample_req_id), .pcm_valid(pcm_valid),
        .pcm_ready(pcm_ready), .pcm_req_id(pcm_req_id),
        .pcm_left(pcm_left), .pcm_right(pcm_right),
        .play_left(play_left), .play_right(play_right),
        .pending_valid(pending_valid), .audio_frame_count(frame_count),
        .pcm_request_count(request_count), .pcm_commit_count(commit_count),
        .audio_underrun(underrun_count)
    );

    wire tx_sample_valid, tx_metadata_valid, tx_req_id_valid;
    wire [31:0] tx_frame_id, tx_req_id;
    wire [1:0] tx_clip_mask;
    wire tx_clip_any, tx_hold, tx_startup_zero;
    wire signed [23:0] tx_left, tx_right;
    wire metadata_error, frame_id_overflow;

    m2_r06_tx_identity_sidecar u_sidecar (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick),
        .tx_valid(1'b1), .result_valid(result_valid),
        .result_ready(result_ready), .result_id(result_id),
        .result_clip_mask(result_clip_mask), .commit_pulse(observed_commit),
        .commit_id(pcm_req_id), .commit_left(pcm_left),
        .commit_right(pcm_right), .buffer_pending_valid(pending_valid),
        .play_left(play_left), .play_right(play_right),
        .tx_sample_valid(tx_sample_valid), .tx_metadata_valid(tx_metadata_valid),
        .tx_req_id_valid(tx_req_id_valid), .tx_frame_id(tx_frame_id),
        .tx_req_id(tx_req_id), .tx_clip_mask(tx_clip_mask),
        .tx_clip_any(tx_clip_any), .tx_hold(tx_hold),
        .tx_startup_zero(tx_startup_zero), .tx_left(tx_left),
        .tx_right(tx_right), .metadata_error(metadata_error),
        .frame_id_overflow(frame_id_overflow)
    );

    integer checks = 0;
    integer cycles = 0;

    task automatic must(input logic condition, input string message);
        begin
            checks = checks + 1;
            if (condition !== 1'b1) begin
                $display("FAIL cycle=%0d: %s", cycles, message);
                $fatal(1, "M2_R06_SIDECAR_SELFTEST_FAIL");
            end
        end
    endtask

    // Drive inputs only while clk is low. Check combinational PRE_NBA values
    // before the active edge, then allow both frozen modules' NBA updates.
    task automatic cycle_check(
        input string label,
        input logic expected_ready,
        input logic expected_commit,
        input logic expected_pending,
        input logic expected_sample,
        input logic expected_metadata,
        input logic expected_identity,
        input logic [31:0] expected_id,
        input logic [1:0] expected_clip,
        input logic expected_hold,
        input logic expected_startup,
        input logic [31:0] expected_ordinal,
        input logic signed [23:0] expected_left,
        input logic signed [23:0] expected_right,
        input logic expected_error
    );
        begin
            #2;
            must(clk === 1'b0, {label, ": clock-low setup"});
            must(result_ready === expected_ready, {label, ": result ready"});
            must(actual_commit === expected_commit, {label, ": actual commit"});
            must(pending_valid === expected_pending, {label, ": buffer pending"});
            must(tx_sample_valid === expected_sample, {label, ": TX adoption"});
            must(tx_metadata_valid === expected_metadata, {label, ": metadata valid"});
            must(tx_req_id_valid === expected_identity, {label, ": identity valid"});
            if (expected_identity)
                must(tx_req_id === expected_id, {label, ": request identity"});
            must(tx_clip_mask === expected_clip, {label, ": saved dual clip"});
            must(tx_clip_any === (|expected_clip), {label, ": clip OR"});
            must(tx_hold === expected_hold, {label, ": HOLD"});
            must(tx_startup_zero === expected_startup, {label, ": startup zero"});
            must(tx_frame_id === expected_ordinal, {label, ": independent ordinal"});
            must(tx_left === expected_left, {label, ": actual left PCM"});
            must(tx_right === expected_right, {label, ": actual right PCM"});
            must(metadata_error === expected_error, {label, ": metadata diagnostic"});
            must(frame_id_overflow === 1'b0, {label, ": no ordinal overflow"});
            #3 clk = 1'b1;
            #1 clk = 1'b0;
            #1;
            cycles = cycles + 1;
        end
    endtask

    task automatic assert_reset;
        begin
            frame_tick = 1'b0;
            result_valid = 1'b0;
            inject_frame_commit = 1'b0;
            // A non-clock assertion checks the async path without a DUT
            // hierarchy probe. Epoch accounting belongs to the capture log.
            #1 rst_n = 1'b0;
            #1;
            must(pending_valid === 1'b0, "async reset invalidates pending");
            must(pcm_valid === 1'b0, "async reset invalidates result hold");
            must(tx_sample_valid === 1'b0, "async reset masks TX adoption");
            must(tx_metadata_valid === 1'b0, "async reset invalidates metadata");
            must(tx_req_id_valid === 1'b0, "async reset invalidates identity");
            must(tx_left === 24'sd0 && tx_right === 24'sd0,
                 "async reset clears PCM without a clock edge");
            must(metadata_error === 1'b0, "async reset clears diagnostic");
            must(tx_frame_id === 32'd0, "async reset restarts ordinal");
            #1 rst_n = 1'b1;
        end
    endtask

    initial begin
        // Safety watchdog only; this source has not been compiled or run.
        #20000;
        $fatal(1, "M2_R06_SIDECAR_SELFTEST_TIMEOUT");
    end

    initial begin
        assert_reset();
        frame_tick = 1'b1;
        cycle_check("startup FRAME", 0,0,0, 1,1,0, 0,2'b00,0,1,0, 0,0,0);

        frame_tick = 1'b0;
        result_valid = 1'b1;
        result_id = 32'd0; // Current generation is 1: stale ID must be held off.
        result_clip_mask = 2'b11;
        result_left = 24'sd777;
        result_right = -24'sd888;
        cycle_check("wrong ID backpressure", 0,0,0, 0,0,0, 0,2'b00,0,0,1, 0,0,0);

        result_id = 32'd1;
        result_clip_mask = 2'b01;
        result_left = 24'sd1234;
        result_right = -24'sd5678;
        cycle_check("accept result left clip", 1,0,0, 0,0,0, 0,2'b00,0,0,1, 0,0,0);

        // Change every upstream field before commit. The committed PCM and
        // dual clip must come from the previously accepted result, never here.
        result_valid = 1'b0;
        result_id = 32'd999;
        result_clip_mask = 2'b10;
        result_left = -24'sd2222;
        result_right = 24'sd3333;
        cycle_check("commit saved result only", 0,1,0, 0,0,0, 0,2'b00,0,0,1, 0,0,0);
        must(pcm_req_id === 32'd1 && pcm_left === 24'sd1234 &&
             pcm_right === -24'sd5678, "hold tuple survives live-bus changes");

        result_valid = 1'b1;
        result_id = 32'd1;
        cycle_check("occupied pending rejects duplicate", 0,0,1,
                    0,0,0, 0,2'b01,0,0,1, 24'sd1234,-24'sd5678,0);
        result_valid = 1'b0;
        frame_tick = 1'b1;
        cycle_check("pending becomes actual TX", 0,0,1,
                    1,1,1, 1,2'b01,0,0,1, 24'sd1234,-24'sd5678,0);

        cycle_check("HOLD inherits ID and clip", 0,0,0,
                    1,1,1, 1,2'b01,1,0,2, 24'sd1234,-24'sd5678,0);

        frame_tick = 1'b0;
        result_valid = 1'b1;
        result_id = 32'd2; // Consecutive FRAME above made current ID 3.
        cycle_check("older generation remains backpressured", 0,0,0,
                    0,0,0, 0,2'b01,0,0,3, 24'sd1234,-24'sd5678,0);
        result_id = 32'd3;
        result_clip_mask = 2'b10;
        result_left = 24'sd1234;
        result_right = -24'sd5678; // Deliberately the same PCM as request 1.
        cycle_check("same PCM different ID result", 1,0,0,
                    0,0,0, 0,2'b01,0,0,3, 24'sd1234,-24'sd5678,0);
        result_valid = 1'b0;
        result_clip_mask = 2'b00;
        cycle_check("second saved clip commit", 0,1,0,
                    0,0,0, 0,2'b01,0,0,3, 24'sd1234,-24'sd5678,0);
        frame_tick = 1'b1;
        cycle_check("same PCM uses new identity", 0,0,1,
                    1,1,1, 3,2'b10,0,0,3, 24'sd1234,-24'sd5678,0);
        cycle_check("second identity HOLD", 0,0,0,
                    1,1,1, 3,2'b10,1,0,4, 24'sd1234,-24'sd5678,0);

        frame_tick = 1'b0;
        result_valid = 1'b1;
        result_id = 32'd5;
        result_clip_mask = 2'b11;
        result_left = 24'sh800000;
        result_right = 24'sh7fffff;
        cycle_check("both clipped full-scale result", 1,0,0,
                    0,0,0, 0,2'b10,0,0,5, 24'sd1234,-24'sd5678,0);
        result_valid = 1'b0;
        result_clip_mask = 2'b01;
        cycle_check("both clipped full-scale commit", 0,1,0,
                    0,0,0, 0,2'b10,0,0,5, 24'sd1234,-24'sd5678,0);
        frame_tick = 1'b1;
        cycle_check("both clip bits reach TX", 0,0,1,
                    1,1,1, 5,2'b11,0,0,5, 24'sh800000,24'sh7fffff,0);

        // Legal modules deassert ready on FRAME, even with matching result.
        result_valid = 1'b1;
        result_id = 32'd6;
        result_clip_mask = 2'b00;
        cycle_check("FRAME rejects same-edge result", 0,0,0,
                    1,1,1, 5,2'b11,1,0,6, 24'sh800000,24'sh7fffff,0);

        frame_tick = 1'b0;
        result_id = 32'd7;
        result_left = 24'sd100;
        result_right = 24'sd200;
        cycle_check("result immediately before FRAME", 1,0,0,
                    0,0,0, 0,2'b11,0,0,7, 24'sh800000,24'sh7fffff,0);
        frame_tick = 1'b1;
        result_valid = 1'b0;
        cycle_check("FRAME blocks candidate commit", 0,0,0,
                    1,1,1, 5,2'b11,1,0,7, 24'sh800000,24'sh7fffff,0);

        frame_tick = 1'b0;
        result_id = 32'd8;
        result_valid = 1'b1;
        result_clip_mask = 2'b01;
        cycle_check("new generation after expiration", 1,0,0,
                    0,0,0, 0,2'b11,0,0,8, 24'sh800000,24'sh7fffff,0);
        result_valid = 1'b0;
        result_clip_mask = 2'b10;
        cycle_check("pending before async reset", 0,1,0,
                    0,0,0, 0,2'b11,0,0,8, 24'sh800000,24'sh7fffff,0);
        must(pending_valid === 1'b1, "committed pending exists before reset");
        assert_reset();
        frame_tick = 1'b1;
        cycle_check("restart has no stale held identity", 0,0,0,
                    1,1,0, 0,2'b00,0,1,0, 0,0,0);

        frame_tick = 1'b0;
        result_valid = 1'b1;
        result_id = 32'd1;
        result_clip_mask = 2'b11;
        cycle_check("result hold before async reset", 1,0,0,
                    0,0,0, 0,2'b00,0,0,1, 0,0,0);
        must(pcm_valid === 1'b1, "accepted result exists before reset");
        assert_reset();
        frame_tick = 1'b1;
        cycle_check("reset invalidates uncommitted result", 0,0,0,
                    1,1,0, 0,2'b00,0,1,0, 0,0,0);

        // Fault injection is into a public sidecar input only. The frozen
        // buffer is still not committing; impossible labels must be invalid.
        inject_frame_commit = 1'b1;
        cycle_check("diagnose illegal FRAME commit", 0,0,0,
                    1,0,0, 0,2'b00,0,1,1, 0,0,1);
        inject_frame_commit = 1'b0;
        cycle_check("diagnostic is sticky", 0,0,0,
                    1,0,0, 0,2'b00,0,1,2, 0,0,1);
        assert_reset();
        frame_tick = 1'b1;
        cycle_check("reset recovers diagnostic", 0,0,0,
                    1,1,0, 0,2'b00,0,1,0, 0,0,0);

        // Ordinal wrap cannot be reached here without 2**32 adoptions;
        // no hierarchy force/write is used to manufacture that coverage.
        $display("PASS M2_R06_SIDECAR_SELFTEST cycles=%0d checks=%0d", cycles, checks);
        $finish;
    end
endmodule
