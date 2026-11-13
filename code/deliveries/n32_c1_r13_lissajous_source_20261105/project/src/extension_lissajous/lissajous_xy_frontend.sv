// Independent candidate. All ports are synchronous to the same pixel clock.
// rst_n: active-low SYNCHRONOUS reset. No ready/backpressure or audio feedback.
// Accepted sample at edge N -> eligible point after edge N+3 (four captures).
// Control/gap restart flushes old in-flight points; a same-edge active packet
// is retained as the new seed. Delay counts valid packets, not pixel cycles.
module lissajous_xy_frontend (
    input  wire clk,
    input  wire rst_n,
    input  wire enable,
    input  wire activity,
    input  wire stream_restart,
    input  wire sample_valid,
    input  wire [31:0] sample_seq,
    input  wire signed [23:0] pcm_left,
    input  wire signed [23:0] pcm_right,
    input  wire stereo_mode,
    input  wire [7:0] delay_samples,
    input  wire [2:0] gain_shift,
    input  wire [1:0] timbre_id,
    output logic point_valid,
    output logic [7:0] point_x,
    output logic [7:0] point_y,
    output logic [1:0] point_timbre,
    output logic point_restart,
    output logic [31:0] gap_count
);
    wire [2:0] gain_clamped = gain_shift > 3'd4 ? 3'd4 : gain_shift;
    logic previous_enable, previous_activity, previous_stereo;
    logic [7:0] previous_delay;
    logic [2:0] previous_gain;
    logic [1:0] previous_timbre;
    logic seq_seen;
    logic [31:0] expected_seq;
    wire running = enable && activity;
    wire accept_sample = running && sample_valid;
    wire control_change = stream_restart || enable != previous_enable ||
        activity != previous_activity || stereo_mode != previous_stereo ||
        delay_samples != previous_delay || gain_clamped != previous_gain ||
        timbre_id != previous_timbre;
    wire sequence_gap = accept_sample && seq_seen && !control_change &&
        sample_seq != expected_seq;
    wire restart_now = control_change || sequence_gap;

    logic [7:0] write_pointer;
    // Saturates at255 prior packets; RAM has one extra slot for current write.
    logic [7:0] history_count;
    wire [7:0] write_address = restart_now ? 8'd0 : write_pointer;
    wire [7:0] read_address = write_pointer - delay_samples;
    wire need_history = !stereo_mode && delay_samples != 8'd0;
    wire history_ready = !restart_now && history_count >= delay_samples;
    wire read_history = accept_sample && need_history && history_ready;
    wire eligible_sample = accept_sample && (!need_history || history_ready);

    // Simple dual-port synchronous RAM inference. No memory or read-data reset.
    // For d>0, modulo256 read_address differs from this packet's write_address.
    // d=0 and stereo use registered current PCM instead of collision semantics.
    logic signed [23:0] history_ram [0:255] /* synthesis syn_ramstyle = "block_ram" */;
    logic signed [23:0] history_read_data;
    always_ff @(posedge clk) begin
        if (rst_n && accept_sample)
            history_ram[write_address] <= pcm_left;
    end
    always_ff @(posedge clk) begin
        if (rst_n && read_history)
            history_read_data <= history_ram[read_address];
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            previous_enable <= 1'b0;
            previous_activity <= 1'b0;
            previous_stereo <= 1'b0;
            previous_delay <= 8'd27;
            previous_gain <= 3'd0;
            previous_timbre <= 2'd0;
            seq_seen <= 1'b0;
            expected_seq <= 32'd0;
            write_pointer <= 8'd0;
            history_count <= 8'd0;
            gap_count <= 32'd0;
        end else begin
            previous_enable <= enable;
            previous_activity <= activity;
            previous_stereo <= stereo_mode;
            previous_delay <= delay_samples;
            previous_gain <= gain_clamped;
            previous_timbre <= timbre_id;
            if (sequence_gap && gap_count != 32'hffffffff)
                gap_count <= gap_count + 32'd1;
            if (!running || restart_now) begin
                write_pointer <= accept_sample ? 8'd1 : 8'd0;
                history_count <= accept_sample ? 8'd1 : 8'd0;
                seq_seen <= accept_sample;
                expected_seq <= accept_sample ? sample_seq + 32'd1 : 32'd0;
            end else if (accept_sample) begin
                write_pointer <= write_pointer + 8'd1;
                if (history_count != 8'hff)
                    history_count <= history_count + 8'd1;
                seq_seen <= 1'b1;
                expected_seq <= sample_seq + 32'd1;
            end
        end
    end

    logic valid_s0, valid_s1, valid_s2;
    logic signed [23:0] left_s0, bypass_y_s0;
    logic use_history_s0;
    logic [2:0] gain_s0;
    logic [1:0] timbre_s0, timbre_s1, timbre_s2;
    logic signed [11:0] shifted_x_s1, shifted_y_s1;
    logic signed [7:0] quant_x_s2, quant_y_s2;

    // Arithmetic right shift always discards at least 12 bits. Select
    // the five fixed shifts with sign extension, then clamp in stage 2.
    function automatic signed [11:0] scale_pcm(
        input signed [23:0] value,
        input [2:0] gain
    );
        case (gain)
            3'd0: scale_pcm = {{4{value[23]}}, value[23:16]};
            3'd1: scale_pcm = {{3{value[23]}}, value[23:15]};
            3'd2: scale_pcm = {{2{value[23]}}, value[23:14]};
            3'd3: scale_pcm = {{1{value[23]}}, value[23:13]};
            default: scale_pcm = value[23:12];
        endcase
    endfunction

    function automatic signed [7:0] saturate_q7(input signed [11:0] value);
        if (value > 12'sd127)
            saturate_q7 = 8'sd127;
        else if (value < -12'sd128)
            saturate_q7 = -8'sd128;
        else
            saturate_q7 = value[7:0];
    endfunction

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            valid_s0 <= 1'b0;
            valid_s1 <= 1'b0;
            valid_s2 <= 1'b0;
            left_s0 <= 24'sd0;
            bypass_y_s0 <= 24'sd0;
            use_history_s0 <= 1'b0;
            gain_s0 <= 3'd0;
            timbre_s0 <= 2'd0;
            timbre_s1 <= 2'd0;
            timbre_s2 <= 2'd0;
            shifted_x_s1 <= 12'sd0;
            shifted_y_s1 <= 12'sd0;
            quant_x_s2 <= 8'sd0;
            quant_y_s2 <= 8'sd0;
            point_valid <= 1'b0;
            point_restart <= 1'b0;
            point_x <= 8'd128;
            point_y <= 8'd127;
            point_timbre <= 2'd0;
        end else begin
            valid_s0 <= eligible_sample;
            if (accept_sample) begin
                left_s0 <= pcm_left;
                bypass_y_s0 <= stereo_mode ? pcm_right : pcm_left;
                use_history_s0 <= need_history;
                gain_s0 <= gain_clamped;
                timbre_s0 <= timbre_id;
            end
            point_restart <= restart_now;
            if (!running || restart_now) begin
                valid_s1 <= 1'b0;
                valid_s2 <= 1'b0;
                point_valid <= 1'b0;
            end else begin
                valid_s1 <= valid_s0;
                shifted_x_s1 <= scale_pcm(left_s0, gain_s0);
                shifted_y_s1 <= scale_pcm(use_history_s0 ? history_read_data : bypass_y_s0,
                                          gain_s0);
                timbre_s1 <= timbre_s0;
                valid_s2 <= valid_s1;
                quant_x_s2 <= saturate_q7(shifted_x_s1);
                quant_y_s2 <= saturate_q7(shifted_y_s1);
                timbre_s2 <= timbre_s1;
                point_valid <= valid_s2;
                if (valid_s2) begin
                    // Offset-binary mapping: x=q+128; y=127-q, exactly8 bits.
                    point_x <= quant_x_s2 ^ 8'h80;
                    point_y <= ~(quant_y_s2 ^ 8'h80);
                    point_timbre <= timbre_s2;
                end
            end
        end
    end
endmodule
