// Public-pin-only observer. Samples in active region before DUT NBA updates.
// Async reset terminates pending at assertion time, not the next posedge.
`timescale 1ns/1ps
module t052_long_observer (
    input logic clk, rst_n, frame_tick, cancel, sample_req, enable, result_ready,
    input integer cycle,
    input logic [31:0] req_id, fcw_lane0, fcw_lane1, fcw_lane2, fcw_lane3,
    input logic [3:0] voice_enable_mask,
    input logic calc_ready, result_valid,
    input logic [31:0] result_req_id
);
    integer obs_fd, pub_fd, reset_fd;
    integer epoch, serial, accepted, published, cancelled;
    integer pending_epoch, pending_serial;
    logic [31:0] pending_id;
    logic pending;
    logic [63:0] observed_time_ns;
    string reason;

    task automatic transaction(input string kind, input string why);
        if (why == "")
            $fdisplay(pub_fd,
                "{\"event\":\"%s\",\"cycle\":%0d,\"time_ns\":%0d,\"key\":[%0d,%0d,%0d]}",
                kind, cycle, $time, pending_epoch, pending_serial, pending_id);
        else
            $fdisplay(pub_fd,
                "{\"event\":\"%s\",\"cycle\":%0d,\"time_ns\":%0d,\"key\":[%0d,%0d,%0d],\"reason\":\"%s\"}",
                kind, cycle, $time, pending_epoch, pending_serial, pending_id, why);
    endtask

    initial begin
        $timeformat(-9, 0, "", 0);
        epoch = 1;
        serial = 0;
        accepted = 0;
        published = 0;
        cancelled = 0;
        pending = 0;
        obs_fd = $fopen("observations.hex", "w");
        pub_fd = $fopen("publications.jsonl", "w");
        reset_fd = $fopen("resets.jsonl", "w");
        if (!obs_fd || !pub_fd || !reset_fd) $fatal(1, "TRACE_OPEN_FAILED");
        #0;
        if (rst_n !== 1'b0) $fatal(1, "INITIAL_RESET_REQUIRED");
        $fdisplay(reset_fd, "{\"time_ns\":0,\"cycle\":0,\"rst_n\":0}");
    end
    always @(rst_n) begin
        if (reset_fd && $time > 0) begin
            if ($isunknown(rst_n)) $fatal(1, "RESET_UNKNOWN");
            $fdisplay(reset_fd, "{\"time_ns\":%0d,\"cycle\":%0d,\"rst_n\":%0d}",
                      $time, cycle, rst_n);
            if (!rst_n) begin
                if (pending) begin
                    transaction("CANCEL", "reset");
                    cancelled = cancelled + 1;
                end
                pending = 0;
                epoch = epoch + 1;
                serial = 0;
            end
        end
    end
    always @(posedge clk) begin
        observed_time_ns = $time;
        if ($isunknown({rst_n, frame_tick, cancel, sample_req, req_id, enable,
                        voice_enable_mask, fcw_lane0, fcw_lane1, fcw_lane2,
                        fcw_lane3, result_ready, calc_ready, result_valid,
                        result_req_id})) $fatal(1, "PUBLIC_PIN_UNKNOWN");
        $fdisplay(obs_fd, "%h", {cycle[31:0], observed_time_ns, rst_n, frame_tick, cancel,
            sample_req, req_id, enable, voice_enable_mask,
            fcw_lane0, fcw_lane1, fcw_lane2, fcw_lane3, result_ready,
            calc_ready, result_valid, result_req_id});
        if (!rst_n) begin
            // Reset cancellation has already been recorded asynchronously.
        end else if (frame_tick || cancel) begin
            if (pending) begin
                if (frame_tick && cancel) reason = "frame+cancel";
                else if (frame_tick) reason = "frame";
                else reason = "cancel";
                transaction("CANCEL", reason);
                cancelled = cancelled + 1;
            end
            pending = 0;
        end else begin
            if (result_valid && result_ready) begin
                if (!pending || result_req_id !== pending_id)
                    $fatal(1, "ORPHAN_OR_WRONG_ID");
                transaction("PUBLISH", "");
                published = published + 1;
                pending = 0;
            end
            if (sample_req && calc_ready) begin
                if (pending) $fatal(1, "MULTIPLE_OPEN");
                serial = serial + 1;
                accepted = accepted + 1;
                pending_epoch = epoch;
                pending_serial = serial;
                pending_id = req_id;
                pending = 1;
                transaction("ACCEPT", "");
            end
        end
        if (cycle == 8536335) begin
            $fdisplay(obs_fd, "END 8536336");
            $fdisplay(pub_fd,
                "{\"type\":\"END\",\"rows\":8536336,\"accepted\":%0d,\"published\":%0d,\"cancelled\":%0d,\"open\":%0d}",
                accepted, published, cancelled, pending ? 1 : 0);
            $fclose(obs_fd);
            $fclose(pub_fd);
            $fclose(reset_fd);
        end
    end
endmodule
