`timescale 1ns/1ps
// Verification-only monitor for zero-delay RTL and stable edge stimulus.
// Compile outside production. Enable with +C1_PCM_CHECK.
module c1_pcm_checker #(
    parameter integer MIN_SAMPLES = 128,
    parameter integer MAX_SAMPLES = 400000
) (
    input wire core_clk, pixel_clk,
    input wire tx_rst_n, tx_frame, tx_valid,
    input wire signed [23:0] tx_left, tx_right,
    input wire signed [15:0] tx_adopted_left, tx_adopted_right,
    input wire observer_rst_n, observer_frame, observer_valid,
    input wire signed [23:0] observer_in_left, observer_in_right,
    input wire [31:0] observer_seq,
    input wire signed [23:0] observer_left, observer_right,
    input wire spectrum_valid,
    input wire [31:0] spectrum_seq,
    input wire signed [23:0] spectrum_left,
    input wire waveform_rst_n, waveform_valid,
    input wire [31:0] waveform_seq,
    input wire signed [23:0] waveform_left, waveform_right
);
    bit enabled, require_stereo;
    bit expect_tx, expect_observer;
    logic signed [15:0] expected_dac_left, expected_dac_right;
    logic signed [23:0] expected_left, expected_right;
    logic [31:0] next_seq = 0;
    logic [47:0] pcm_by_seq [int unsigned];
    integer tx_count = 0, observer_count = 0, spectrum_count = 0;
    integer waveform_count = 0, nonzero_count = 0, stereo_count = 0;

    initial begin
        enabled = $test$plusargs("C1_PCM_CHECK");
        require_stereo = $test$plusargs("C1_PCM_REQUIRE_STEREO");
    end

    function automatic logic signed [15:0] dac_quantize(input logic signed [23:0] x);
        integer value;
        begin
            value = $signed(x);
            value = (value + 128) >>> 8;
            if (value > 32767) dac_quantize = 16'sh7fff;
            else if (value < -32768) dac_quantize = 16'sh8000;
            else dac_quantize = value[15:0];
        end
    endfunction

    always @(posedge core_clk) if (enabled) begin
        expect_tx = tx_rst_n && tx_frame && tx_valid;
        expect_observer = observer_rst_n && observer_frame;
        if (!observer_rst_n) begin
            pcm_by_seq.delete();
            next_seq = 0;
        end else if (tx_rst_n) begin
            if (observer_frame !== tx_frame || (tx_frame && tx_valid !== 1'b1))
                $fatal(1, "C1 PCM capture edge mismatch");
            if (observer_frame && ({observer_in_left,observer_in_right} !== {tx_left,tx_right}))
                $fatal(1, "C1 PCM source mismatch at shared frame edge");
            if (spectrum_valid !== observer_valid)
                $fatal(1, "C1 spectrum valid mismatches shared observer");
            if (observer_valid) begin
                if ({spectrum_seq,spectrum_left} !== {observer_seq,observer_left})
                    $fatal(1, "C1 spectrum did not receive observed left PCM/sequence");
                spectrum_count = spectrum_count + 1;
            end
        end
        if (expect_tx && $isunknown({tx_left,tx_right}))
            $fatal(1, "C1 unknown DAC input");
        expected_dac_left = dac_quantize(tx_left);
        expected_dac_right = dac_quantize(tx_right);
        expected_left = observer_in_left;
        expected_right = observer_in_right;
        #1;
        if (expect_tx) begin
            if ({tx_adopted_left,tx_adopted_right} !== {expected_dac_left,expected_dac_right})
                $fatal(1, "C1 DAC register adoption mismatch");
            tx_count = tx_count + 1;
            if (tx_count > MAX_SAMPLES) $fatal(1, "C1 bounded monitor limit");
        end
        if (observer_valid !== expect_observer)
            $fatal(1, "C1 observer valid did not follow frame edge");
        if (expect_observer) begin
            if ($isunknown({expected_left,expected_right}) ||
                {observer_seq,observer_left,observer_right} !== {next_seq,expected_left,expected_right})
                $fatal(1, "C1 observer capture/sequence mismatch");
            pcm_by_seq[next_seq] = {expected_left,expected_right};
            next_seq = next_seq + 1;
            observer_count = observer_count + 1;
            if (expected_left != 0 || expected_right != 0) nonzero_count = nonzero_count + 1;
            if (expected_left != expected_right) stereo_count = stereo_count + 1;
        end
    end

    // Check data as the waveform renderer consumes it. CDC transport may skip
    // sequence numbers on overflow or display reset. It must not alter PCM.
    always @(posedge pixel_clk) if (enabled && waveform_rst_n && observer_rst_n && waveform_valid) begin
        if ($isunknown(waveform_seq) || !pcm_by_seq.exists(waveform_seq))
            $fatal(1, "C1 waveform consumes unobserved sequence");
        if ({waveform_left,waveform_right} !== pcm_by_seq[waveform_seq])
            $fatal(1, "C1 waveform input differs from source frame");
        waveform_count = waveform_count + 1;
    end

    final if (enabled) begin
        if (tx_count >= MIN_SAMPLES && observer_count >= MIN_SAMPLES &&
            spectrum_count >= MIN_SAMPLES && waveform_count >= MIN_SAMPLES &&
            nonzero_count > 0 && (!require_stereo || stereo_count > 0))
            $display("PASS C1_PCM_TAPS tx=%0d observer=%0d spectrum=%0d waveform=%0d nonzero=%0d stereo=%0d",
                tx_count,observer_count,spectrum_count,waveform_count,nonzero_count,stereo_count);
        else
            $display("INCOMPLETE C1_PCM_TAPS tx=%0d observer=%0d spectrum=%0d waveform=%0d nonzero=%0d",
                tx_count,observer_count,spectrum_count,waveform_count,nonzero_count);
    end
endmodule

// Opt-in bind for C1 source top and a candidate retaining these instance names.
`ifdef C1_PCM_CHECK_BIND
`define C1_BRIDGE u_score_visual.u_display.u_waveform_overlay.u_shared_waveform.u_bridge
`define C1_WAVE u_score_visual.u_display.u_waveform_overlay.u_shared_waveform.u_renderer
`define C1_SPEC u_score_visual.u_display.u_waveform_overlay.u_shared_spectrum
`define C1_TX u_audio.u_i2s_tx
bind pro_audio_minimal_top c1_pcm_checker u_c1_pcm_checker (
    .core_clk(core_clk), .pixel_clk(pixel_clk),
    .tx_rst_n(`C1_TX.rst_n), .tx_frame(`C1_TX.frame_tick), .tx_valid(`C1_TX.valid),
    .tx_left(`C1_TX.pcm_left), .tx_right(`C1_TX.pcm_right),
    .tx_adopted_left(`C1_TX.sample_left), .tx_adopted_right(`C1_TX.sample_right),
    .observer_rst_n(`C1_BRIDGE.observer_reset_done),
    .observer_frame(`C1_BRIDGE.audio_frame_load),
    .observer_in_left(`C1_BRIDGE.audio_play_left), .observer_in_right(`C1_BRIDGE.audio_play_right),
    .observer_valid(`C1_BRIDGE.observed_valid), .observer_seq(`C1_BRIDGE.observed_seq),
    .observer_left(`C1_BRIDGE.observed_left), .observer_right(`C1_BRIDGE.observed_right),
    .spectrum_valid(`C1_SPEC.sample_valid), .spectrum_seq(`C1_SPEC.sample_seq), .spectrum_left(`C1_SPEC.pcm_mono),
    .waveform_rst_n(`C1_WAVE.pixel_rst_n), .waveform_valid(`C1_WAVE.sample_valid),
    .waveform_seq(`C1_WAVE.sample_seq), .waveform_left(`C1_WAVE.sample_left), .waveform_right(`C1_WAVE.sample_right)
);
`undef C1_BRIDGE
`undef C1_WAVE
`undef C1_SPEC
`undef C1_TX
`endif
