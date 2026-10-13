// T052 P0-1 static successor. Compilation and simulation require M2 approval.
`timescale 1ns/1ps

module tb_t052_control_128_v2;
    localparam integer CONTROL_WIDTH = 170;
    localparam CONTROL_FILE = "controls_128.hex";
    localparam ROM_FILE = "readonly/sine_1024_8192.mem";

    logic clk;
    logic rst_n;
    logic frame_tick;
    logic cancel;
    logic sample_req;
    logic [31:0] req_id;
    logic enable;
    logic [3:0] voice_enable_mask;
    logic [31:0] fcw_lane0, fcw_lane1, fcw_lane2, fcw_lane3;
    logic result_ready;
    logic calc_ready;
    logic result_valid;
    logic [31:0] result_req_id;
    logic [95:0] voices_left, voices_right;
    logic [31:0] active_voice_count;
    logic clip_any;
    logic [CONTROL_WIDTH-1:0] controls [0:127];
    integer driver_index;
    integer observer_cycle;

    task automatic apply_control(input logic [CONTROL_WIDTH-1:0] word);
        begin
            {rst_n, frame_tick, cancel, sample_req, req_id, enable,
             voice_enable_mask, fcw_lane0, fcw_lane1, fcw_lane2,
             fcw_lane3, result_ready} = word;
        end
    endtask

    t052_polyphony_test_source #(.ROM_FILE(ROM_FILE)) dut (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick),
        .sample_req(sample_req), .calc_ready(calc_ready), .req_id(req_id),
        .enable(enable), .voice_enable_mask(voice_enable_mask),
        .fcw_lane0(fcw_lane0), .fcw_lane1(fcw_lane1),
        .fcw_lane2(fcw_lane2), .fcw_lane3(fcw_lane3), .cancel(cancel),
        .result_valid(result_valid), .result_ready(result_ready),
        .result_req_id(result_req_id), .voices_left(voices_left),
        .voices_right(voices_right), .active_voice_count(active_voice_count),
        .clip_any(clip_any)
    );

    t052_public_observer_v2 observer (
        .clk(clk), .cycle(observer_cycle), .rst_n(rst_n),
        .frame_tick(frame_tick), .cancel(cancel), .sample_req(sample_req),
        .req_id(req_id), .enable(enable), .voice_enable_mask(voice_enable_mask),
        .fcw_lane0(fcw_lane0), .fcw_lane1(fcw_lane1),
        .fcw_lane2(fcw_lane2), .fcw_lane3(fcw_lane3),
        .result_ready(result_ready), .calc_ready(calc_ready),
        .result_valid(result_valid), .result_req_id(result_req_id)
    );

    // SCHEDULE_BEGIN: audited by the bounded software source-schedule checker.
    initial begin
        $timeformat(-9, 0, "", 0);
        clk = 1'b0;
        driver_index = 0;
        observer_cycle = 0;
        $readmemh(CONTROL_FILE, controls);
        apply_control(controls[driver_index]);
        forever #10 clk = ~clk;
    end

    // A blocking increment belongs to the driver only. At time20 row1 is
    // stable for posedge30; the observer's NBA counter cannot skip row1.
    always @(negedge clk) begin
        if (driver_index < 127) begin
            driver_index = driver_index + 1;
            apply_control(controls[driver_index]);
        end
    end

    // cycle remains N in the active region while the observer samples N.
    always @(posedge clk) begin
        if (observer_cycle == 127) begin
            #1 $finish(0);
        end else begin
            observer_cycle <= observer_cycle + 1;
        end
    end
    // SCHEDULE_END

    initial begin
        #3000;
        $fatal(1, "T052_CONTROL_WINDOW_TIMEOUT");
    end
endmodule
