// Read-only public-port observer for the proposed T052 128-edge capture.
// Static preparation only. It intentionally has no hierarchical DUT access.
`timescale 1ns/1ps

module t052_public_observer (
    input logic clk,
    input integer cycle,
    input logic rst_n,
    input logic frame_tick,
    input logic cancel,
    input logic sample_req,
    input logic [31:0] req_id,
    input logic enable,
    input logic [3:0] voice_enable_mask,
    input logic [31:0] fcw_lane0,
    input logic [31:0] fcw_lane1,
    input logic [31:0] fcw_lane2,
    input logic [31:0] fcw_lane3,
    input logic result_ready,
    input logic calc_ready,
    input logic result_valid,
    input logic [31:0] result_req_id
);
    integer controls_file;
    integer observations_file;
    integer publications_file;
    integer reset_file;
    integer epoch;
    integer serial;
    integer accepted_count;
    integer published_count;
    integer cancelled_count;
    integer open_count;
    integer pending_epoch;
    integer pending_serial;
    logic [31:0] pending_id;
    logic pending;
    logic previous_rst_n;
    string dut_sha;
    string rom_sha;
    string plan_sha;
    string tb_sha;
    string observer_sha;
    string tool_sha;

    initial begin
        epoch = 0;
        serial = 0;
        accepted_count = 0;
        published_count = 0;
        cancelled_count = 0;
        open_count = 0;
        pending = 1'b0;
        previous_rst_n = 1'b1;
        if (!$value$plusargs("DUT_SHA=%s", dut_sha))
            $fatal(1, "MISSING_IDENTITY_PLUSARG:DUT_SHA");
        if (!$value$plusargs("ROM_SHA=%s", rom_sha))
            $fatal(1, "MISSING_IDENTITY_PLUSARG:ROM_SHA");
        if (!$value$plusargs("PLAN_SHA=%s", plan_sha))
            $fatal(1, "MISSING_IDENTITY_PLUSARG:PLAN_SHA");
        if (!$value$plusargs("TB_SHA=%s", tb_sha))
            $fatal(1, "MISSING_IDENTITY_PLUSARG:TB_SHA");
        if (!$value$plusargs("OBSERVER_SHA=%s", observer_sha))
            $fatal(1, "MISSING_IDENTITY_PLUSARG:OBSERVER_SHA");
        if (!$value$plusargs("TOOL_SHA=%s", tool_sha))
            $fatal(1, "MISSING_IDENTITY_PLUSARG:TOOL_SHA");
        controls_file = $fopen("t052_controls_actual.jsonl", "w");
        observations_file = $fopen("t052_observations_actual.jsonl", "w");
        publications_file = $fopen("t052_publications_actual.jsonl", "w");
        reset_file = $fopen("t052_reset_events_actual.jsonl", "w");
        if (!controls_file || !observations_file || !publications_file || !reset_file)
            $fatal(1, "T052_CAPTURE_OPEN_FAILED");
        $fdisplay(controls_file,
            "{\"type\":\"META\",\"origin\":\"RTL_SIM_PUBLIC_PORTS_V1\",\"sampling\":\"PRE_NBA\",\"dut_sha256\":\"%s\",\"rom_sha256\":\"%s\",\"plan_sha256\":\"%s\",\"tb_sha256\":\"%s\",\"observer_sha256\":\"%s\",\"tool_sha256\":\"%s\"}",
            dut_sha, rom_sha, plan_sha, tb_sha, observer_sha, tool_sha);
        $fdisplay(observations_file,
            "{\"type\":\"META\",\"origin\":\"RTL_SIM_PUBLIC_PORTS_V1\",\"sampling\":\"PRE_NBA\",\"dut_sha256\":\"%s\",\"plan_sha256\":\"%s\"}",
            dut_sha, plan_sha);
        $fdisplay(publications_file,
            "{\"type\":\"META\",\"origin\":\"RTL_SIM_PUBLIC_PORTS_V1\",\"qualification\":\"PUBLIC_HANDSHAKE_ONLY\",\"dut_sha256\":\"%s\",\"plan_sha256\":\"%s\"}",
            dut_sha, plan_sha);
        $fdisplay(reset_file,
            "{\"type\":\"META\",\"origin\":\"RTL_SIM_RESET_SIGNAL_V1\",\"time_unit\":\"1ns\",\"dut_sha256\":\"%s\",\"plan_sha256\":\"%s\"}",
            dut_sha, plan_sha);
        // Time-zero X->known ordering is simulator-dependent. Sample the
        // settled initial reset once in the inactive region and ignore a
        // concurrent time-zero signal event below.
        #0;
        if (rst_n === 1'b0 || rst_n === 1'b1)
            $fdisplay(reset_file,
                "{\"event\":\"RESET_EDGE\",\"time\":%0t,\"cycle_visible_next\":%0d,\"rst_n\":%0d}",
                $time, cycle, rst_n);
    end

    // Records every reset transition, including transitions between posedges.
    always @(rst_n) begin
        if (reset_file && $time > 0)
            $fdisplay(reset_file,
                "{\"event\":\"RESET_EDGE\",\"time\":%0t,\"cycle_visible_next\":%0d,\"rst_n\":%0d}",
                $time, cycle, rst_n);
    end

    always @(posedge clk) begin
        $fdisplay(controls_file,
            "{\"cycle\":%0d,\"time\":%0t,\"rst_n\":%0d,\"frame\":%0d,\"cancel\":%0d,\"sample_req\":%0d,\"req_id\":%0d,\"enable\":%0d,\"mask\":%0d,\"fcw\":[%0d,%0d,%0d,%0d],\"result_ready\":%0d}",
            cycle, $time, rst_n, frame_tick, cancel, sample_req, req_id,
            enable, voice_enable_mask, fcw_lane0, fcw_lane1, fcw_lane2,
            fcw_lane3, result_ready);
        $fdisplay(observations_file,
            "{\"cycle\":%0d,\"time\":%0t,\"calc_ready\":%0d,\"result_valid\":%0d,\"result_req_id\":%0d}",
            cycle, $time, calc_ready, result_valid, result_req_id);

        if (!rst_n) begin
            if (previous_rst_n) begin
                epoch = epoch + 1;
                serial = 0;
            end
            if (pending) begin
                cancelled_count = cancelled_count + 1;
                $fdisplay(publications_file,
                    "{\"event\":\"CANCEL\",\"cycle\":%0d,\"time\":%0t,\"epoch\":%0d,\"serial\":%0d,\"req_id\":%0d,\"reason\":\"reset\"}",
                    cycle, $time, pending_epoch, pending_serial, pending_id);
            end
            pending = 1'b0;
        end else if (frame_tick || cancel) begin
            if (pending) begin
                cancelled_count = cancelled_count + 1;
                $fdisplay(publications_file,
                    "{\"event\":\"CANCEL\",\"cycle\":%0d,\"time\":%0t,\"epoch\":%0d,\"serial\":%0d,\"req_id\":%0d,\"reason\":\"%s\"}",
                    cycle, $time, pending_epoch, pending_serial, pending_id,
                    frame_tick ? "frame" : "cancel");
            end
            pending = 1'b0;
        end else begin
            if (result_valid && result_ready) begin
                published_count = published_count + 1;
                $fdisplay(publications_file,
                    "{\"event\":\"PUBLISH\",\"cycle\":%0d,\"time\":%0t,\"epoch\":%0d,\"serial\":%0d,\"req_id\":%0d,\"observed_req_id\":%0d}",
                    cycle, $time, pending_epoch, pending_serial, pending_id,
                    result_req_id);
                pending = 1'b0;
            end
            if (sample_req && calc_ready) begin
                serial = serial + 1;
                accepted_count = accepted_count + 1;
                pending_epoch = epoch;
                pending_serial = serial;
                pending_id = req_id;
                pending = 1'b1;
                $fdisplay(publications_file,
                    "{\"event\":\"ACCEPT\",\"cycle\":%0d,\"time\":%0t,\"epoch\":%0d,\"serial\":%0d,\"req_id\":%0d}",
                    cycle, $time, pending_epoch, pending_serial, pending_id);
            end
        end
        previous_rst_n = rst_n;

        if (cycle == 127) begin
            open_count = pending ? 1 : 0;
            $fdisplay(controls_file, "{\"type\":\"END\",\"last_cycle\":127,\"rows\":128}");
            $fdisplay(observations_file, "{\"type\":\"END\",\"last_cycle\":127,\"rows\":128}");
            $fdisplay(publications_file,
                "{\"type\":\"END\",\"accepted\":%0d,\"published\":%0d,\"cancelled\":%0d,\"open\":%0d}",
                accepted_count, published_count, cancelled_count, open_count);
            $fdisplay(reset_file, "{\"type\":\"END\",\"last_cycle\":127}");
            $fclose(controls_file);
            $fclose(observations_file);
            $fclose(publications_file);
            $fclose(reset_file);
        end
    end
endmodule
