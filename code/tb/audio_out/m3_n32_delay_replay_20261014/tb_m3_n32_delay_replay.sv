`timescale 1ns/1ps

module tb_m3_n32_delay_replay;
    localparam integer MAX_VECTORS = 2048;
    localparam integer CLOCK_PERIOD_NS = 25;
    reg clk = 1'b0;
    reg pixel_clk = 1'b0;
    reg rst_n = 1'b0;
    reg display_rst_n = 1'b0;
    always #(CLOCK_PERIOD_NS/2.0) clk = ~clk;
    always #20 pixel_clk = ~pixel_clk;

    reg [191:0] vectors [0:MAX_VECTORS-1];
    integer vector_count;
    integer vector_index;
    integer trace_fd;
    integer sim_cycle;
    integer accepted_count;
    integer config_step;
    integer post_done_frames;
    integer hold_edges;
    reg [31:0] hold_request_id;
    reg hold_target;
    reg cancel_target;
    reg [31:0] cancel_request_id;
    reg [2047:0] committed_low_ids;
    integer bclk_rises;
    integer lrck_edges;
    reg bclk_d;
    reg lrck_d;
    reg [2047:0] request_logged;
    reg [2047:0] accepted_seen;
    reg [2047:0] first_logged;

    string vector_path;
    string trace_path;

    wire [191:0] current_vector = vectors[vector_index];
    wire [7:0] src_lifetime = current_vector[191:184];
    wire [31:0] src_k_line = current_vector[183:152];
    wire [31:0] src_p_line = current_vector[151:120];
    wire [31:0] src_cycle = current_vector[119:88];
    wire [31:0] src_id = current_vector[87:56];
    wire signed [23:0] src_left = current_vector[55:32];
    wire signed [23:0] src_right = current_vector[31:8];
    wire src_clipped = current_vector[7];

    wire candidate_cancel;
    wire candidate_sample_valid;
    wire candidate_sample_ready;
    wire [31:0] candidate_sample_id;
    wire candidate_result_valid;
    wire candidate_result_ready;
    wire [31:0] candidate_result_id;
    wire signed [23:0] candidate_left;
    wire signed [23:0] candidate_right;
    wire candidate_clipped;
    wire signed [23:0] play_left, play_right;
    wire bclk, lrck, din, frame_tick, commit_pulse;
    wire [31:0] frame_count, frame_request_count, commit_count, underrun_count, clip_count;
    wire [31:0] committed_id;
    wire signed [23:0] committed_left, committed_right;
    wire committed_clip;
    wire observed_valid;
    wire [31:0] observed_seq;
    wire signed [23:0] observed_left, observed_right;
    wire waveform_rst_n, stream_restart, sample_valid;
    wire [31:0] sample_seq;
    wire signed [23:0] sample_left, sample_right;
    wire [31:0] observation_drop_count;

    wire delay_input_ready;
    wire delay_config_ready;
    wire delay_output_valid;
    wire [31:0] delay_output_id;
    wire signed [23:0] delay_output_left, delay_output_right;
    wire delay_upstream_clip_left, delay_upstream_clip_right;
    wire delay_effect_clip_left, delay_effect_clip_right;
    wire delay_feedback_clip_left, delay_feedback_clip_right;
    wire delay_clip_left, delay_clip_right;
    wire delay_busy;

    reg delay_config_valid;
    reg delay_config_enable;
    reg [15:0] delay_config_samples;
    reg [14:0] delay_config_dry, delay_config_wet, delay_config_feedback;

    wire have_vector = vector_index < vector_count;
    wire delay_input_valid = candidate_sample_valid && have_vector && !delay_config_valid;
    assign candidate_sample_ready = have_vector && !delay_config_valid && delay_input_ready;

    wire hold_gate = hold_target && delay_output_valid &&
                     delay_output_id == hold_request_id && hold_edges < 5;
    wire cancel_gate = cancel_target && delay_output_id == cancel_request_id;
    assign candidate_result_valid = delay_output_valid && !hold_gate && !cancel_gate;
    assign candidate_result_id = delay_output_id;
    assign candidate_left = delay_output_left;
    assign candidate_right = delay_output_right;
    assign candidate_clipped = delay_clip_left || delay_clip_right;
    wire delay_output_ready = candidate_result_ready && !hold_gate && !cancel_gate;

    m1td_stereo_delay delay_dut (
        .clk(clk), .rst_n(rst_n), .frame_tick(frame_tick),
        .current_req_id(candidate_sample_id),
        .input_valid(delay_input_valid), .input_ready(delay_input_ready),
        .input_id(candidate_sample_id), .input_left(src_left), .input_right(src_right),
        .input_clipped_left(src_clipped), .input_clipped_right(src_clipped),
        .config_valid(delay_config_valid), .config_ready(delay_config_ready),
        .config_enable(delay_config_enable), .config_delay_samples(delay_config_samples),
        .config_dry_gain(delay_config_dry), .config_wet_gain(delay_config_wet),
        .config_feedback(delay_config_feedback),
        .output_valid(delay_output_valid), .output_ready(delay_output_ready),
        .output_id(delay_output_id), .output_left(delay_output_left),
        .output_right(delay_output_right),
        .upstream_clipped_left(delay_upstream_clip_left),
        .upstream_clipped_right(delay_upstream_clip_right),
        .effect_clipped_left(delay_effect_clip_left),
        .effect_clipped_right(delay_effect_clip_right),
        .feedback_clipped_left(delay_feedback_clip_left),
        .feedback_clipped_right(delay_feedback_clip_right),
        .clipped_left(delay_clip_left), .clipped_right(delay_clip_right),
        .busy(delay_busy)
    );

    m2_n32_output_transport #(.OBS_DEPTH(32)) transport_dut (
        .clk(clk), .pixel_clk(pixel_clk), .rst_n(rst_n), .display_rst_n(display_rst_n),
        .candidate_cancel(candidate_cancel),
        .candidate_sample_valid(candidate_sample_valid),
        .candidate_sample_ready(candidate_sample_ready),
        .candidate_sample_id(candidate_sample_id),
        .candidate_result_valid(candidate_result_valid),
        .candidate_result_ready(candidate_result_ready),
        .candidate_result_id(candidate_result_id),
        .candidate_left(candidate_left), .candidate_right(candidate_right),
        .candidate_clipped(candidate_clipped),
        .play_left(play_left), .play_right(play_right),
        .bclk(bclk), .lrck(lrck), .din(din), .frame_tick(frame_tick),
        .commit_pulse(commit_pulse), .frame_count(frame_count),
        .frame_request_count(frame_request_count), .commit_count(commit_count),
        .underrun_count(underrun_count), .clip_count(clip_count),
        .committed_id(committed_id), .committed_left(committed_left),
        .committed_right(committed_right), .committed_clip(committed_clip),
        .observed_valid(observed_valid), .observed_seq(observed_seq),
        .observed_left(observed_left), .observed_right(observed_right),
        .waveform_rst_n(waveform_rst_n), .stream_restart(stream_restart),
        .sample_valid(sample_valid), .sample_seq(sample_seq),
        .sample_left(sample_left), .sample_right(sample_right),
        .observation_drop_count(observation_drop_count)
    );

    task set_config;
        input enable_value;
        input [15:0] delay_value;
        input [14:0] dry_value;
        input [14:0] wet_value;
        input [14:0] feedback_value;
        begin
            delay_config_enable = enable_value;
            delay_config_samples = delay_value;
            delay_config_dry = dry_value;
            delay_config_wet = wet_value;
            delay_config_feedback = feedback_value;
        end
    endtask

    always @* begin
        delay_config_valid = 1'b0;
        set_config(1'b0, 16'd1, 15'd32767, 15'd0, 15'd0);
        case (config_step)
            0: if (accepted_count >= 8) begin
                delay_config_valid = 1'b1;
                set_config(1'b1, 16'd4, 15'd32767, 15'd16384, 15'd4096);
            end
            1: if (accepted_count >= 40) begin
                delay_config_valid = 1'b1;
                set_config(1'b1, 16'd7, 15'd32767, 15'd16384, 15'd4096);
            end
            2: if (accepted_count >= 72) begin
                delay_config_valid = 1'b1;
                set_config(1'b0, 16'd7, 15'd32767, 15'd0, 15'd0);
            end
            3: if (accepted_count >= 80) begin
                delay_config_valid = 1'b1;
                set_config(1'b1, 16'd1023, 15'd24576, 15'd16384, 15'd0);
            end
            4: if (accepted_count >= 100) begin
                delay_config_valid = 1'b1;
                set_config(1'b1, 16'd1023, 15'd32767, 15'd8192, 15'd0);
            end
            default: begin end
        endcase
    end

    initial begin
        if (!$value$plusargs("VECTORS=%s", vector_path)) $fatal(1, "VECTORS plusarg missing");
        if (!$value$plusargs("TRACE=%s", trace_path)) $fatal(1, "TRACE plusarg missing");
        if (!$value$plusargs("COUNT=%d", vector_count)) $fatal(1, "COUNT plusarg missing");
        if (vector_count < 1105 || vector_count > MAX_VECTORS)
            $fatal(1, "COUNT outside bounded replay range");
        $readmemh(vector_path, vectors, 0, vector_count-1);
        trace_fd = $fopen(trace_path, "w");
        if (trace_fd == 0) $fatal(1, "cannot open trace");
        vector_index = 0;
        accepted_count = 0;
        config_step = 0;
        post_done_frames = 0;
        sim_cycle = 0;
        hold_edges = 0;
        hold_request_id = 0;
        hold_target = 0;
        cancel_target = 0;
        cancel_request_id = 0;
        committed_low_ids = 0;
        request_logged = 0;
        accepted_seen = 0;
        first_logged = 0;
        bclk_rises = 0;
        lrck_edges = 0;
        bclk_d = 0;
        lrck_d = 0;
        repeat (8) @(posedge clk);
        rst_n <= 1'b1;
        display_rst_n <= 1'b1;
    end

    always @(posedge clk) begin
        sim_cycle <= sim_cycle + 1;
        bclk_d <= bclk;
        lrck_d <= lrck;
        if (rst_n) begin
            if (bclk && !bclk_d) bclk_rises <= bclk_rises + 1;
            if (lrck != lrck_d) lrck_edges <= lrck_edges + 1;
            if ((bclk !== 1'b0 && bclk !== 1'b1) ||
                (lrck !== 1'b0 && lrck !== 1'b1) ||
                (din !== 1'b0 && din !== 1'b1))
                $fatal(1, "I2S_X_AT_CYCLE_%0d", sim_cycle);

            if (delay_config_valid && delay_config_ready) begin
                $fwrite(trace_fd, "CFG %0d %0d %0d %0d %0d %0d\n",
                    sim_cycle, delay_config_enable, delay_config_samples,
                    delay_config_dry, delay_config_wet, delay_config_feedback);
                config_step <= config_step + 1;
            end

            if (candidate_sample_valid && candidate_sample_id < 2048 &&
                !request_logged[candidate_sample_id]) begin
                request_logged[candidate_sample_id] <= 1'b1;
                $fwrite(trace_fd, "REQUEST %0d %08x\n", sim_cycle, candidate_sample_id);
            end

            if (delay_input_valid && delay_input_ready) begin
                if (candidate_sample_id < 2048 && accepted_seen[candidate_sample_id])
                    $fatal(1, "DUPLICATE_TRANSPORT_REQUEST_ID");
                if (candidate_sample_id < 2048)
                    accepted_seen[candidate_sample_id] <= 1'b1;
                $fwrite(trace_fd,
                    "REQ %0d %08x %0d %0d %0d %0d %0d %08x %0d %0d %0d\n",
                    sim_cycle, candidate_sample_id, vector_index, src_lifetime,
                    src_k_line, src_p_line, src_cycle, src_id,
                    $signed(src_left), $signed(src_right), src_clipped);
                if (accepted_count == 10) begin
                    hold_target <= 1'b1;
                    hold_request_id <= candidate_sample_id;
                    hold_edges <= 0;
                end
                if (accepted_count == 12) begin
                    cancel_target <= 1'b1;
                    cancel_request_id <= candidate_sample_id;
                end
                vector_index <= vector_index + 1;
                accepted_count <= accepted_count + 1;
            end

            if (delay_output_valid && delay_output_id < 2048 &&
                !first_logged[delay_output_id]) begin
                first_logged[delay_output_id] <= 1'b1;
                $fwrite(trace_fd, "FIRST %0d %08x %0d %0d %0d\n",
                    sim_cycle, delay_output_id, $signed(delay_output_left),
                    $signed(delay_output_right), delay_clip_left || delay_clip_right);
            end

            if (hold_gate) begin
                $fwrite(trace_fd, "HOLD %0d %08x %0d %0d %0d\n",
                    sim_cycle, delay_output_id, $signed(delay_output_left),
                    $signed(delay_output_right), delay_clip_left || delay_clip_right);
                hold_edges <= hold_edges + 1;
            end

            if (candidate_result_valid && candidate_result_ready) begin
                $fwrite(trace_fd, "RES %0d %08x %0d %0d %0d\n",
                    sim_cycle, candidate_result_id, $signed(candidate_left),
                    $signed(candidate_right), candidate_clipped);
            end

            if (commit_pulse) begin
                if (committed_id < 2048 && committed_low_ids[committed_id])
                    $fatal(1, "DUPLICATE_COMMIT_ID");
                if (committed_id < 2048)
                    committed_low_ids[committed_id] <= 1'b1;
                $fwrite(trace_fd, "COM %0d %08x %0d %0d %0d\n",
                    sim_cycle, committed_id, $signed(committed_left),
                    $signed(committed_right), committed_clip);
                if (hold_target && committed_id == hold_request_id)
                    hold_target <= 1'b0;
            end

            if (frame_tick) begin
                $fwrite(trace_fd, "FRAME %0d %0d %0d %0d\n",
                    sim_cycle, frame_count, $signed(play_left), $signed(play_right));
                if (cancel_target) begin
                    $fwrite(trace_fd, "CANCEL %0d %08x\n", sim_cycle, cancel_request_id);
                    cancel_target <= 1'b0;
                end
                if (vector_index >= vector_count)
                    post_done_frames <= post_done_frames + 1;
            end
            if (observed_valid)
                $fwrite(trace_fd, "OBS %0d %0d %0d %0d\n", sim_cycle,
                    observed_seq, $signed(observed_left), $signed(observed_right));

            if (post_done_frames >= 4 && !delay_busy) begin
                $fwrite(trace_fd,
                    "I2S %0d %0d %0d %0d %0d\n", sim_cycle, bclk_rises,
                    lrck_edges, observation_drop_count, clip_count);
                $fwrite(trace_fd,
                    "END %0d %0d %0d %0d %0d %0d %0d\n", sim_cycle,
                    accepted_count, commit_count, frame_count,
                    underrun_count, clip_count, observation_drop_count);
                $fclose(trace_fd);
                $finish;
            end
            if (sim_cycle > 1400000) $fatal(1, "SIMULATION_CYCLE_BUDGET");
        end
    end

    always @(posedge pixel_clk) begin
        if (display_rst_n && sample_valid)
            $fwrite(trace_fd, "PX %0d %0d %0d %0d\n", sim_cycle,
                sample_seq, $signed(sample_left), $signed(sample_right));
    end
endmodule
