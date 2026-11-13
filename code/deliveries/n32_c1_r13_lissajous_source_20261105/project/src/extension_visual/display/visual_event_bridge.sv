// M2 display-only event copy. Audio acceptance must NEVER depend on this bridge.
// rst_n is shared: asynchronous assertion, synchronous release per clock domain.
// No unilateral video reset: PLL unlock must flush BOTH sides via shared rst_n.
// Payload is held from request launch until destination acceptance + returned ack.
// Physical integration must bound the payload path before destination capture.
`timescale 1ns/1ps
module visual_event_bridge #(
    parameter integer DEPTH = 32,
    parameter integer TAG_WIDTH = 33
) (
    input logic sys_clk, video_clk, rst_n,
    input logic accepted_valid,
    input audio_defs_pkg::performance_event_t accepted_data,
    input logic [TAG_WIDTH-1:0] accepted_tag,
    output logic [15:0] visual_queue_level,
    output logic [15:0] visual_queue_high_watermark,
    output logic [31:0] visual_drop_count,
    output logic visual_drop_pulse,
    output logic sys_reset_done, video_reset_done,
    output logic video_valid,
    output logic video_desync,
    input logic video_ready,
    output audio_defs_pkg::performance_event_t video_data,
    output logic [TAG_WIDTH-1:0] video_tag
);
    localparam integer PTR_W = (DEPTH <= 2) ? 1 : $clog2(DEPTH);
    localparam integer CNT_W = $clog2(DEPTH + 1);
    audio_defs_pkg::performance_event_t queue [0:DEPTH-1];
    audio_defs_pkg::performance_event_t payload_hold;
    logic [TAG_WIDTH-1:0] tag_queue [0:DEPTH-1];
    logic [TAG_WIDTH-1:0] tag_hold;
    logic [PTR_W-1:0] wr_ptr, rd_ptr;
    // Native009: delay only logical rd_ptr[4] at the tag RAM read consumer.
    // Payload queue read, write address, pop/ack and capture edge stay direct.
    wire [PTR_W-1:0] tag_read_address;
    for (genvar address_bit=0; address_bit<PTR_W; address_bit=address_bit+1) begin:g_tag_read_address
        if (address_bit==4) begin:g_hold
            (* syn_keep=1, syn_dont_touch=1 *) wire l0,l1;
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_hold0(.I0(rd_ptr[address_bit]),.F(l0));
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_hold1(.I0(l0),.F(l1));
            assign tag_read_address[address_bit]=l1;
        end else begin:g_direct
            assign tag_read_address[address_bit]=rd_ptr[address_bit];
        end
    end
    logic [CNT_W-1:0] count, next_count;
    logic request_toggle, acknowledge_toggle;
    (* async_reg = "true" *) logic ack_meta, ack_sync;
    (* async_reg = "true" *) logic req_meta, req_sync;
    logic pop, push, space;
    logic source_desync;
    (* async_reg = "true" *) logic desync_meta;

    reset_sync u_sys_reset (.clk(sys_clk), .rst_n(rst_n), .rst_sync_n(sys_reset_done));
    reset_sync u_video_reset (.clk(video_clk), .rst_n(rst_n), .rst_sync_n(video_reset_done));

    function automatic [PTR_W-1:0] advance(input [PTR_W-1:0] ptr);
        if (ptr == DEPTH-1) advance = '0;
        else advance = ptr + 1'b1;
    endfunction

    // ack only moves after video_valid && video_ready. Queue and one mailbox
    // are separate storage: total capacity is DEPTH queued + one in flight.
    always_comb begin
        pop = sys_reset_done && count != 0 && ack_sync == request_toggle;
        space = sys_reset_done && ((count < DEPTH) || pop);
        push = accepted_valid && space;
        next_count = count + push - pop;
        visual_queue_level = {{(16-CNT_W){1'b0}}, count};
    end

    always_ff @(posedge sys_clk or negedge sys_reset_done) begin
        if (!sys_reset_done) begin
            ack_meta <= 1'b0;
            ack_sync <= 1'b0;
        end else begin
            ack_meta <= acknowledge_toggle;
            ack_sync <= ack_meta;
        end
    end

    always_ff @(posedge sys_clk or negedge sys_reset_done) begin
        if (!sys_reset_done) begin
            wr_ptr <= '0;
            rd_ptr <= '0;
            count <= '0;
            payload_hold <= '0;
            tag_hold <= '0;
            request_toggle <= 1'b0;
            visual_queue_high_watermark <= '0;
            visual_drop_count <= '0;
            visual_drop_pulse <= 1'b0;
            source_desync <= 1'b0;
        end else begin
            visual_drop_pulse <= accepted_valid && !space;
            if (accepted_valid && !space) source_desync <= 1'b1;
            if (accepted_valid && !space && visual_drop_count != 32'hffff_ffff)
                visual_drop_count <= visual_drop_count + 1'b1;
            if (push) begin
                queue[wr_ptr] <= accepted_data;
                tag_queue[wr_ptr] <= accepted_tag;
                wr_ptr <= advance(wr_ptr);
            end
            if (pop) begin
                payload_hold <= queue[rd_ptr];
                tag_hold <= tag_queue[tag_read_address];
                request_toggle <= ~request_toggle;
                rd_ptr <= advance(rd_ptr);
            end
            count <= next_count;
            if (next_count > visual_queue_high_watermark)
                visual_queue_high_watermark <= next_count;
        end
    end

    always_ff @(posedge video_clk or negedge video_reset_done) begin
        if (!video_reset_done) begin
            req_meta <= 1'b0;
            req_sync <= 1'b0;
            desync_meta <= 1'b0;
            video_desync <= 1'b0;
        end else begin
            req_meta <= request_toggle;
            req_sync <= req_meta;
            desync_meta <= source_desync;
            video_desync <= desync_meta;
        end
    end

    always_ff @(posedge video_clk or negedge video_reset_done) begin
        if (!video_reset_done) begin
            video_data <= '0;
            video_tag <= '0;
            video_valid <= 1'b0;
            acknowledge_toggle <= 1'b0;
        end else if (video_valid) begin
            if (video_ready) begin
                video_valid <= 1'b0;
                acknowledge_toggle <= req_sync;
            end
        end else if (req_sync != acknowledge_toggle) begin
            // Bundled-data CDC: capture only after the two-flop request has
            // arrived. payload_hold stays constant until the returned ack.
            video_data <= payload_hold;
            video_tag <= tag_hold;
            video_valid <= 1'b1;
        end
    end

`ifndef SYNTHESIS
    initial begin
        if (DEPTH < 2 || DEPTH > 32767) $fatal(1, "visual queue DEPTH outside 2..32767");
    end
`endif
endmodule
