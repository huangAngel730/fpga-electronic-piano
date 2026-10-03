// G isolation candidate only. clk=50MHz; asynchronous reset assertion;
// caller synchronizes reset release. cancel discards results, NOT history.
`timescale 1ns/1ps
module m3_delay_transaction_adapter #(
    parameter integer DEPTH = 1024
) (
    input logic clk, rst_n, cancel,
    input logic request_valid,
    output logic request_ready,
    input logic [31:0] request_id,
    input logic signed [23:0] request_pcm,
    input logic [15:0] delay_samples,
    input logic [14:0] dry_gain, wet_gain, feedback,
    output logic result_valid,
    input logic result_ready,
    output logic [31:0] result_id,
    output logic signed [23:0] result_pcm
);
    typedef enum logic [1:0] {IDLE, WAIT_RAW, DRAIN, HOLD_RESULT} state_t;
    state_t state;
    logic [31:0] id_q;
    logic signed [23:0] pcm_q;
    logic [15:0] delay_q;
    logic [14:0] dry_q, wet_q, feedback_q;
    logic signed [23:0] held_pcm, raw_pcm;
    logic raw_valid, launch;

    assign request_ready = rst_n && !cancel && (state == IDLE);
    assign launch = request_valid && request_ready;
    assign result_valid = rst_n && !cancel && (state == HOLD_RESULT);
    assign result_id = id_q;
    assign result_pcm = held_pcm;

    // A successful public handshake is the original algorithm's E edge.
    // Parameters are also saved; live changes after E cannot affect the work.
    delay_effect #(.DEPTH(DEPTH)) u_effect (
        .sys_clk(clk), .sys_rst_n(rst_n), .sample_enable(launch),
        .pcm_in(launch ? request_pcm : pcm_q),
        .delay_samples(launch ? delay_samples : delay_q),
        .dry_gain(launch ? dry_gain : dry_q),
        .wet_gain(launch ? wet_gain : wet_q),
        .feedback(launch ? feedback : feedback_q),
        .pcm_out(raw_pcm), .pcm_valid(raw_valid)
    );

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            id_q <= 0;
            pcm_q <= 0;
            delay_q <= 0;
            dry_q <= 0;
            wet_q <= 0;
            feedback_q <= 0;
            held_pcm <= 0;
        end else if (cancel) begin
            // WAIT_RAW may already present its E+2 valid before this edge.
            // Otherwise drain it exactly once before re-opening admission.
            if ((state == WAIT_RAW || state == DRAIN) && !raw_valid)
                state <= DRAIN;
            else
                state <= IDLE;
        end else begin
            case (state)
                IDLE: if (launch) begin
                    id_q <= request_id;
                    pcm_q <= request_pcm;
                    delay_q <= delay_samples;
                    dry_q <= dry_gain;
                    wet_q <= wet_gain;
                    feedback_q <= feedback;
                    state <= WAIT_RAW;
                end
                WAIT_RAW: if (raw_valid) begin
                    held_pcm <= raw_pcm;
                    state <= HOLD_RESULT;
                end
                DRAIN: if (raw_valid) state <= IDLE;
                HOLD_RESULT: if (result_ready) state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end
endmodule
