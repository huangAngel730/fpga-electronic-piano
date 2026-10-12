// Static preparation only. Do not compile or run without a new M2 approval.
// Drives the frozen 128-edge input plan independently of DUT outputs.
`timescale 1ns/1ps

module tb_t052_publication_control_128;
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
    logic [31:0] fcw_lane0;
    logic [31:0] fcw_lane1;
    logic [31:0] fcw_lane2;
    logic [31:0] fcw_lane3;
    logic result_ready;
    logic calc_ready;
    logic result_valid;
    logic [31:0] result_req_id;
    logic [95:0] voices_left;
    logic [95:0] voices_right;
    logic [31:0] active_voice_count;
    logic clip_any;
    logic [CONTROL_WIDTH-1:0] controls [0:127];
    integer cycle;

    task automatic apply_control(input logic [CONTROL_WIDTH-1:0] word);
        begin
            {rst_n, frame_tick, cancel, sample_req, req_id, enable,
             voice_enable_mask, fcw_lane0, fcw_lane1, fcw_lane2,
             fcw_lane3, result_ready} = word;
        end
    endtask

    t052_polyphony_test_source #(.ROM_FILE(ROM_FILE)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .frame_tick(frame_tick),
        .sample_req(sample_req),
        .calc_ready(calc_ready),
        .req_id(req_id),
        .enable(enable),
        .voice_enable_mask(voice_enable_mask),
        .fcw_lane0(fcw_lane0),
        .fcw_lane1(fcw_lane1),
        .fcw_lane2(fcw_lane2),
        .fcw_lane3(fcw_lane3),
        .cancel(cancel),
        .result_valid(result_valid),
        .result_ready(result_ready),
        .result_req_id(result_req_id),
        .voices_left(voices_left),
        .voices_right(voices_right),
        .active_voice_count(active_voice_count),
        .clip_any(clip_any)
    );

    t052_public_observer observer (
        .clk(clk),
        .cycle(cycle),
        .rst_n(rst_n),
        .frame_tick(frame_tick),
        .cancel(cancel),
        .sample_req(sample_req),
        .req_id(req_id),
        .enable(enable),
        .voice_enable_mask(voice_enable_mask),
        .fcw_lane0(fcw_lane0),
        .fcw_lane1(fcw_lane1),
        .fcw_lane2(fcw_lane2),
        .fcw_lane3(fcw_lane3),
        .result_ready(result_ready),
        .calc_ready(calc_ready),
        .result_valid(result_valid),
        .result_req_id(result_req_id)
    );

    initial begin
        clk = 1'b0;
        cycle = 0;
        $readmemh(CONTROL_FILE, controls);
        apply_control(controls[0]);
        forever #10 clk = ~clk;
    end

    // Inputs for cycle N+1 are made stable at the preceding negedge.
    // No DUT output participates in this driver.
    always @(negedge clk) begin
        if (cycle < 127)
            apply_control(controls[cycle + 1]);
    end

    // The observer samples before DUT NBA updates at each posedge.
    always @(posedge clk) begin
        if (cycle == 127) begin
            #1 $finish(0);
        end else begin
            cycle <= cycle + 1;
        end
    end

    initial begin
        #3000;
        $fatal(1, "T052_CONTROL_WINDOW_TIMEOUT");
    end
endmodule
