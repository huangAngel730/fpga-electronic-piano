// Supplemental lifecycle boundaries: async reset, generation wrap, duplicate
// commands, multi-slot release payload and ready/valid ordering.
`timescale 1ns / 1ps
module tb_sustain_controller;
    import sustain_control_contract_pkg::*;
    logic clk = 0, run_clock = 1;
    always #10 if (run_clock) clk = ~clk;
    logic rst_n = 0, cmd_valid = 0, release_ready = 0;
    logic [2:0] cmd_type = 0;
    logic [1:0] cmd_slot = 0;
    logic [3:0] cmd_source_id = 0, cmd_channel = 0;
    logic [6:0] cmd_note_number = 0;
    logic [11:0] cmd_control_value = 0;
    logic [31:0] cmd_generation = 0;
    wire cmd_ready, release_valid;
    wire [3:0] release_mask, occupied_mask, key_down_mask, deferred_mask, releasing_mask;
    wire [127:0] release_generations;
    integer checks = 0;
    sustain_controller dut (.*);

    task automatic check(input logic condition, input string reason);
        checks = checks + 1;
        if (condition !== 1'b1) $fatal(1, "%s at %0t", reason, $time);
    endtask
    task automatic send_cmd(input logic [2:0] kind, input logic [1:0] slot,
                            input logic [3:0] source, channel,
                            input logic [6:0] note, input logic [11:0] value,
                            input logic [31:0] generation);
        @(negedge clk);
        check(cmd_ready, "command issued without ready");
        cmd_type = kind; cmd_slot = slot; cmd_source_id = source;
        cmd_channel = channel; cmd_note_number = note;
        cmd_control_value = value; cmd_generation = generation;
        cmd_valid = 1;
        @(negedge clk); cmd_valid = 0;
    endtask
    task automatic ack_release;
        @(negedge clk); release_ready = 1;
        @(negedge clk); release_ready = 0;
        check(!release_valid && release_mask == 0 && release_generations == 0,
              "ACK failed to clear payload");
    endtask
    initial begin
        logic [127:0] held_generations;
        repeat (2) @(negedge clk); rst_n = 1;
        send_cmd(SUSTAIN_CMD_NOTE_ON, 0, 15, 15, 127, 0, 32'hffffffff);
        send_cmd(SUSTAIN_CMD_RETIRE, 0, 15, 15, 127, 0, 32'hffffffff);
        check(occupied_mask == 1 && key_down_mask == 1, "held RETIRE cleared slot");
        send_cmd(SUSTAIN_CMD_PEDAL, 0, 15, 15, 0, 2048, 0);
        send_cmd(SUSTAIN_CMD_NOTE_OFF, 0, 15, 15, 127, 0, 32'hffffffff);
        send_cmd(SUSTAIN_CMD_NOTE_OFF, 0, 15, 15, 127, 0, 32'hffffffff);
        check(deferred_mask == 1 && !release_valid, "duplicate deferred OFF");
        send_cmd(SUSTAIN_CMD_RETIRE, 0, 15, 15, 127, 0, 32'hffffffff);
        check(occupied_mask == 1 && deferred_mask == 1, "deferred RETIRE cleared slot");
        // Same note re-trigger after generation wrap, then stale OFF/RETIRE.
        send_cmd(SUSTAIN_CMD_NOTE_ON, 0, 15, 15, 127, 0, 0);
        send_cmd(SUSTAIN_CMD_NOTE_OFF, 0, 15, 15, 127, 0, 32'hffffffff);
        send_cmd(SUSTAIN_CMD_RETIRE, 0, 15, 15, 127, 0, 32'hffffffff);
        check(key_down_mask == 1 && deferred_mask == 0, "stale generation affected wrapped slot");
        send_cmd(SUSTAIN_CMD_NOTE_ON, 1, 15, 15, 60, 0, 32'h80000000);
        send_cmd(SUSTAIN_CMD_NOTE_ON, 2, 15, 15, 64, 0, 7);
        send_cmd(SUSTAIN_CMD_NOTE_OFF, 0, 15, 15, 127, 0, 0);
        send_cmd(SUSTAIN_CMD_NOTE_OFF, 1, 15, 15, 60, 0, 32'h80000000);
        send_cmd(SUSTAIN_CMD_PEDAL, 0, 15, 15, 0, 2047, 0);
        check(release_valid && release_mask == 3 && key_down_mask == 4 &&
              deferred_mask == 0 && releasing_mask == 3, "group pedal-up/held-key boundary");
        check(release_generations == 128'h00000000_00000000_80000000_00000000,
              "generation zero/high bit payload or nonmask slices");
        held_generations = release_generations;
        // Held upstream command must not apply on the release ACK edge.
        @(negedge clk); cmd_valid = 1; cmd_type = SUSTAIN_CMD_NOTE_ON;
        cmd_slot = 3; cmd_source_id = 0; cmd_channel = 0;
        cmd_note_number = 50; cmd_generation = 9;
        repeat (4) begin
            @(negedge clk);
            check(!cmd_ready && release_valid && release_mask == 3 &&
                  release_generations == held_generations && occupied_mask == 7,
                  "pending release payload/state changed under backpressure");
        end
        release_ready = 1;
        @(negedge clk); release_ready = 0;
        check(cmd_ready && !release_valid && occupied_mask == 7,
              "ACK edge incorrectly accepted upstream command");
        @(negedge clk); cmd_valid = 0;
        check(occupied_mask == 15 && key_down_mask == 12,
              "held command not accepted after ACK");
        // Repeated OFF and pedal-up cannot repeat an already issued Release.
        send_cmd(SUSTAIN_CMD_NOTE_OFF, 1, 15, 15, 60, 0, 32'h80000000);
        send_cmd(SUSTAIN_CMD_PEDAL, 0, 15, 15, 0, 0, 0);
        check(!release_valid, "duplicate release generated");
        send_cmd(SUSTAIN_CMD_PEDAL, 0, 15, 15, 0, 4095, 0);
        check(releasing_mask == 3, "pedal down revived releasing notes");
        send_cmd(3'd5, 0, 0, 0, 0, 0, 0);
        send_cmd(3'd6, 0, 0, 0, 0, 0, 0);
        send_cmd(3'd7, 0, 0, 0, 0, 0, 0);
        check(occupied_mask == 15 && releasing_mask == 3, "reserved command changed state");
        send_cmd(SUSTAIN_CMD_PANIC, 0, 0, 0, 0, 0, 0);
        check(release_mask == 12 && key_down_mask == 0 && deferred_mask == 0 &&
              releasing_mask == 15, "panic must release only previously unreleased notes");
        ack_release();
        send_cmd(SUSTAIN_CMD_PANIC, 0, 0, 0, 0, 0, 0);
        check(!release_valid && occupied_mask == 15, "panic duplicates or early frees");
        send_cmd(SUSTAIN_CMD_RETIRE, 0, 15, 15, 127, 0, 0);
        check(occupied_mask == 14, "matching retire did not free slot");
        // PANIC cleared the previously down pedal for source/channel 15/15.
        send_cmd(SUSTAIN_CMD_NOTE_ON, 0, 15, 15, 127, 0, 1);
        send_cmd(SUSTAIN_CMD_NOTE_OFF, 0, 15, 15, 127, 0, 1);
        check(release_valid && release_mask == 1, "panic failed to clear pedal bank");
        // Reset while clock stopped must cancel a stalled payload immediately.
        @(negedge clk); run_clock = 0;
        #3; rst_n = 0; #1;
        check(!release_valid && !cmd_ready && occupied_mask == 0 &&
              key_down_mask == 0 && deferred_mask == 0 && releasing_mask == 0 &&
              release_generations == 0, "asynchronous reset failed with stopped clock");
        #20; run_clock = 1;
        repeat (2) @(negedge clk); rst_n = 1;
        repeat (2) @(negedge clk);
        check(cmd_ready && !release_valid && occupied_mask == 0, "reset replayed old release");
        $display("PASS tb_sustain_controller checks=%0d", checks);
        $finish;
    end
    initial begin #100000; $fatal(1, "sustain controller timeout"); end
endmodule
