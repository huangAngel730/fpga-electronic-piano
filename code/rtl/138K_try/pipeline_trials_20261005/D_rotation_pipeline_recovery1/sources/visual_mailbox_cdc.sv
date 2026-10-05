// M2 independent reliable one-entry display-control CDC mailbox.
// Shared rst_n asserts asynchronously and releases through local synchronizers.
// A unilateral reset of either domain is forbidden; PLL loss must flush both.
// src_data is latched at acceptance and held through returned destination ACK.
// Physical integration must bound payload_hold -> dst_data before request sync.
`timescale 1ns/1ps
module visual_mailbox_cdc #(
    parameter integer WIDTH = 1
) (
    input  logic src_clk, dst_clk, rst_n,
    input  logic src_valid,
    output logic src_ready,
    input  logic [WIDTH-1:0] src_data,
    output logic dst_valid,
    input  logic dst_ready,
    output logic [WIDTH-1:0] dst_data,
    output wire src_reset_done, dst_reset_done
);
    logic [WIDTH-1:0] payload_hold;
    logic request_toggle, acknowledge_toggle;
    (* async_reg = "true" *) logic ack_meta, ack_sync;
    (* async_reg = "true" *) logic req_meta, req_sync;
    reset_sync u_src_reset (.clk(src_clk), .rst_n(rst_n), .rst_sync_n(src_reset_done));
    reset_sync u_dst_reset (.clk(dst_clk), .rst_n(rst_n), .rst_sync_n(dst_reset_done));
    assign src_ready = src_reset_done && (request_toggle == ack_sync);

    always_ff @(posedge src_clk or negedge src_reset_done) begin
        if (!src_reset_done) begin
            ack_meta <= 1'b0;
            ack_sync <= 1'b0;
        end else begin
            ack_meta <= acknowledge_toggle;
            ack_sync <= ack_meta;
        end
    end
    always_ff @(posedge src_clk or negedge src_reset_done) begin
        if (!src_reset_done) begin
            payload_hold <= '0;
            request_toggle <= 1'b0;
        end else if (src_valid && src_ready) begin
            payload_hold <= src_data;
            request_toggle <= ~request_toggle;
        end
    end
    always_ff @(posedge dst_clk or negedge dst_reset_done) begin
        if (!dst_reset_done) begin
            req_meta <= 1'b0;
            req_sync <= 1'b0;
        end else begin
            req_meta <= request_toggle;
            req_sync <= req_meta;
        end
    end
    always_ff @(posedge dst_clk or negedge dst_reset_done) begin
        if (!dst_reset_done) begin
            dst_data <= '0;
            dst_valid <= 1'b0;
            acknowledge_toggle <= 1'b0;
        end else if (dst_valid) begin
            if (dst_ready) begin
                dst_valid <= 1'b0;
                acknowledge_toggle <= req_sync;
            end
        end else if (req_sync != acknowledge_toggle) begin
            // Data is held at the source until acceptance and returned ACK.
            dst_data <= payload_hold;
            dst_valid <= 1'b1;
        end
    end
`ifndef SYNTHESIS
    initial if (WIDTH < 1) $fatal(1,"visual_mailbox_cdc WIDTH must be positive");
`endif
endmodule
