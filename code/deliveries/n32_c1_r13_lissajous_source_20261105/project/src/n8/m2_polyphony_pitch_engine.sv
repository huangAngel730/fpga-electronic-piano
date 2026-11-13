// Shared one-lane pitch/LFO pipeline for N=4/8/16/32 voices.
//
// The former backend instantiated one complete seven-stage pitch pipeline and
// three ROMs per voice.  This engine keeps independent LFO phase state for
// every voice, but launches one occupied voice per clock through one shared
// arithmetic/ROM pipeline.  A 32-voice request therefore needs at most 39
// clocks, well below the 833-clock 48 kHz frame budget at 40 MHz.
//
// start captures a complete control snapshot. done pulses only after every
// launched result has been written. Unoccupied lanes return their base FCW and
// do not advance LFO state. note_on resets the corresponding independent LFO.
`timescale 1ns/1ps
module m2_polyphony_pitch_engine #(
    parameter integer N=32,
    parameter integer SW=$clog2(N),
    parameter OCT_FILE="rom/oct_ratio_q16.mem",
    parameter SUB_FILE="rom/sub_ratio_q16.mem",
    parameter LFO_FILE="rom/lfo_sine_q15.mem",
    parameter logic [31:0] LFO_INC=32'd447392,
    parameter logic [31:0] FCW_MAX=32'h80000000,
    parameter logic [9:0] MOD_DEPTH_MAX_Q10=10'd512
) (
    input  wire clk,
    input  wire rst_n,
    input  wire start,
    output wire start_ready,
    output logic busy,
    output logic done,
    input  wire [N-1:0] note_on,
    input  wire [N-1:0] occupied,
    input  wire [N*32-1:0] base_fcw,
    input  wire [N*12-1:0] bend,
    input  wire [N*12-1:0] modulation,
    input  wire [N*5-1:0] pitch_range,
    output wire [N*32-1:0] fcw_values
);
    logic [19:0] oct_lut [0:49];
    logic [19:0] sub_lut [0:1023];
    logic [19:0] sub_source [0:1023];
    logic signed [15:0] lfo_lut [0:1023];

    function automatic logic [9:0] encode_fraction(input logic [9:0] value);
        encode_fraction=value ^ {value[8:0],value[9]} ^
            {value[6:0],value[9:7]};
    endfunction

    // synthesis translate_off
    string oct_path,sub_path,lfo_path;
    integer rom_check;
    // synthesis translate_on
    initial begin
        $readmemh(OCT_FILE,oct_lut);
        $readmemh(SUB_FILE,sub_source);
        $readmemh(LFO_FILE,lfo_lut);
        // synthesis translate_off
        if($value$plusargs("OCT_PATH=%s",oct_path)) begin
            rom_check=$fopen(oct_path,"r");
            if(!rom_check) $fatal(1,"missing requested OCT_PATH");
            $fclose(rom_check); $readmemh(oct_path,oct_lut);
        end
        if($value$plusargs("SUB_PATH=%s",sub_path)) begin
            rom_check=$fopen(sub_path,"r");
            if(!rom_check) $fatal(1,"missing requested SUB_PATH");
            $fclose(rom_check); $readmemh(sub_path,sub_source);
        end
        if($value$plusargs("LFO_PATH=%s",lfo_path)) begin
            rom_check=$fopen(lfo_path,"r");
            if(!rom_check) $fatal(1,"missing requested LFO_PATH");
            $fclose(rom_check); $readmemh(lfo_path,lfo_lut);
        end
        // synthesis translate_on
        for(integer address=0;address<1024;address=address+1)
            sub_lut[encode_fraction(10'(address))]=sub_source[address];
        // synthesis translate_off
        for(integer i=0;i<50;i++)
            if(^oct_lut[i]===1'bx) $fatal(1,"shared pitch missing oct[%0d]",i);
        for(integer i=0;i<1024;i++)
            if(^sub_lut[i]===1'bx || ^lfo_lut[i]===1'bx)
                $fatal(1,"shared pitch missing sub/LFO[%0d]",i);
        // synthesis translate_on
    end

    logic [N-1:0] occupied_q;
    logic signed [11:0] bend_q [0:N-1];
    logic [11:0] modulation_q [0:N-1];
    logic [4:0] pitch_range_q [0:N-1];
    logic [31:0] base_q [0:N-1];
    logic [31:0] result_q [0:N-1];
    logic [31:0] lfo_phase [0:N-1];

    for(genvar out_i=0;out_i<N;out_i=out_i+1) begin:g_result_flatten
        assign fcw_values[32*out_i+:32]=result_q[out_i];
    end

    logic [SW-1:0] launch_slot;
    logic launch_done;
    wire launch_valid=busy && !launch_done && occupied_q[launch_slot];
    wire [31:0] launch_phase=note_on[launch_slot] ? 32'd0 :
        lfo_phase[launch_slot];
    wire signed [16:0] bend_product=
        $signed(bend_q[launch_slot]) *
        $signed({1'b0,pitch_range_q[launch_slot]});
    wire [21:0] mod_product=modulation_q[launch_slot] *
        {12'd0,MOD_DEPTH_MAX_Q10};
    wire [21:0] rounded_depth=mod_product+22'd2048;

    // Keep the accepted identity-delay style once on the shared datapath.
    (* syn_keep=1, syn_dont_touch=1 *) wire signed [16:0] bend_product_hold;
    for(genvar bend_bit=0;bend_bit<17;bend_bit=bend_bit+1) begin:g_bend_hold
        (* syn_keep=1, syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=bend_product[bend_bit];
        for(genvar hs=0;hs<2;hs=hs+1) begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                .I0(chain[hs]),.F(chain[hs+1]));
        end
        assign bend_product_hold[bend_bit]=chain[2];
    end

    logic signed [15:0] sine_s0;
    logic [9:0] depth_s0;
    logic signed [16:0] semi_s0,semi_s1;
    logic signed [25:0] sine_product_s1;
    logic signed [17:0] total_s2;
    logic [19:0] oct_s3,sub_s3;
    logic [39:0] ratio_s4;
    logic [56:0] fcw_product_s5;
    logic [31:0] base_s0,base_s1,base_s2,base_s3,base_s4;
    logic [5:0] valid_pipe;
    logic [SW-1:0] slot_pipe [0:5];

    wire [5:0] stage_enable;
    for(genvar ve_bit=0;ve_bit<6;ve_bit=ve_bit+1) begin:g_valid_hold
        (* syn_keep=1, syn_dont_touch=1 *) wire [2:0] chain;
        assign chain[0]=valid_pipe[ve_bit];
        for(genvar vs=0;vs<2;vs=vs+1) begin:g_stage
            (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_identity(
                .I0(chain[vs]),.F(chain[vs+1]));
        end
        assign stage_enable[ve_bit]=chain[2];
    end

    wire signed [16:0] vib_s1=sine_product_s1>>>15;
    wire signed [17:0] total_sum_s1=$signed(semi_s1)+$signed(vib_s1);
    (* syn_keep=1, syn_dont_touch=1 *) wire total_bit10_l0,total_bit10_l1;
    (* syn_keep=1, syn_dont_touch=1 *) wire total_bit12_l0,total_bit12_l1;
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_total10_hold_0(
        .I0(total_sum_s1[10]),.F(total_bit10_l0));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_total10_hold_1(
        .I0(total_bit10_l0),.F(total_bit10_l1));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_total12_hold_0(
        .I0(total_sum_s1[12]),.F(total_bit12_l0));
    (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_total12_hold_1(
        .I0(total_bit12_l0),.F(total_bit12_l1));
    wire signed [17:0] total_capture_s1={total_sum_s1[17:13],
        total_bit12_l1,total_sum_s1[11],total_bit10_l1,total_sum_s1[9:0]};
    wire signed [17:0] q_s2=total_s2>>>10;
    wire [5:0] oct_index=(q_s2>18'sd24) ? 6'd49 :
        (q_s2< -18'sd25) ? 6'd0 : q_s2[5:0]+6'd25;
    wire [9:0] sub_index=total_s2[9:0];
    wire [24:0] factor_s4={1'b0,ratio_s4[39:16]};
    wire [56:0] round_fc_product=fcw_product_s5+57'd32768;
    wire [32:0] raw_fcw=round_fc_product>>16;
    wire [31:0] limited_fcw=raw_fcw>FCW_MAX ? FCW_MAX : raw_fcw[31:0];
    (* syn_keep=1, syn_dont_touch=1 *) wire [31:0] held_fcw_data;
    for(genvar fcw_bit=0;fcw_bit<32;fcw_bit=fcw_bit+1) begin:g_fcw_hold
        LUT1 #(.INIT(2'h2)) u_identity(
            .I0(limited_fcw[fcw_bit]),.F(held_fcw_data[fcw_bit]));
    end

    assign start_ready=!busy;

    // ROM outputs are registered so the three tables remain shared memories.
    always_ff @(posedge clk) begin
        if(launch_valid) sine_s0<=lfo_lut[launch_phase[31:22]];
        if(stage_enable[2]) begin
            oct_s3<=oct_lut[oct_index];
            sub_s3<=sub_lut[encode_fraction(sub_index)];
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            busy<=1'b0; done<=1'b0; launch_slot<='0; launch_done<=1'b0;
            valid_pipe<='0;
            depth_s0<='0; semi_s0<='0; semi_s1<='0;
            sine_product_s1<='0; total_s2<='0; ratio_s4<='0;
            fcw_product_s5<='0;
            base_s0<='0; base_s1<='0; base_s2<='0; base_s3<='0; base_s4<='0;
            for(integer i=0;i<N;i=i+1) begin
                occupied_q[i]<=1'b0; bend_q[i]<='0; modulation_q[i]<='0;
                pitch_range_q[i]<='0; base_q[i]<='0; result_q[i]<='0;
                lfo_phase[i]<='0;
            end
            for(integer p=0;p<6;p=p+1) slot_pipe[p]<='0;
        end else begin
            done<=1'b0;

            // Note events remain independent of frame requests.
            for(integer i=0;i<N;i=i+1)
                if(note_on[i]) lfo_phase[i]<=32'd0;

            if(start && start_ready) begin
                busy<=1'b1;
                launch_slot<='0;
                launch_done<=1'b0;
                valid_pipe<='0;
                for(integer i=0;i<N;i=i+1) begin
                    occupied_q[i]<=occupied[i];
                    bend_q[i]<=bend[12*i+:12];
                    modulation_q[i]<=modulation[12*i+:12];
                    pitch_range_q[i]<=pitch_range[5*i+:5];
                    base_q[i]<=base_fcw[32*i+:32];
                    result_q[i]<=base_fcw[32*i+:32];
                end
            end else begin
                valid_pipe<={valid_pipe[4:0],launch_valid};
                slot_pipe[0]<=launch_slot;
                for(integer p=1;p<6;p=p+1) slot_pipe[p]<=slot_pipe[p-1];

                if(launch_valid) begin
                    depth_s0<=rounded_depth>>12;
                    semi_s0<=bend_product_hold>>>1;
                    base_s0<=base_q[launch_slot];
                    if(note_on[launch_slot]) lfo_phase[launch_slot]<=LFO_INC;
                    else lfo_phase[launch_slot]<=lfo_phase[launch_slot]+LFO_INC;
                end
                if(stage_enable[0]) begin
                    sine_product_s1<=sine_s0*$signed({1'b0,depth_s0});
                    semi_s1<=semi_s0; base_s1<=base_s0;
                end
                if(stage_enable[1]) begin
                    total_s2<=total_capture_s1; base_s2<=base_s1;
                end
                if(stage_enable[2]) base_s3<=base_s2;
                if(stage_enable[3]) begin
                    ratio_s4<=oct_s3*sub_s3; base_s4<=base_s3;
                end
                if(stage_enable[4]) fcw_product_s5<=base_s4*factor_s4;
                if(stage_enable[5]) result_q[slot_pipe[5]]<=held_fcw_data;

                if(busy && !launch_done) begin
                    if(launch_slot==N-1) launch_done<=1'b1;
                    else launch_slot<=launch_slot+1'b1;
                end
                if(busy && launch_done && valid_pipe==0) begin
                    busy<=1'b0;
                    done<=1'b1;
                end
            end
        end
    end

    // synthesis translate_off
    initial begin
        if(!(N==4 || N==8 || N==16 || N==32))
            $fatal(1,"SHARED_PITCH_N_NOT_SUPPORTED");
        if(SW!=$clog2(N)) $fatal(1,"SHARED_PITCH_SW");
    end
    always @(posedge clk) if(rst_n && launch_valid &&
        pitch_range_q[launch_slot]>24)
        $fatal(1,"pitch_range outside accepted0..24 contract");
    // synthesis translate_on
endmodule
