// Static preparation only. No compile/run authorization is conveyed by this TB.
`timescale 1ns/1ps
module tb_t052_long;
    localparam integer LAST_CYCLE = 8536335;
    logic clk, rst_n, frame_tick, cancel, sample_req, enable, result_ready;
    logic [31:0] req_id, fcw_lane0, fcw_lane1, fcw_lane2, fcw_lane3;
    logic [3:0] voice_enable_mask;
    logic calc_ready, result_valid, clip_any;
    logic [31:0] result_req_id, active_voice_count;
    logic [95:0] voices_left, voices_right;
    logic [169:0] control_word;
    integer driver_index, cycle, input_file, status;

    task automatic apply_next;
        begin
            status = $fscanf(input_file, "%h\n", control_word);
            if (status != 1 || $isunknown(control_word))
                $fatal(1, "CONTROL_INPUT_MISSING_OR_UNKNOWN");
            {rst_n, frame_tick, cancel, sample_req, req_id, enable,
             voice_enable_mask, fcw_lane0, fcw_lane1, fcw_lane2,
             fcw_lane3, result_ready} = control_word;
        end
    endtask

    t052_polyphony_test_source #(.ROM_FILE("readonly/sine_1024_8192.mem")) dut (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick), .cancel(cancel),
        .sample_req(sample_req), .req_id(req_id), .enable(enable),
        .voice_enable_mask(voice_enable_mask), .fcw_lane0(fcw_lane0),
        .fcw_lane1(fcw_lane1), .fcw_lane2(fcw_lane2), .fcw_lane3(fcw_lane3),
        .result_ready(result_ready), .calc_ready(calc_ready),
        .result_valid(result_valid), .result_req_id(result_req_id),
        .voices_left(voices_left), .voices_right(voices_right),
        .active_voice_count(active_voice_count), .clip_any(clip_any)
    );
    t052_long_observer observer (.*);

    // DRIVER_BEGIN: row0 at t0, then one row per positive-time negedge.
    initial begin
        clk = 0;
        driver_index = 0;
        cycle = 0;
        input_file = $fopen("controls.hex", "r");
        if (!input_file) $fatal(1, "CONTROL_OPEN_FAILED");
        apply_next();
        forever #10 clk = ~clk;
    end
    always @(negedge clk) begin
        // X -> 0 at initialization may trigger this block in the t0 region.
        // A delta delay (#0) would still be t0; explicitly exclude time zero.
        if (($time > 0) && (driver_index < LAST_CYCLE)) begin
            driver_index = driver_index + 1;
            apply_next();
        end
    end
    always @(posedge clk) begin
        if (cycle == LAST_CYCLE) begin
            #1;
            status = $fscanf(input_file, "%h", control_word);
            if (status != -1) $fatal(1, "EXTRA_CONTROL_INPUT");
            $fclose(input_file);
            $display("T052_LONG_CAPTURE_FINISHED_NOT_ACCEPTANCE_PASS");
            $finish(0);
        end else cycle <= cycle + 1;
    end
    // DRIVER_END
    initial begin
        #170726720;
        $fatal(1, "T052_LONG_SIM_TIME_LIMIT");
    end
endmodule
