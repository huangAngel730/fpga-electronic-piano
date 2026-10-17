`timescale 1ns / 1ps

// Testbench-only driver. It drives only external reset, MIDI RX and public
// event_ready, and observes only the public event valid/data handshake.
module midi_public_port_driver #(
    parameter integer CLK_HZ = 40_000_000,
    parameter integer MIDI_BAUD = 31_250,
    parameter string BYTE_PLAN = "bytes.drv",
    parameter string RESET_PLAN = "reset.drv",
    parameter string READY_PLAN = "ready.drv",
    parameter string EVENT_LOG = "public_events.log"
) (
    input  logic        clk,
    output logic        sys_rst_n,
    output logic        midi_rx,
    output logic        event_ready,
    input  logic        event_valid,
    input  logic [63:0] event_data
);
    localparam integer BIT_CYCLES = CLK_HZ / MIDI_BAUD;
    integer cycle_count = 0;
    integer event_fd;

    initial begin
        if (CLK_HZ <= 0 || MIDI_BAUD <= 0 || CLK_HZ % MIDI_BAUD != 0)
            $fatal(1, "NON_INTEGER_BIT_CYCLES");
        midi_rx = 1'b1;
        sys_rst_n = 1'b0;
        event_ready = 1'b1;
        event_fd = $fopen(EVENT_LOG, "w");
        if (event_fd == 0) $fatal(1, "EVENT_LOG_OPEN");
    end

    always @(posedge clk) begin
        cycle_count <= cycle_count + 1;
        if (event_valid && event_ready)
            $fwrite(event_fd, "%0d %016h\n", cycle_count, event_data);
    end

    task automatic wait_until(input integer target_cycle);
        while (cycle_count < target_cycle) @(negedge clk);
    endtask

    task automatic drive_uart_byte(input logic [7:0] value);
        integer bit_index;
        begin
            midi_rx = 1'b0;
            repeat (BIT_CYCLES) @(negedge clk);
            for (bit_index = 0; bit_index < 8; bit_index = bit_index + 1) begin
                midi_rx = value[bit_index];
                repeat (BIT_CYCLES) @(negedge clk);
            end
            midi_rx = 1'b1;
            repeat (BIT_CYCLES) @(negedge clk);
        end
    endtask

    initial begin : drive_bytes
        integer fd, rc, start_cycle, byte_seq;
        logic [7:0] value;
        fd = $fopen(BYTE_PLAN, "r");
        if (fd == 0) $fatal(1, "BYTE_PLAN_OPEN");
        while (!$feof(fd)) begin
            rc = $fscanf(fd, "%d %h %d\n", start_cycle, value, byte_seq);
            if (rc == 3) begin
                wait_until(start_cycle);
                drive_uart_byte(value);
            end else if (!$feof(fd)) $fatal(1, "BYTE_PLAN_PARSE");
        end
        $fclose(fd);
    end

    initial begin : drive_reset
        integer fd, rc, target_cycle, level;
        fd = $fopen(RESET_PLAN, "r");
        if (fd == 0) $fatal(1, "RESET_PLAN_OPEN");
        while (!$feof(fd)) begin
            rc = $fscanf(fd, "%d %d\n", target_cycle, level);
            if (rc == 2) begin
                wait_until(target_cycle);
                sys_rst_n = level[0];
            end else if (!$feof(fd)) $fatal(1, "RESET_PLAN_PARSE");
        end
        $fclose(fd);
    end

    initial begin : drive_ready
        integer fd, rc, target_cycle, level;
        fd = $fopen(READY_PLAN, "r");
        if (fd == 0) $fatal(1, "READY_PLAN_OPEN");
        while (!$feof(fd)) begin
            rc = $fscanf(fd, "%d %d\n", target_cycle, level);
            if (rc == 2) begin
                wait_until(target_cycle);
                event_ready = level[0];
            end else if (!$feof(fd)) $fatal(1, "READY_PLAN_PARSE");
        end
        $fclose(fd);
    end
endmodule
