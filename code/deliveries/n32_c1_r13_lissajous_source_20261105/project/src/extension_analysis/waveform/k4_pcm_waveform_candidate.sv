// T058 isolated pixel-domain candidate. No audio backpressure or CDC logic.
// Reset is async assert; caller supplies pixel-domain synchronous release.
// Geometry and latency are frozen by D038. Memory contents are not reset.
`timescale 1ns/1ps
module k4_pcm_waveform_candidate (
    input wire pixel_clk, pixel_rst_n,
    input wire sample_valid,
    input wire [31:0] sample_seq,
    input wire signed [23:0] sample_left, sample_right,
    input wire stream_restart,
    input wire [15:0] pixel_x, pixel_y,
    input wire data_enable, frame_start, waveform_enable,
    output reg waveform_mask,
    output reg [7:0] waveform_r, waveform_g, waveform_b,
    output reg trace_valid,
    output reg [31:0] display_gap_count, window_drop_count
);
    reg [15:0] bank0 [0:511];
    reg [15:0] bank1 [0:511];
    reg [15:0] bank2 [0:511];
    reg [1:0] front_bank, pending_bank, write_bank;
    reg pending_valid, have_seq;
    reg [31:0] last_seq;
    reg [10:0] sample_index;
    reg signed [23:0] bin_min, bin_max;
    wire gap = have_seq && sample_seq != last_seq + 32'd1;
    wire first_in_bin = gap || sample_index[1:0] == 0;
    wire signed [23:0] next_min = first_in_bin ? sample_left :
        (sample_left < bin_min ? sample_left : bin_min);
    wire signed [23:0] next_max = first_in_bin ? sample_left :
        (sample_left > bin_max ? sample_left : bin_max);
    wire bin_write = sample_valid && !stream_restart && !gap &&
        sample_index[1:0] == 3;
    wire window_complete = bin_write && sample_index == 2047;
    wire publish = frame_start && pending_valid && !stream_restart;
    wire [1:0] read_bank = publish ? pending_bank : front_bank;
    wire read_valid = !stream_restart && (trace_valid || publish);
    wire [8:0] read_address = pixel_x[8:0] - 9'd64;
    // Native03 scan.pixel_x[3] ->bank1.ADB[7] is a short pixel path.
    // All9 logical read-address bits get the same transparent2LUT style
    // before the3banks; synchronous read capture remains this same edge.
    wire [8:0] read_address_held;
    for(genvar address_bit=0;address_bit<9;address_bit=address_bit+1)begin:g_bank_read_hold
        (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=read_address[address_bit];
        for(genvar stage=0;stage<2;stage=stage+1)begin:g_delay
            (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(.I0(chain[stage]),.F(chain[stage+1]));
        end
        assign read_address_held[address_bit]=chain[2];
    end
    // The scan counter to x0 register is another same-clock, zero-logic hold
    // path.  Delay only the registered x token; address and mask semantics stay
    // unchanged and no pixel is inserted or removed from the renderer pipe.
    (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) wire [15:0] pixel_x_hold;
    for(genvar x_hold_bit=0;x_hold_bit<16;x_hold_bit=x_hold_bit+1)begin:g_pixel_x_hold
        if(x_hold_bit>=14) begin:g_buffered
            (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) wire [2:0] chain;
            assign chain[0]=pixel_x[x_hold_bit];
            for(genvar x_hold_stage=0;x_hold_stage<2;x_hold_stage=x_hold_stage+1)begin:g_delay
                (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                    .I0(chain[x_hold_stage]),.F(chain[x_hold_stage+1]));
            end
            assign pixel_x_hold[x_hold_bit]=chain[2];
        end else begin:g_direct
            assign pixel_x_hold[x_hold_bit]=pixel_x[x_hold_bit];
        end
    end
    wire [15:0] bin_data = {next_min[23:16], next_max[23:16]};
    reg [1:0] front_next, pending_next, write_next;
    reg pending_valid_next;
    reg drop_complete;
    integer k;

    // Allocation is only on completed windows. A publish has priority over
    // pending replacement, then the newly complete window becomes pending.
    always @* begin
        front_next = front_bank;
        pending_next = pending_bank;
        pending_valid_next = pending_valid;
        write_next = write_bank;
        drop_complete = 0;
        if (publish) begin
            front_next = pending_bank;
            pending_valid_next = 0;
        end
        if (window_complete) begin
            drop_complete = pending_valid_next;
            pending_next = write_bank;
            pending_valid_next = 1;
            for (k = 0; k < 3; k = k + 1)
                if (k != front_next && k != pending_next)
                    write_next = k[1:0];
        end
    end

    function [31:0] sat_inc;
        input [31:0] value;
        begin sat_inc = (&value) ? value : value + 32'd1; end
    endfunction

    always @(posedge pixel_clk or negedge pixel_rst_n) begin
        if (!pixel_rst_n) begin
            front_bank <= 0; pending_bank <= 2; write_bank <= 1;
            pending_valid <= 0; trace_valid <= 0;
            have_seq <= 0; last_seq <= 0; sample_index <= 0;
            bin_min <= 0; bin_max <= 0;
            display_gap_count <= 0; window_drop_count <= 0;
        end else if (stream_restart) begin
            front_bank <= 0; pending_bank <= 2; write_bank <= 1;
            pending_valid <= 0; trace_valid <= 0;
            have_seq <= 0; sample_index <= 0;
            bin_min <= 0; bin_max <= 0;
            // Restart clears epoch metadata, not cumulative diagnostic counts.
        end else begin
            front_bank <= front_next; pending_bank <= pending_next;
            write_bank <= write_next; pending_valid <= pending_valid_next;
            if (publish) trace_valid <= 1;
            if (drop_complete) window_drop_count <= sat_inc(window_drop_count);
            if (sample_valid) begin
                have_seq <= 1; last_seq <= sample_seq;
                bin_min <= next_min; bin_max <= next_max;
                if (gap) begin
                    sample_index <= 1;
                    display_gap_count <= sat_inc(display_gap_count);
                end else sample_index <= sample_index + 11'd1;
            end
        end
    end

    // Three synchronous-read/write banks. Quantization is monotonic: signed24
    // extrema are computed first, then their high signed byte is stored.
    reg [15:0] read0, read1, read2;
    always @(posedge pixel_clk) begin
        if (bin_write && pixel_rst_n) begin
            case (write_bank)
                0: bank0[sample_index[10:2]] <= bin_data;
                1: bank1[sample_index[10:2]] <= bin_data;
                2: bank2[sample_index[10:2]] <= bin_data;
            endcase
        end
        read0 <= bank0[read_address_held];
        read1 <= bank1[read_address_held];
        read2 <= bank2[read_address_held];
    end

    // 2048 samples / 48 kHz = 42.666667 ms across 512 columns.
    // Each column retains the four-sample min/max, with signed-byte FS mapping:
    // +127 -> y64, zero -> y191, -128 -> y319. No invented signal/grid pixels.
    localparam [23:0] TRACE_RGB = 24'hd8ff40;
    reg front_epoch;
    always @(posedge pixel_clk or negedge pixel_rst_n) begin
        if (!pixel_rst_n) front_epoch <= 0;
        else if (stream_restart) front_epoch <= 0;
        else if (publish) front_epoch <= ~front_epoch;
    end
    reg mask0, valid0, epoch0;
    reg [1:0] bank0_sel;
    reg [15:0] x0, y0;
    reg mask1;
    reg [23:0] rgb1;
    reg [15:0] selected_bin;
    reg signed [16:0] top_y, bottom_y, draw_top, draw_bottom;
    reg prev_valid, prev_epoch;
    reg [1:0] prev_bank;
    reg [15:0] prev_x, prev_y;
    reg signed [16:0] prev_top, prev_bottom;
    reg trace_hit;
    reg [23:0] rendered;
    always @* begin
        case (bank0_sel)
            0: selected_bin = read0;
            1: selected_bin = read1;
            default: selected_bin = read2;
        endcase
        top_y = 17'sd191 - $signed(selected_bin[7:0]);
        bottom_y = 17'sd191 - $signed(selected_bin[15:8]);
        draw_top = top_y;
        draw_bottom = bottom_y;
        // Minimal vertical join between disjoint adjacent min/max intervals.
        // A raster row change, blank/disabled token, bank publish or restart
        // cannot connect to the old column. Overlapping intervals need no fill.
        if (prev_valid && mask0 && valid0 && x0 > 16'd64 &&
            x0 == prev_x + 16'd1 && y0 == prev_y &&
            bank0_sel == prev_bank && epoch0 == prev_epoch) begin
            if (prev_bottom < top_y) draw_top = prev_bottom;
            if (prev_top > bottom_y) draw_bottom = prev_top;
        end
        trace_hit = mask0 && valid0 &&
            $signed({1'b0,y0}) >= draw_top &&
            $signed({1'b0,y0}) <= draw_bottom;
        rendered = trace_hit ? TRACE_RGB : 24'd0;
    end
    always @(posedge pixel_clk or negedge pixel_rst_n) begin
        if (!pixel_rst_n) begin
            mask0 <= 0; valid0 <= 0; bank0_sel <= 0; x0 <= 0; y0 <= 0; epoch0 <= 0;
            prev_valid <= 0; prev_epoch <= 0; prev_bank <= 0;
            prev_x <= 0; prev_y <= 0; prev_top <= 0; prev_bottom <= 0;
            mask1 <= 0; rgb1 <= 0;
            waveform_mask <= 0; waveform_r <= 0; waveform_g <= 0; waveform_b <= 0;
        end else begin
            mask0 <= data_enable && waveform_enable &&
                pixel_x >= 64 && pixel_x <= 575 && pixel_y >= 64 && pixel_y <= 319;
            valid0 <= read_valid; bank0_sel <= read_bank;
            x0 <= pixel_x_hold; y0 <= pixel_y;
            epoch0 <= publish ? ~front_epoch : front_epoch;
            prev_valid <= mask0 && valid0;
            prev_x <= x0; prev_y <= y0;
            prev_bank <= bank0_sel; prev_epoch <= epoch0;
            prev_top <= top_y; prev_bottom <= bottom_y;
            mask1 <= trace_hit; rgb1 <= rendered;
            waveform_mask <= mask1;
            {waveform_r,waveform_g,waveform_b} <= rgb1;
        end
    end
    // Right is deliberately not averaged into the left-channel trace.
    wire unused_right = ^sample_right;
endmodule
