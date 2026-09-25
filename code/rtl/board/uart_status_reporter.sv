// T025: fixed-field ASCII telemetry for the PC status monitor.
// One coherent snapshot is emitted every REPORT_CYCLES sys_clk cycles.
// Port values are uint32; unavailable metrics must not be silently tied low.
`timescale 1ns/1ps
module uart_status_reporter #(
    parameter int unsigned CLK_HZ = 50_000_000,
    parameter int unsigned BAUD = 115_200,
    parameter int unsigned REPORT_CYCLES = CLK_HZ / 4,
    // Before the mixer exists, report a DIAG line and a nonnumeric clip field.
    parameter bit CLIP_COUNT_VALID = 1'b1
) (
    input  logic        clk,
    input  logic        rst_n,  // synchronous, active low
    input  logic [31:0] active_voice_count,
    input  logic [31:0] clip_count,
    input  logic [31:0] event_fifo_level,
    input  logic [31:0] event_fifo_high_watermark,
    input  logic [31:0] event_fifo_overflow,
    input  logic [31:0] audio_underrun,
    input  logic [31:0] max_processing_cycles,
    output logic        tx,
    output logic        report_busy
);
    localparam logic [8*26-1:0] LABEL0 = CLIP_COUNT_VALID ?
        "STAT active_voice_count=0x" : "DIAG active_voice_count=0x";
    localparam logic [8*14-1:0] LABEL1 = " clip_count=0x";
    localparam logic [8*20-1:0] LABEL2 = " event_fifo_level=0x";
    localparam logic [8*29-1:0] LABEL3 = " event_fifo_high_watermark=0x";
    localparam logic [8*23-1:0] LABEL4 = " event_fifo_overflow=0x";
    localparam logic [8*18-1:0] LABEL5 = " audio_underrun=0x";
    localparam logic [8*25-1:0] LABEL6 = " max_processing_cycles=0x";

    logic [31:0] snapshot [0:6];
    logic [31:0] interval_count;
    logic [2:0] field_index;
    logic [4:0] char_index;
    logic [2:0] hex_index;
    logic [1:0] phase; // 0 label, 1 eight hex digits, 2 CR, 3 LF
    logic [7:0] tx_data;
    logic tx_ready, tx_valid;

    function automatic logic [4:0] label_length(input logic [2:0] field);
        case (field)
            3'd0: label_length = 5'd26;
            3'd1: label_length = 5'd14;
            3'd2: label_length = 5'd20;
            3'd3: label_length = 5'd29;
            3'd4: label_length = 5'd23;
            3'd5: label_length = 5'd18;
            default: label_length = 5'd25;
        endcase
    endfunction

    function automatic logic [7:0] label_char(
        input logic [2:0] field, input logic [4:0] pos
    );
        case (field)
            3'd0: label_char = LABEL0[8*(25-pos) +: 8];
            3'd1: label_char = LABEL1[8*(13-pos) +: 8];
            3'd2: label_char = LABEL2[8*(19-pos) +: 8];
            3'd3: label_char = LABEL3[8*(28-pos) +: 8];
            3'd4: label_char = LABEL4[8*(22-pos) +: 8];
            3'd5: label_char = LABEL5[8*(17-pos) +: 8];
            default: label_char = LABEL6[8*(24-pos) +: 8];
        endcase
    endfunction

    logic [3:0] nibble;
    always_comb begin
        nibble = snapshot[field_index][4*(7-hex_index) +: 4];
        case (phase)
            2'd0: tx_data = label_char(field_index, char_index);
            2'd1: tx_data = (!CLIP_COUNT_VALID && field_index == 3'd1) ?
                8'h2d : (nibble < 4'd10 ? 8'h30 + {4'b0,nibble}
                                           : 8'h37 + {4'b0,nibble});
            2'd2: tx_data = 8'h0d;
            default: tx_data = 8'h0a;
        endcase
    end
    assign tx_valid = report_busy;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            interval_count <= '0;
            field_index <= '0;
            char_index <= '0;
            hex_index <= '0;
            phase <= '0;
            report_busy <= 1'b0;
            for (integer i = 0; i < 7; i = i + 1) snapshot[i] <= '0;
        end else begin
            if (interval_count == REPORT_CYCLES - 1) begin
                interval_count <= '0;
                if (!report_busy) begin
                    snapshot[0] <= active_voice_count;
                    snapshot[1] <= clip_count;
                    snapshot[2] <= event_fifo_level;
                    snapshot[3] <= event_fifo_high_watermark;
                    snapshot[4] <= event_fifo_overflow;
                    snapshot[5] <= audio_underrun;
                    snapshot[6] <= max_processing_cycles;
                    field_index <= '0;
                    char_index <= '0;
                    hex_index <= '0;
                    phase <= '0;
                    report_busy <= 1'b1;
                end
            end else begin
                interval_count <= interval_count + 1'b1;
            end

            if (report_busy && tx_ready) begin
                case (phase)
                    2'd0: if (char_index == label_length(field_index)-1'b1) begin
                        char_index <= '0;
                        hex_index <= '0;
                        phase <= 2'd1;
                    end else char_index <= char_index + 1'b1;
                    2'd1: if (hex_index == 3'd7) begin
                        hex_index <= '0;
                        if (field_index == 3'd6) phase <= 2'd2;
                        else begin
                            field_index <= field_index + 1'b1;
                            phase <= 2'd0;
                        end
                    end else hex_index <= hex_index + 1'b1;
                    2'd2: phase <= 2'd3;
                    default: report_busy <= 1'b0;
                endcase
            end
        end
    end

    uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(BAUD)) u_uart_tx (
        .clk, .rst_n, .tx_data, .tx_valid, .tx_ready, .tx
    );
endmodule
