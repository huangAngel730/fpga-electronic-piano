// R15 hold candidate: exact s18 real^2+imag^2 -> u37, registered squares,
// then TWO registered partial sums, then registered carry combination.
// Three elastic captures, throughput1/clock; one extra core latency vs baseline.
// Low/high partial-sum FFs separate both square outputs from the final sum
// and remove the full-width two-DSP MAC/cascade inference pattern.
// Synchronous active-low reset. cancel flushes partial stream explicitly.
// Bad order/metadata/scale is consumed but NOT emitted; a new valid first/bin0
// resynchronizes. Already-emitted prefix has no last, so a complete-snapshot
// collector must reject/discard it. This module does not publish a RAM bank.
module spectrum_power_stream (
    input wire audio_clk,
    input wire audio_rst_n,
    input wire cancel,
    input wire fft_valid,
    output wire fft_ready,
    input wire fft_first,
    input wire fft_last,
    input wire [10:0] fft_bin_index,
    input wire signed [17:0] fft_real,
    input wire signed [17:0] fft_imag,
    input wire [31:0] fft_spectrum_id,
    input wire [15:0] fft_epoch,
    input wire [31:0] fft_first_sample_seq,
    input wire [7:0] fft_scale_id,
    output wire result_valid,
    input wire result_ready,
    output reg result_first,
    output reg result_last,
    output reg [31:0] spectrum_id,
    output reg [15:0] result_epoch,
    output reg [31:0] first_sample_seq,
    output reg [10:0] bin_index,
    output reg [36:0] bin_power,
    output reg [7:0] scale_id,
    output reg [31:0] completed_spectrum_count,
    output reg [31:0] protocol_error_count,
    output reg [31:0] dropped_spectrum_count,
    output reg [31:0] blocked_cycle_count
);
    reg held_valid, products_valid, partial_valid, active, discarding;
    (* syn_keep=1, syn_preserve=1 *) reg [35:0] product_re,product_im;
    (* syn_keep=1, syn_preserve=1 *) reg [18:0] partial_low,partial_high;
    reg partial_first,partial_last;
    reg [31:0] partial_id,partial_seq;
    reg [15:0] partial_epoch;
    reg [10:0] partial_index;
    reg [7:0] partial_scale;
    reg product_first,product_last;
    reg [31:0] product_id,product_seq;
    reg [15:0] product_epoch;
    reg [10:0] product_index;
    reg [7:0] product_scale;
    reg [10:0] expected_index;
    reg [31:0] active_id, active_seq;
    reg [15:0] active_epoch;
    wire signed [35:0] square_re=$signed(fft_real)*$signed(fft_real);
    wire signed [35:0] square_im=$signed(fft_imag)*$signed(fft_imag);
    wire start_ok=fft_first && !fft_last && fft_bin_index==0 && fft_scale_id==1;
    wire next_ok=!fft_first && fft_bin_index==expected_index && fft_last==(expected_index==1024) &&
                 fft_scale_id==1 && fft_spectrum_id==active_id && fft_epoch==active_epoch &&
                 fft_first_sample_seq==active_seq;
    wire accepted_fields=start_ok || (active && next_ok);
    // Protect the full known short-path consumer class, not three isolated bits.
    wire [31:0] product_seq_input;
    spectrum_hold_input_luts #(.WIDTH(32)) u_product_seq_hold(
        .data_in(fft_first_sample_seq),.data_out(product_seq_input));
    wire output_space=!held_valid || result_ready;
    wire partial_space=!partial_valid || output_space;
    // Each partial add is19 bits. The high sum is <=2^19-2, so adding
    // the low carry (0/1) fits19; concatenating low18 is an exact u37 sum.
    wire [18:0] corrected_high=partial_high+{18'd0,partial_low[18]};
    function automatic [31:0] increment;
        input [31:0] value;
        begin increment=(value==32'hffffffff)?value:value+1'b1; end
    endfunction
    function automatic [31:0] increment_two;
        input [31:0] value;
        begin increment_two=(value>=32'hfffffffe)?32'hffffffff:value+32'd2; end
    endfunction
    assign result_valid=held_valid && audio_rst_n && !cancel;
    assign fft_ready=audio_rst_n && !cancel && (!products_valid || partial_space);
    always @(posedge audio_clk) begin
        if(!audio_rst_n) begin
            held_valid<=0; products_valid<=0; partial_valid<=0; active<=0; discarding<=0; expected_index<=0;
            product_re<=0; product_im<=0; product_first<=0; product_last<=0;
            partial_low<=0; partial_high<=0; partial_first<=0; partial_last<=0;
            partial_id<=0; partial_seq<=0; partial_epoch<=0;
            partial_index<=0; partial_scale<=1;
            product_id<=0; product_seq<=0; product_epoch<=0; product_index<=0; product_scale<=1;
            active_id<=0; active_seq<=0; active_epoch<=0;
            result_first<=0; result_last<=0; spectrum_id<=0; result_epoch<=0;
            first_sample_seq<=0; bin_index<=0; bin_power<=0; scale_id<=1;
            completed_spectrum_count<=0; protocol_error_count<=0;
            dropped_spectrum_count<=0; blocked_cycle_count<=0;
        end else if(cancel) begin
            // A complete older spectrum's last can be held in output OR the
            // added partial stage, with a younger spectrum behind it. Cancel
            // discards both in either position; malformed prefixes were
            // already counted by the input validator, as in the baseline.
            if((held_valid && result_last && (partial_valid || products_valid)) ||
               (partial_valid && partial_last && products_valid))
                dropped_spectrum_count<=increment_two(dropped_spectrum_count);
            else if(active || held_valid || partial_valid || products_valid)
                dropped_spectrum_count<=increment(dropped_spectrum_count);
            held_valid<=0; products_valid<=0; partial_valid<=0; active<=0; discarding<=0; expected_index<=0;
        end else begin
            if(result_valid && !result_ready) blocked_cycle_count<=increment(blocked_cycle_count);
            if(result_valid && result_ready && result_last) completed_spectrum_count<=increment(completed_spectrum_count);
            if(output_space) begin
                held_valid<=partial_valid;
                if(partial_valid) begin
                    result_first<=partial_first; result_last<=partial_last;
                    spectrum_id<=partial_id; result_epoch<=partial_epoch;
                    first_sample_seq<=partial_seq; bin_index<=partial_index; scale_id<=partial_scale;
                    bin_power<={corrected_high,partial_low[17:0]};
                end
            end
            if(partial_space) begin
                partial_valid<=products_valid;
                if(products_valid) begin
                    // Deliberately separate the low18 add/carry and high18
                    // add into independent FFs. No full37bit MAC expression
                    // remains for DSP1.CASO -> DSP2.CASI matching.
                    partial_low<={1'b0,product_re[17:0]}+{1'b0,product_im[17:0]};
                    partial_high<={1'b0,product_re[35:18]}+{1'b0,product_im[35:18]};
                    partial_first<=product_first; partial_last<=product_last;
                    partial_id<=product_id; partial_seq<=product_seq;
                    partial_epoch<=product_epoch; partial_index<=product_index;
                    partial_scale<=product_scale;
                end
            end
            if(fft_ready) begin
                products_valid<=0;
                if(fft_valid) begin
                    if(accepted_fields) begin
                        products_valid<=1; product_re<=square_re; product_im<=square_im;
                        product_first<=fft_first; product_last<=fft_last;
                        product_id<=fft_spectrum_id; product_epoch<=fft_epoch;
                        product_seq<=product_seq_input; product_index<=fft_bin_index; product_scale<=fft_scale_id;
                        discarding<=0;
                        if(start_ok) begin
                            // A new legal first replaces one incomplete prefix.
                            if(active) begin
                                protocol_error_count<=increment(protocol_error_count);
                                dropped_spectrum_count<=increment(dropped_spectrum_count);
                            end
                            active<=1; expected_index<=1;
                            active_id<=fft_spectrum_id; active_epoch<=fft_epoch; active_seq<=fft_first_sample_seq;
                        end else if(fft_bin_index==1024) begin active<=0; expected_index<=0; end
                        else expected_index<=expected_index+1'b1;
                    end else begin
                        active<=0; expected_index<=0; discarding<=1;
                        if(!discarding) begin
                            protocol_error_count<=increment(protocol_error_count);
                            dropped_spectrum_count<=increment(dropped_spectrum_count);
                        end
                    end
                end
            end
        end
    end
endmodule
