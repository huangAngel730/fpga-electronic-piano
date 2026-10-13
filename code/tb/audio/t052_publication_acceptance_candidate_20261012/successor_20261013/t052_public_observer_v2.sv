// T052 P0-1 static successor: public pins only, PRE_NBA, integer ns.
`timescale 1ns/1ps

module t052_public_observer_v2 (
    input logic clk,
    input integer cycle,
    input logic rst_n,
    input logic frame_tick,
    input logic cancel,
    input logic sample_req,
    input logic [31:0] req_id,
    input logic enable,
    input logic [3:0] voice_enable_mask,
    input logic [31:0] fcw_lane0, fcw_lane1, fcw_lane2, fcw_lane3,
    input logic result_ready,
    input logic calc_ready,
    input logic result_valid,
    input logic [31:0] result_req_id
);
    integer controls_file, observations_file, publications_file, reset_file;
    integer epoch, serial, accepted_count, published_count, cancelled_count;
    integer pending_epoch, pending_serial;
    logic [31:0] pending_id;
    logic pending, previous_rst_n;
    string dut_sha, rom_sha, plan_sha, tb_sha, observer_sha, tool_sha;

    task automatic write_meta(input integer fd, input string origin);
        $fdisplay(fd,
            "{\"type\":\"META\",\"origin\":\"%s\",\"sampling\":\"PRE_NBA\",\"time_unit\":\"1ns\",\"time_precision\":\"1ps\",\"clock_period_ns\":20,\"first_posedge_ns\":10,\"dut_sha256\":\"%s\",\"rom_sha256\":\"%s\",\"plan_sha256\":\"%s\",\"tb_sha256\":\"%s\",\"observer_sha256\":\"%s\",\"tool_sha256\":\"%s\"}",
            origin, dut_sha, rom_sha, plan_sha, tb_sha, observer_sha, tool_sha);
    endtask

    initial begin
        $timeformat(-9, 0, "", 0);
        epoch = 0;
        serial = 0;
        accepted_count = 0;
        published_count = 0;
        cancelled_count = 0;
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
        write_meta(controls_file, "RTL_SIM_PUBLIC_PORTS_V1");
        write_meta(observations_file, "RTL_SIM_PUBLIC_PORTS_V1");
        write_meta(publications_file, "RTL_SIM_PUBLIC_PORTS_V1");
        write_meta(reset_file, "RTL_SIM_RESET_SIGNAL_V1");
        // Inactive-region initial sample handles time-zero X->known ordering.
        #0;
        if (rst_n !== 1'b0 && rst_n !== 1'b1)
            $fatal(1, "T052_INITIAL_RESET_UNKNOWN");
        $fdisplay(reset_file,
            "{\"event\":\"RESET_EDGE\",\"time\":%0d,\"cycle_visible_next\":%0d,\"rst_n\":%0d}",
            $time, cycle, rst_n);
    end

    // Every asynchronous transition is recorded, not only posedge levels.
    // Extra pulses relative to the fixed input plan cannot qualify as PASS.
    always @(rst_n) begin
        if (reset_file && $time > 0) begin
            if (rst_n !== 1'b0 && rst_n !== 1'b1)
                $fatal(1, "T052_RESET_UNKNOWN");
            $fdisplay(reset_file,
                "{\"event\":\"RESET_EDGE\",\"time\":%0d,\"cycle_visible_next\":%0d,\"rst_n\":%0d}",
                $time, cycle, rst_n);
        end
    end

    // Blocking observer bookkeeping does not drive any DUT input. All reads
    // occur in the active region, before the DUT's nonblocking assignments.
    always @(posedge clk) begin
        if ($isunknown({rst_n, frame_tick, cancel, sample_req, req_id, enable,
                        voice_enable_mask, fcw_lane0, fcw_lane1, fcw_lane2,
                        fcw_lane3, result_ready, calc_ready, result_valid,
                        result_req_id}))
            $fatal(1, "T052_PUBLIC_PIN_UNKNOWN");
        $fdisplay(controls_file,
            "{\"cycle\":%0d,\"time\":%0d,\"rst_n\":%0d,\"frame\":%0d,\"cancel\":%0d,\"sample_req\":%0d,\"req_id\":%0d,\"enable\":%0d,\"mask\":%0d,\"fcw\":[%0d,%0d,%0d,%0d],\"result_ready\":%0d}",
            cycle, $time, rst_n, frame_tick, cancel, sample_req, req_id,
            enable, voice_enable_mask, fcw_lane0, fcw_lane1, fcw_lane2,
            fcw_lane3, result_ready);
        $fdisplay(observations_file,
            "{\"cycle\":%0d,\"time\":%0d,\"calc_ready\":%0d,\"result_valid\":%0d,\"result_req_id\":%0d}",
            cycle, $time, calc_ready, result_valid, result_req_id);
        if (!rst_n) begin
            if (previous_rst_n) begin
                epoch = epoch + 1;
                serial = 0;
            end
            if (pending) begin
                cancelled_count = cancelled_count + 1;
                $fdisplay(publications_file,
                    "{\"event\":\"CANCEL\",\"cycle\":%0d,\"time\":%0d,\"epoch\":%0d,\"serial\":%0d,\"req_id\":%0d,\"reason\":\"reset\"}",
                    cycle, $time, pending_epoch, pending_serial, pending_id);
            end
            pending = 1'b0;
        end else if (frame_tick || cancel) begin
            if (pending) begin
                cancelled_count = cancelled_count + 1;
                $fdisplay(publications_file,
                    "{\"event\":\"CANCEL\",\"cycle\":%0d,\"time\":%0d,\"epoch\":%0d,\"serial\":%0d,\"req_id\":%0d,\"reason\":\"%s\"}",
                    cycle, $time, pending_epoch, pending_serial, pending_id,
                    frame_tick ? "frame" : "cancel");
            end
            pending = 1'b0;
        end else begin
            if (result_valid && result_ready) begin
                if (!pending || result_req_id !== pending_id)
                    $fatal(1, "T052_OBSERVER_ORPHAN_OR_ID");
                published_count = published_count + 1;
                $fdisplay(publications_file,
                    "{\"event\":\"PUBLISH\",\"cycle\":%0d,\"time\":%0d,\"epoch\":%0d,\"serial\":%0d,\"req_id\":%0d,\"observed_req_id\":%0d}",
                    cycle, $time, pending_epoch, pending_serial, pending_id,
                    result_req_id);
                pending = 1'b0;
            end
            if (sample_req && calc_ready) begin
                if (pending)
                    $fatal(1, "T052_OBSERVER_MULTIPLE_OPEN");
                serial = serial + 1;
                accepted_count = accepted_count + 1;
                pending_epoch = epoch;
                pending_serial = serial;
                pending_id = req_id;
                pending = 1'b1;
                $fdisplay(publications_file,
                    "{\"event\":\"ACCEPT\",\"cycle\":%0d,\"time\":%0d,\"epoch\":%0d,\"serial\":%0d,\"req_id\":%0d}",
                    cycle, $time, pending_epoch, pending_serial, pending_id);
            end
        end
        previous_rst_n = rst_n;
        if (cycle == 127) begin
            $fdisplay(controls_file, "{\"type\":\"END\",\"last_cycle\":127,\"rows\":128}");
            $fdisplay(observations_file, "{\"type\":\"END\",\"last_cycle\":127,\"rows\":128}");
            $fdisplay(publications_file,
                "{\"type\":\"END\",\"accepted\":%0d,\"published\":%0d,\"cancelled\":%0d,\"open\":%0d}",
                accepted_count, published_count, cancelled_count, pending ? 1 : 0);
            $fdisplay(reset_file, "{\"type\":\"END\",\"last_cycle\":127}");
            $fclose(controls_file);
            $fclose(observations_file);
            $fclose(publications_file);
            $fclose(reset_file);
        end
    end
endmodule
