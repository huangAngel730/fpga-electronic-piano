// Private spectrum R01: PCM sample branch, never an audio-path buffer.
// Single audio_clk domain (40 MHz); low-active async control reset.
// Default N=2048, no overlap. RAM contents need no reset: only FULL/PROCESS
// windows may be observed, and a full N writes precede each publication.
//
// Consumer protocol:
//   window_valid && window_ready claims window_bank: FULL -> PROCESS.
//   Metadata holds while valid && !ready. A newly completed bank can be
//   offered immediately after its last write edge. Claim/read/release are
//   audio-clock handshakes; read only on a later edge AFTER claim.
//   read_enable/read_bank/read_index -> read_valid/read_data exactly 1 edge.
//   release_valid frees only a bank already PROCESS before this edge.
//   Invalid reads/releases increment protocol_error_count, never grant access.
//   A release is reusable for capture starting on the FOLLOWING clock edge;
//   a read on its release edge returns old data before any later overwrite.
//
// FREE=0 FILL=1 FULL=2 PROCESS=3. Completed FULL/PROCESS windows survive
// gap/restart/epoch changes with original metadata; only partial FILL/DROP
// is canceled. Owner must consume/filter complete old epochs explicitly.
// Full banks are lossless FIFO order (at most two); PROCESS is never written.
// With no FREE bank at a window start, discard exactly N consecutive valid
// samples, even if a bank becomes FREE halfway. Count dropped_windows only
// on complete discarded windows; canceled partial drops count as cancels.
// Gap starts a new window AT the current sample. restart is level-sensitive:
// each asserted edge cancels any previous residual; a valid sample on that
// edge is sample zero of a new window. Epoch change works even without valid.
// sample_seq wraps naturally modulo 2^32 only within the same epoch.
// Counters saturate at 0xffffffff; window_id is modulo32 attempt ordinal,
// consuming one ID for every started FILL/DROP, including later cancellation.
// Saturation counts every valid PCM reduction, including discarded samples.
// PCM reduction is exactly abs/sign round-away shift6/saturate, implemented
// as one signed18 high-part increment (proof immediately below), not chained
// abs/add/negate/compare. Control/count/offer/expected-seq endpoints are flops.
// Only two bank candidates exist; no N-way combinational mux or window scan.
`timescale 1ns/1ps
module spectrum_window_capture #(
    parameter integer WINDOW_SAMPLES = 2048,
    parameter integer ADDR_BITS = $clog2(WINDOW_SAMPLES)
) (
    input  wire audio_clk,
    input  wire audio_rst_n,
    input  wire sample_valid,
    input  wire signed [23:0] pcm_mono,
    input  wire [31:0] sample_seq,
    input  wire [15:0] stream_epoch,
    input  wire stream_restart,

    output wire window_valid,
    input  wire window_ready,
    output wire window_bank,
    output wire [31:0] window_id,
    output wire [15:0] window_epoch,
    output wire [31:0] window_first_sample_seq,

    input  wire read_enable,
    input  wire read_bank,
    input  wire [ADDR_BITS-1:0] read_index,
    output logic read_valid,
    output logic signed [17:0] read_data,
    input  wire release_valid,
    input  wire release_bank,

    output wire [1:0] bank_state0,
    output wire [1:0] bank_state1,
    output wire [31:0] complete_windows,
    output wire [31:0] dropped_windows,
    output wire [31:0] gap_count,
    output wire [31:0] canceled_windows,
    output wire [31:0] restart_count,
    output wire [31:0] saturation_count,
    output wire saturation_sticky,
    output wire [31:0] blocked_cycles,
    output wire [31:0] protocol_error_count
);
    localparam logic [1:0] FREE=2'd0, FILL=2'd1, FULL=2'd2, PROCESS=2'd3;
    logic signed [17:0] memory0 [0:WINDOW_SAMPLES-1];
    logic signed [17:0] memory1 [0:WINDOW_SAMPLES-1];
    logic [1:0] state_q [0:1], state_d [0:1];
    logic [15:0] epoch_q [0:1], epoch_d [0:1];
    logic [31:0] first_q [0:1], first_d [0:1];
    logic [31:0] id_q [0:1], id_d [0:1];
    logic filling_q, filling_d, dropping_q, dropping_d;
    logic fill_bank_q, fill_bank_d;
    logic [ADDR_BITS:0] count_q, count_d;
    logic offer_q, offer_d, offer_bank_q, offer_bank_d;
    logic have_seq_q, have_seq_d, have_epoch_q, have_epoch_d;
    logic [31:0] expected_seq_q, expected_seq_d, next_id_q, next_id_d;
    logic [15:0] tracked_epoch_q, tracked_epoch_d;
    logic [31:0] complete_q, complete_d, dropped_q, dropped_d;
    logic [31:0] gap_q, gap_d, canceled_q, canceled_d;
    logic [31:0] restart_q, restart_d, saturation_q, saturation_d;
    logic sticky_q, sticky_d;
    logic [31:0] blocked_q, blocked_d, errors_q, errors_d;
    logic write_enable, write_bank;
    logic [ADDR_BITS-1:0] write_index;
    logic signed [17:0] reduced;
    logic reduce_saturated;
    logic increment_high;
    logic invalid_release, invalid_read;
    logic [1:0] error_events;
    logic [32:0] error_sum;
    logic boundary, seq_gap, free_found, free_bank;
    integer b;

    function automatic [31:0] sat_increment(input [31:0] value);
        sat_increment = (&value) ? value : value + 32'd1;
    endfunction

    assign window_valid = offer_q;
    assign window_bank = offer_bank_q;
    assign window_id = id_q[offer_bank_q];
    assign window_epoch = epoch_q[offer_bank_q];
    assign window_first_sample_seq = first_q[offer_bank_q];
    assign bank_state0=state_q[0];
    assign bank_state1=state_q[1];
    assign complete_windows=complete_q;
    assign dropped_windows=dropped_q;
    assign gap_count=gap_q;
    assign canceled_windows=canceled_q;
    assign restart_count=restart_q;
    assign saturation_count=saturation_q;
    assign saturation_sticky=sticky_q;
    assign blocked_cycles=blocked_q;
    assign protocol_error_count=errors_q;

    // Write x=64*h+r, h=arithmetic floor(x/64), 0<=r<64.
    // Positive: nearest-away is h+(r>=32). Negative: h+(r>32).
    // This is identical to sign(x)*floor((abs(x)+32)/64) for all PCM24,
    // including -8388608. No same-width abs or serial sign restoration.
    // Only positive h=131071 with r>=32 needs saturation. Negative cannot
    // round below -131072, so no wide comparator sits after the increment.
    always_comb begin
        increment_high = pcm_mono[5] && (!pcm_mono[23] || (|pcm_mono[4:0]));
        reduce_saturated = !pcm_mono[23] && (&pcm_mono[22:6]) && pcm_mono[5];
        if (reduce_saturated) reduced = 18'sd131071;
        else reduced = $signed(pcm_mono[23:6]) + $signed({17'd0,increment_high});
    end
    // Parallel event predicates and a single 33-bit saturated counter add;
    // two same-edge protocol faults do not cascade two 32-bit increments.
    always_comb begin
        invalid_release = release_valid && state_q[release_bank]!=PROCESS;
        invalid_read = read_enable &&
            ((state_q[read_bank]!=PROCESS) || ($unsigned(read_index)>=WINDOW_SAMPLES));
        error_events = {1'b0,invalid_release} + {1'b0,invalid_read};
        error_sum = {1'b0,errors_q} + {31'd0,error_events};
    end

    always_comb begin
        for (integer k=0;k<2;k=k+1) begin
            state_d[k]=state_q[k]; epoch_d[k]=epoch_q[k];
            first_d[k]=first_q[k]; id_d[k]=id_q[k];
        end
        filling_d=filling_q; dropping_d=dropping_q;
        fill_bank_d=fill_bank_q; count_d=count_q;
        offer_d=offer_q; offer_bank_d=offer_bank_q;
        have_seq_d=have_seq_q; expected_seq_d=expected_seq_q;
        have_epoch_d=1'b1; tracked_epoch_d=stream_epoch;
        next_id_d=next_id_q;
        complete_d=complete_q; dropped_d=dropped_q; gap_d=gap_q;
        canceled_d=canceled_q; restart_d=restart_q;
        saturation_d=saturation_q; sticky_d=sticky_q;
        blocked_d=blocked_q;
        errors_d=error_sum[32] ? 32'hffffffff : error_sum[31:0];
        write_enable=1'b0; write_bank=1'b0; write_index='0;
        free_found=1'b0; free_bank=1'b0;
        boundary=stream_restart || (have_epoch_q && stream_epoch!=tracked_epoch_q);
        seq_gap=sample_valid && have_seq_q && !boundary &&
                (sample_seq != expected_seq_q);

        if (offer_q && !window_ready) blocked_d=sat_increment(blocked_d);
        if (release_valid) begin
            if (state_q[release_bank]==PROCESS) state_d[release_bank]=FREE;
        end
        if (offer_q && window_ready) begin
            state_d[offer_bank_q]=PROCESS;
            offer_d=1'b0;
        end
        if (boundary || seq_gap) begin
            if (filling_q || dropping_q) canceled_d=sat_increment(canceled_d);
            if (filling_q) state_d[fill_bank_q]=FREE;
            filling_d=1'b0; dropping_d=1'b0; count_d='0;
            have_seq_d=1'b0;
            if (boundary) restart_d=sat_increment(restart_d);
            if (seq_gap) gap_d=sat_increment(gap_d);
        end

        if (sample_valid) begin
            // Precompute the next ordinal into a flop: the next sample's
            // gap cone has only equality, not a 32-bit increment + equality.
            have_seq_d=1'b1; expected_seq_d=sample_seq+32'd1;
            if (reduce_saturated) begin
                saturation_d=sat_increment(saturation_d); sticky_d=1'b1;
            end
            if (!filling_d && !dropping_d) begin
                // A PROCESS bank released now is intentionally not reusable
                // this edge, preventing any same-bank read/write ambiguity.
                // Parallel availability from registered state, not state_d's
                // release/claim priority chain. Only a canceled FILL becomes
                // additionally usable this edge; old PROCESS never does.
                if (state_q[0]==FREE ||
                    ((boundary || seq_gap) && filling_q && !fill_bank_q)) begin
                    free_found=1'b1; free_bank=1'b0;
                end else if (state_q[1]==FREE ||
                    ((boundary || seq_gap) && filling_q && fill_bank_q)) begin
                    free_found=1'b1; free_bank=1'b1;
                end
                count_d='0;
                next_id_d=next_id_q+32'd1;
                if (free_found) begin
                    filling_d=1'b1; fill_bank_d=free_bank;
                    state_d[free_bank]=FILL;
                    epoch_d[free_bank]=stream_epoch;
                    first_d[free_bank]=sample_seq;
                    id_d[free_bank]=next_id_q;
                end else dropping_d=1'b1;
            end
            if (filling_d) begin
                write_enable=1'b1; write_bank=fill_bank_d;
                write_index=count_d[ADDR_BITS-1:0];
                if (count_d==WINDOW_SAMPLES-1) begin
                    state_d[fill_bank_d]=FULL;
                    filling_d=1'b0; count_d='0;
                    complete_d=sat_increment(complete_d);
                end else count_d=count_d+1'b1;
            end else if (dropping_d) begin
                if (count_d==WINDOW_SAMPLES-1) begin
                    dropping_d=1'b0; count_d='0;
                    dropped_d=sat_increment(dropped_d);
                end else count_d=count_d+1'b1;
            end
        end
        // Locked offer: cannot change bank/metadata under backpressure when
        // the other bank becomes FULL. Queue depth is only two, so after a
        // claim the remaining FULL bank is necessarily the older candidate.
        if (!offer_d) begin
            if (state_d[0]==FULL) begin offer_d=1'b1; offer_bank_d=1'b0; end
            else if (state_d[1]==FULL) begin offer_d=1'b1; offer_bank_d=1'b1; end
        end
    end

    always_ff @(posedge audio_clk or negedge audio_rst_n) begin
        if (!audio_rst_n) begin
            for (b=0;b<2;b=b+1) begin
                state_q[b]<=FREE; epoch_q[b]<='0; first_q[b]<='0; id_q[b]<='0;
            end
            filling_q<=1'b0; dropping_q<=1'b0; fill_bank_q<=1'b0; count_q<='0;
            offer_q<=1'b0; offer_bank_q<=1'b0;
            have_seq_q<=1'b0; expected_seq_q<='0;
            have_epoch_q<=1'b0; tracked_epoch_q<='0; next_id_q<='0;
            complete_q<='0; dropped_q<='0; gap_q<='0; canceled_q<='0;
            restart_q<='0; saturation_q<='0; sticky_q<=1'b0;
            blocked_q<='0; errors_q<='0;
        end else begin
            for (b=0;b<2;b=b+1) begin
                state_q[b]<=state_d[b]; epoch_q[b]<=epoch_d[b];
                first_q[b]<=first_d[b]; id_q[b]<=id_d[b];
            end
            filling_q<=filling_d; dropping_q<=dropping_d;
            fill_bank_q<=fill_bank_d; count_q<=count_d;
            offer_q<=offer_d; offer_bank_q<=offer_bank_d;
            have_seq_q<=have_seq_d; expected_seq_q<=expected_seq_d;
            have_epoch_q<=have_epoch_d; tracked_epoch_q<=tracked_epoch_d;
            next_id_q<=next_id_d;
            complete_q<=complete_d; dropped_q<=dropped_d; gap_q<=gap_d;
            canceled_q<=canceled_d; restart_q<=restart_d;
            saturation_q<=saturation_d; sticky_q<=sticky_d;
            blocked_q<=blocked_d; errors_q<=errors_d;
        end
    end

    // No RAM reset or initial contents: these infer two bounded sample banks.
    always_ff @(posedge audio_clk) begin
        if (audio_rst_n && write_enable) begin
            if (write_bank) memory1[write_index]<=reduced;
            else memory0[write_index]<=reduced;
        end
    end
    always_ff @(posedge audio_clk or negedge audio_rst_n) begin
        if (!audio_rst_n) begin read_valid<=1'b0; read_data<='0; end
        else begin
            read_valid<=1'b0;
            if (read_enable && state_q[read_bank]==PROCESS &&
                $unsigned(read_index)<WINDOW_SAMPLES) begin
                read_valid<=1'b1;
                if (read_bank) read_data<=memory1[read_index];
                else read_data<=memory0[read_index];
            end
        end
    end
`ifndef SYNTHESIS
    initial begin
        if (WINDOW_SAMPLES<2 || ADDR_BITS<1 || (2**ADDR_BITS)<WINDOW_SAMPLES)
            $fatal(1,"spectrum_window_capture invalid finite geometry");
    end
`endif
endmodule
