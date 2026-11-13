// Stage-A private FFT, 40MHz audio_clk, synchronous active-low audio_rst_n.
// Input is a COMPLETE captured window streamed locally, NOT the unthrottled
// audio sample port. input_ready must never be fed back to the audio producer.
// Exactly2048 PCM24 samples, first/last on indices0/2047; metadata constant.
// cancel synchronously discards partial load/FFT/output, counters are retained.
// Periodic Hann Q1.17 -> bit-reversed write ->11-stage radix2 DIT -> natural
// bins0..1024. Complex sum-products round ONCE before each scaled butterfly.
// Product, complex-sum, butterfly-sum and round/clamp have register boundaries.
// 3 cycles/load,10/butterfly,2/output. Continuous local valid + ready output:
// <=3*2048+10*11264+2*1025+8=120842 clocks (3.02105ms at40MHz), excluding
// external input gaps/output stalls. No declaration of synthesis/STA success.
// Capture's read_data is already s18 Q1.17: wrapper must drive
// input_pcm={read_data,6'b0}, NOT sign-extend read_data directly. This exactly
// preserves the reduced value; original PCM clipping belongs to capture's
// counter, this module counts only its own declared reduction events.
module radix2_fft_2048 #(
    parameter HANN_FILE = "rom/k4_spectrum_hann_q17.mem",
    parameter TWIDDLE_RE_FILE = "rom/k4_spectrum_twiddle_re_q17.mem",
    parameter TWIDDLE_IM_FILE = "rom/k4_spectrum_twiddle_im_q17.mem"
) (
    input  wire audio_clk,
    input  wire audio_rst_n,
    input  wire cancel,
    input  wire input_valid,
    output wire input_ready,
    input  wire signed [23:0] input_pcm,
    input  wire input_first,
    input  wire input_last,
    input  wire [31:0] input_spectrum_id,
    input  wire [15:0] input_epoch,
    input  wire [31:0] input_first_sample_seq,
    output wire fft_valid,
    input  wire fft_ready,
    output wire fft_first,
    output wire fft_last,
    output wire [10:0] fft_bin_index,
    output wire signed [17:0] fft_real,
    output wire signed [17:0] fft_imag,
    output wire [31:0] fft_spectrum_id,
    output wire [15:0] fft_epoch,
    output wire [31:0] fft_first_sample_seq,
    output wire [7:0] fft_scale_id,
    output wire busy,
    output reg [31:0] accepted_window_count,
    output reg [31:0] emitted_spectrum_count,
    output reg [31:0] dropped_window_count,
    output reg [31:0] input_error_count,
    output reg [31:0] saturation_count,
    output reg saturation_sticky,
    output reg [31:0] blocked_cycle_count
);
    localparam [3:0] LOAD=0, WINDOW_MULT=1, WINDOW_WRITE=2, READ_A=3,
        READ_B=4, MULTIPLY=5, COMPLEX_SUM=6, ROTATE=7, BUTTERFLY_SUM=8,
        BUTTERFLY=9, WRITE_A=10, WRITE_B=11, OUTPUT_READ=12, OUTPUT_HOLD=13, COMPLEX_JOIN=14;
    reg [3:0] state;
    reg signed [17:0] hann [0:2047];
    reg signed [17:0] twiddle_re [0:1023];
    reg signed [17:0] twiddle_im [0:1023];
    reg signed [17:0] real_mem [0:2047];
    reg signed [17:0] imag_mem [0:2047];
    initial begin
        $readmemh(HANN_FILE, hann);
        $readmemh(TWIDDLE_RE_FILE, twiddle_re);
        $readmemh(TWIDDLE_IM_FILE, twiddle_im);
    end

    // Return {clipped,s18}. Signed arithmetic shift is floor division:
    // increment for positive remainder>=half, negative remainder>half.
    // This is ties-away without an abs/add/negate chain or MIN negation.
    function automatic [18:0] reduce_s18;
        input signed [39:0] value;
        input integer shift;
        reg signed [39:0] rounded;
        reg [39:0] remainder,half;
        reg round_up;
        begin
            remainder=$unsigned(value)&((40'd1<<shift)-1'b1);
            half=40'd1<<(shift-1);
            round_up=value[39] ? remainder>half : remainder>=half;
            rounded=(value>>>shift)+(round_up?40'sd1:40'sd0);
            if (rounded > 40'sd131071) reduce_s18 = {1'b1,18'h1ffff};
            else if (rounded < -40'sd131072) reduce_s18 = {1'b1,18'h20000};
            else reduce_s18 = {1'b0,rounded[17:0]};
        end
    endfunction
    function automatic [10:0] reverse11;
        input [10:0] value;
        integer i;
        begin for (i=0;i<11;i=i+1) reverse11[i]=value[10-i]; end
    endfunction
    function automatic [31:0] add_counter;
        input [31:0] value;
        input [3:0] increment;
        reg [32:0] total;
        begin total={1'b0,value}+{29'd0,increment}; add_counter=total[32]?32'hffffffff:total[31:0]; end
    endfunction

    reg [10:0] load_index, offset_index, output_index;
    reg [11:0] block_start;
    reg [3:0] stage_index;
    reg [9:0] twiddle_index;
    reg [9:0] twiddle_step;
    reg discarding;
    reg [31:0] frame_id, frame_first_seq;
    reg [15:0] frame_epoch;
    reg signed [17:0] pcm_reduced, window_coefficient;
    reg signed [35:0] window_product;
    reg signed [17:0] ar,ai,br,bi,wr,wi,tr,ti;
    reg signed [35:0] rr,ii,ri,ir;
    reg signed [17:0] new_ar,new_ai,new_br,new_bi;
    reg signed [17:0] output_real,output_imag;
    wire [11:0] half_size=12'd1 << stage_index;
    wire [11:0] span_size=half_size << 1;
    wire [11:0] address_a=block_start+{1'b0,offset_index};
    wire [11:0] address_b=address_a+half_size;
    // Registered twiddle address generation replaces a variable barrel shift.
    // At each stage the step halves; within a block the index advances by the
    // registered step and resets to zero at the next block.
    wire [9:0] twiddle_address=twiddle_index;
    // Native08 showed a direct output_index FF -> output-read RAM ADB hold
    // path. Protect the COMPLETE11bit output-read address class, shared by
    // both real/imag arrays (four native read-port lane consumers).
    // Consumer-only combinational identity; no read clock, state or cycle added.
    wire [10:0] output_read_index;
    spectrum_hold_input_luts #(.WIDTH(11)) u_output_read_address_hold(
        .data_in(output_index),.data_out(output_read_index));
    (* syn_keep=1,syn_preserve=1 *) reg signed [36:0] complex_real,complex_imag;
    (* syn_keep=1,syn_preserve=1 *) reg [18:0] complex_real_low,complex_real_high;
    (* syn_keep=1,syn_preserve=1 *) reg [18:0] complex_imag_low,complex_imag_high;
    wire [143:0] product_sum_input;
    spectrum_hold_input_luts #(.WIDTH(144)) u_product_sum_hold(
        .data_in({rr,ii,ri,ir}),.data_out(product_sum_input));
    wire [35:0] rr_sum=product_sum_input[143:108],ii_sum=product_sum_input[107:72];
    wire [35:0] ri_sum=product_sum_input[71:36],ir_sum=product_sum_input[35:0];
    wire [75:0] partial_join_input;
    spectrum_hold_input_luts #(.WIDTH(76)) u_partial_join_hold(
        .data_in({complex_real_low,complex_real_high,complex_imag_low,complex_imag_high}),
        .data_out(partial_join_input));
    wire [18:0] real_low_join=partial_join_input[75:57];
    wire [18:0] real_high_join=partial_join_input[56:38];
    wire [18:0] imag_low_join=partial_join_input[37:19];
    wire [18:0] imag_high_join=partial_join_input[18:0];
    wire [18:0] real_corrected_high=real_high_join+{18'd0,real_low_join[18]};
    wire [18:0] imag_corrected_high=imag_high_join+{18'd0,imag_low_join[18]};
    wire [73:0] rotation_input;
    spectrum_hold_input_luts #(.WIDTH(74)) u_rotation_hold(
        .data_in({complex_real,complex_imag}),.data_out(rotation_input));
    wire signed [36:0] complex_real_rotate=rotation_input[73:37];
    wire signed [36:0] complex_imag_rotate=rotation_input[36:0];
    reg signed [18:0] sum_ar,sum_ai,sum_br,sum_bi;
    wire [18:0] reduced_pcm=reduce_s18({{16{input_pcm[23]}},input_pcm},6);
    wire [18:0] reduced_window=reduce_s18({{4{window_product[35]}},window_product},17);
    wire [18:0] reduced_tr=reduce_s18({{3{complex_real_rotate[36]}},complex_real_rotate},17);
    wire [18:0] reduced_ti=reduce_s18({{3{complex_imag_rotate[36]}},complex_imag_rotate},17);
    wire [18:0] reduced_ar=reduce_s18({{21{sum_ar[18]}},sum_ar},1);
    wire [18:0] reduced_ai=reduce_s18({{21{sum_ai[18]}},sum_ai},1);
    wire [18:0] reduced_br=reduce_s18({{21{sum_br[18]}},sum_br},1);
    wire [18:0] reduced_bi=reduce_s18({{21{sum_bi[18]}},sum_bi},1);
    wire [3:0] rotation_clips={3'd0,reduced_tr[18]}+{3'd0,reduced_ti[18]};
    wire [3:0] butterfly_clips={3'd0,reduced_ar[18]}+{3'd0,reduced_ai[18]}+
                              {3'd0,reduced_br[18]}+{3'd0,reduced_bi[18]};
    wire metadata_matches=input_spectrum_id==frame_id && input_epoch==frame_epoch &&
                          input_first_sample_seq==frame_first_seq;
    assign input_ready=audio_rst_n && !cancel && state==LOAD;
    assign fft_valid=audio_rst_n && !cancel && state==OUTPUT_HOLD;
    assign fft_first=output_index==0;
    assign fft_last=output_index==1024;
    assign fft_bin_index=output_index;
    assign fft_real=output_real;
    assign fft_imag=output_imag;
    assign fft_spectrum_id=frame_id;
    assign fft_epoch=frame_epoch;
    assign fft_first_sample_seq=frame_first_seq;
    assign fft_scale_id=8'd1; // Model R01 scale ID1:11 divide-by2 stages,1/2048.
    assign busy=(state!=LOAD)||(load_index!=0);

    always @(posedge audio_clk) begin
        if (!audio_rst_n) begin
            state<=LOAD; load_index<=0; discarding<=0;
            block_start<=0; offset_index<=0; stage_index<=0; output_index<=0;
            twiddle_index<=0; twiddle_step<=10'd512;
            frame_id<=0; frame_epoch<=0; frame_first_seq<=0;
            output_real<=0; output_imag<=0;
            accepted_window_count<=0; emitted_spectrum_count<=0;
            dropped_window_count<=0; input_error_count<=0; saturation_count<=0;
            saturation_sticky<=0; blocked_cycle_count<=0;
        end else if (cancel) begin
            if (busy) dropped_window_count<=add_counter(dropped_window_count,1);
            state<=LOAD; load_index<=0; discarding<=0;
            block_start<=0; offset_index<=0; stage_index<=0; output_index<=0;
            twiddle_index<=0; twiddle_step<=10'd512;
        end else begin
            if (fft_valid && !fft_ready) blocked_cycle_count<=add_counter(blocked_cycle_count,1);
            case (state)
                LOAD: if (input_valid) begin
                    if (input_first && !input_last) begin
                        if (load_index!=0) begin
                            dropped_window_count<=add_counter(dropped_window_count,1);
                            input_error_count<=add_counter(input_error_count,1);
                        end
                        load_index<=0; discarding<=0;
                        frame_id<=input_spectrum_id; frame_epoch<=input_epoch;
                        frame_first_seq<=input_first_sample_seq;
                        pcm_reduced<=reduced_pcm[17:0]; window_coefficient<=hann[0];
                        saturation_count<=add_counter(saturation_count,{3'd0,reduced_pcm[18]});
                        if(reduced_pcm[18]) saturation_sticky<=1;
                        state<=WINDOW_MULT;
                    end else if (!discarding && load_index!=0 && !input_first &&
                                 input_last==(load_index==2047) && metadata_matches) begin
                        pcm_reduced<=reduced_pcm[17:0]; window_coefficient<=hann[load_index];
                        saturation_count<=add_counter(saturation_count,{3'd0,reduced_pcm[18]});
                        if(reduced_pcm[18]) saturation_sticky<=1;
                        state<=WINDOW_MULT;
                    end else begin
                        if (!discarding) begin
                            input_error_count<=add_counter(input_error_count,1);
                            dropped_window_count<=add_counter(dropped_window_count,1);
                        end
                        load_index<=0; discarding<=1;
                    end
                end
                WINDOW_MULT: begin
                    window_product<=$signed(pcm_reduced)*$signed(window_coefficient);
                    state<=WINDOW_WRITE;
                end
                WINDOW_WRITE: begin
                    real_mem[reverse11(load_index)]<=reduced_window[17:0];
                    imag_mem[reverse11(load_index)]<=0;
                    saturation_count<=add_counter(saturation_count,{3'd0,reduced_window[18]});
                    if(reduced_window[18]) saturation_sticky<=1;
                    if(load_index==2047) begin
                        accepted_window_count<=add_counter(accepted_window_count,1);
                        stage_index<=0; block_start<=0; offset_index<=0;
                        twiddle_index<=0; twiddle_step<=10'd512; state<=READ_A;
                    end else begin load_index<=load_index+1'b1; state<=LOAD; end
                end
                READ_A: begin ar<=real_mem[address_a[10:0]]; ai<=imag_mem[address_a[10:0]]; state<=READ_B; end
                READ_B: begin
                    br<=real_mem[address_b[10:0]]; bi<=imag_mem[address_b[10:0]];
                    wr<=twiddle_re[twiddle_address]; wi<=twiddle_im[twiddle_address]; state<=MULTIPLY;
                end
                MULTIPLY: begin
                    rr<=$signed(br)*$signed(wr); ii<=$signed(bi)*$signed(wi);
                    ri<=$signed(br)*$signed(wi); ir<=$signed(bi)*$signed(wr); state<=COMPLEX_SUM;
                end
                COMPLEX_SUM: begin
                    // Exact signed37 subtraction via two's complement:
                    // low18 adds the complement and carry-in1; high19 adds
                    // sign-extended upper halves and receives low carry later.
                    complex_real_low<={1'b0,rr_sum[17:0]}+{1'b0,~ii_sum[17:0]}+19'd1;
                    complex_real_high<={rr_sum[35],rr_sum[35:18]}+{~ii_sum[35],~ii_sum[35:18]};
                    complex_imag_low<={1'b0,ri_sum[17:0]}+{1'b0,ir_sum[17:0]};
                    complex_imag_high<={ri_sum[35],ri_sum[35:18]}+{ir_sum[35],ir_sum[35:18]};
                    state<=COMPLEX_JOIN;
                end
                COMPLEX_JOIN: begin
                    // modulo19 upper carry is the exact signed37 result.
                    // No component is rounded until the unchanged ROTATE step.
                    complex_real<={real_corrected_high,real_low_join[17:0]};
                    complex_imag<={imag_corrected_high,imag_low_join[17:0]};
                    state<=ROTATE;
                end
                ROTATE: begin
                    tr<=reduced_tr[17:0]; ti<=reduced_ti[17:0];
                    saturation_count<=add_counter(saturation_count,rotation_clips);
                    if(rotation_clips!=0) saturation_sticky<=1;
                    state<=BUTTERFLY_SUM;
                end
                BUTTERFLY_SUM: begin
                    sum_ar<={ar[17],ar}+{tr[17],tr}; sum_ai<={ai[17],ai}+{ti[17],ti};
                    sum_br<={ar[17],ar}-{tr[17],tr}; sum_bi<={ai[17],ai}-{ti[17],ti};
                    state<=BUTTERFLY;
                end
                BUTTERFLY: begin
                    new_ar<=reduced_ar[17:0]; new_ai<=reduced_ai[17:0];
                    new_br<=reduced_br[17:0]; new_bi<=reduced_bi[17:0];
                    saturation_count<=add_counter(saturation_count,butterfly_clips);
                    if(butterfly_clips!=0) saturation_sticky<=1;
                    state<=WRITE_A;
                end
                WRITE_A: begin real_mem[address_a[10:0]]<=new_ar; imag_mem[address_a[10:0]]<=new_ai; state<=WRITE_B; end
                WRITE_B: begin
                    real_mem[address_b[10:0]]<=new_br; imag_mem[address_b[10:0]]<=new_bi;
                    state<=READ_A;
                    if ({1'b0,offset_index}+1 < half_size) begin
                        offset_index<=offset_index+1'b1;
                        twiddle_index<=twiddle_index+twiddle_step;
                    end
                    else begin
                        offset_index<=0; twiddle_index<=0;
                        if(block_start+span_size<2048) block_start<=block_start+span_size;
                        else begin
                            block_start<=0;
                            if(stage_index==10) begin output_index<=0; state<=OUTPUT_READ; end
                            else begin
                                stage_index<=stage_index+1'b1;
                                // Stage 0 has only offset zero, so the stored
                                // step already represents stage 1 (512).  From
                                // stage 1 onward it halves once per stage.
                                if (stage_index != 0)
                                    twiddle_step<=twiddle_step>>1;
                            end
                        end
                    end
                end
                OUTPUT_READ: begin
                    output_real<=real_mem[output_read_index]; output_imag<=imag_mem[output_read_index]; state<=OUTPUT_HOLD;
                end
                OUTPUT_HOLD: if(fft_ready) begin
                    if(output_index==1024) begin
                        emitted_spectrum_count<=add_counter(emitted_spectrum_count,1);
                        load_index<=0; state<=LOAD;
                    end else begin output_index<=output_index+1'b1; state<=OUTPUT_READ; end
                end
                default: begin state<=LOAD; load_index<=0; discarding<=0; end
            endcase
        end
    end
endmodule

// Consumer-only transparent hold cells, matching the project's native LUT1
// convention. WIDTH bits have equal two-cell depth; no clock/CE/FF/reset change.
// GW5A LUT1 primary model is used in tests, never a simulation bypass.
module spectrum_hold_input_luts #(parameter integer WIDTH=1) (
    input wire [WIDTH-1:0] data_in,
    output wire [WIDTH-1:0] data_out
);
    for(genvar bit_index=0;bit_index<WIDTH;bit_index=bit_index+1)begin:g_bit
        (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=data_in[bit_index];
        for(genvar stage=0;stage<2;stage=stage+1)begin:g_delay
            (* syn_keep=1,syn_preserve=1,syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                .I0(chain[stage]),.F(chain[stage+1]));
        end
        assign data_out[bit_index]=chain[2];
    end
endmodule
