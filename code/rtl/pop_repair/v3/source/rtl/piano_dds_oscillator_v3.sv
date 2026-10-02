// V3 isolated research candidate, NOT an accepted beat repair.
// Same 32-bit fundamental FCW, 48k sample enable, active-low async reset.
// <=220Hz: twelve harmonic partials, individual Q16 decay + smooth retrigger.
// >220Hz: untouched formal V1 oscillator (must compile baseline source too).
// One shared sine multiplier per lane, 12*3+1 clocks after sample_tick.
// No phase reset, randomness, detuning, global gain, public MIDI changes.
`timescale 1ns/1ps
module piano_dds_oscillator_v3 #(
    parameter ROM_FILE = "source/baseline/piano_band_4x256_8191.mem",
    parameter SINE_ROM_FILE = "source/rom/sine_v3_1024_32767.mem"
) (
    input logic sys_clk, sys_rst_n, sample_tick, note_on,
    input logic [9:0] velocity,
    input logic [31:0] fcw,
    output wire signed [15:0] wt_sample
);
    `include "v3_constants.svh"
    localparam logic [31:0] FCW_220_HZ = 32'd19685267;
    localparam logic [35:0] PARTIAL_LIMIT = 36'd1789569706; // floor(20000*2^32/48000)
    localparam logic [2:0] WAIT_TICK=0, FETCH=1, ROM_WAIT=2, ACCUMULATE=3, FINISH=4;
    logic [2:0] state;
    logic [3:0] partial_index;
    logic [31:0] phase_acc, render_phase, render_fcw;
    logic [31:0] target_q16 [0:11];
    logic [31:0] amplitude_q16 [0:11];
    logic signed [35:0] sum_product;
    logic signed [15:0] bass_sample, legacy_sample;
    logic signed [15:0] sine_rom [0:1023];
    logic signed [15:0] sine_sample;
    logic [9:0] sine_address;
    logic [31:0] harmonic_phase;
    logic [35:0] harmonic_fcw;
    logic [15:0] partial_amplitude;
    logic signed [32:0] product;
    logic signed [35:0] rounded_sum;
    integer i;

    function automatic [31:0] harmonic_phase_of(input [31:0] phase_value, input [3:0] index);
        // Explicit shift/add constants; no variable 32-bit phase multiplier.
        case(index)
            0: harmonic_phase_of=phase_value;
            1: harmonic_phase_of=phase_value<<1;
            2: harmonic_phase_of=(phase_value<<1)+phase_value;
            3: harmonic_phase_of=phase_value<<2;
            4: harmonic_phase_of=(phase_value<<2)+phase_value;
            5: harmonic_phase_of=(phase_value<<2)+(phase_value<<1);
            6: harmonic_phase_of=(phase_value<<3)-phase_value;
            7: harmonic_phase_of=phase_value<<3;
            8: harmonic_phase_of=(phase_value<<3)+phase_value;
            9: harmonic_phase_of=(phase_value<<3)+(phase_value<<1);
            10: harmonic_phase_of=(phase_value<<3)+(phase_value<<1)+phase_value;
            default: harmonic_phase_of=(phase_value<<3)+(phase_value<<2);
        endcase
    endfunction
    function automatic [35:0] harmonic_fcw_of(input [31:0] step_value, input [3:0] index);
        logic [35:0] wide;
        begin
            wide={4'b0,step_value};
            case(index)
                0: harmonic_fcw_of=wide;
                1: harmonic_fcw_of=wide<<1;
                2: harmonic_fcw_of=(wide<<1)+wide;
                3: harmonic_fcw_of=wide<<2;
                4: harmonic_fcw_of=(wide<<2)+wide;
                5: harmonic_fcw_of=(wide<<2)+(wide<<1);
                6: harmonic_fcw_of=(wide<<3)-wide;
                7: harmonic_fcw_of=wide<<3;
                8: harmonic_fcw_of=(wide<<3)+wide;
                9: harmonic_fcw_of=(wide<<3)+(wide<<1);
                10: harmonic_fcw_of=(wide<<3)+(wide<<1)+wide;
                default: harmonic_fcw_of=(wide<<3)+(wide<<2);
            endcase
        end
    endfunction
    function automatic [31:0] smoothed(input [31:0] current_value, target_value);
        if(target_value>=current_value)
            smoothed=current_value+((target_value-current_value+32'd63)>>6);
        else smoothed=current_value-((current_value-target_value+32'd63)>>6);
    endfunction
    function automatic [31:0] struck_target(input integer index, input [9:0] vel);
        logic [15:0] initial_value, floor_value;
        logic [17:0] extra;
        begin
            initial_value=BASS_INITIAL[16*index+:16];
            floor_value=BASS_FLOOR[16*index+:16];
            extra={2'b0,initial_value}-{2'b0,floor_value};
            if(vel<256) extra=extra>>1;
            else if(vel<768) extra=((extra<<1)+extra)>>2;
            struck_target=({16'b0,floor_value}+{14'b0,extra})<<16;
        end
    endfunction
    function automatic [31:0] decayed_target(input [31:0] current_value, input integer index);
        logic [31:0] floor_q16, gap, decrement;
        logic [4:0] shift_value;
        begin
            floor_q16={BASS_FLOOR[16*index+:16],16'b0};
            shift_value=PARTIAL_SHIFT[5*index+:5];
            gap=current_value>floor_q16 ? current_value-floor_q16 : 0;
            decrement=shift_value==0 ? 0 : (gap+((32'd1<<shift_value)-1))>>shift_value;
            decayed_target=current_value-decrement;
        end
    endfunction

    initial begin
        $readmemh(SINE_ROM_FILE,sine_rom);
        // synthesis translate_off
        for(integer word_index=0;word_index<1024;word_index=word_index+1)
            if(^sine_rom[word_index]===1'bx)
                $fatal(1,"V3 uninitialized sine word %0d",word_index);
        // synthesis translate_on
    end
    always_comb begin
        harmonic_phase=harmonic_phase_of(render_phase,partial_index);
        sine_address=harmonic_phase[31:22];
        harmonic_fcw=harmonic_fcw_of(render_fcw,partial_index);
        partial_amplitude=amplitude_q16[partial_index][31:16];
        // Q15 sine * positive amplitude; signed 17-bit operand prevents sign inversion.
        product=$signed(sine_sample)*$signed({1'b0,partial_amplitude});
        rounded_sum=(sum_product+36'sd16384)>>>15;
    end
    always_ff @(posedge sys_clk) sine_sample<=sine_rom[sine_address];
    always_ff @(posedge sys_clk or negedge sys_rst_n) begin
        if(!sys_rst_n) begin
            phase_acc<=0;render_phase<=0;render_fcw<=0;state<=WAIT_TICK;
            partial_index<=0;sum_product<=0;bass_sample<=0;
            for(i=0;i<12;i=i+1) begin
                target_q16[i]<={BASS_FLOOR[16*i+:16],16'b0};
                amplitude_q16[i]<={BASS_FLOOR[16*i+:16],16'b0};
            end
        end else begin
            if(note_on)
                for(i=0;i<12;i=i+1) target_q16[i]<=struck_target(i,velocity);
            if(sample_tick) begin
                phase_acc<=phase_acc+fcw;
                render_phase<=phase_acc+fcw;render_fcw<=fcw;
                sum_product<=0;partial_index<=0;state<=FETCH;
                for(i=0;i<12;i=i+1) begin
                    amplitude_q16[i]<=smoothed(amplitude_q16[i],target_q16[i]);
                    if(!note_on) target_q16[i]<=decayed_target(target_q16[i],i);
                end
            end else begin
                case(state)
                    FETCH: state<=ROM_WAIT;
                    ROM_WAIT: state<=ACCUMULATE;
                    ACCUMULATE: begin
                        if(harmonic_fcw<=PARTIAL_LIMIT)
                            sum_product<=sum_product+{{3{product[32]}},product};
                        if(partial_index==11) state<=FINISH;
                        else begin partial_index<=partial_index+1'b1;state<=FETCH;end
                    end
                    FINISH: begin
                        if(rounded_sum>8191) bass_sample<=16'sd8191;
                        else if(rounded_sum< -8192) bass_sample<= -16'sd8192;
                        else bass_sample<=rounded_sum[15:0];
                        state<=WAIT_TICK;
                    end
                    default: state<=WAIT_TICK;
                endcase
            end
            // synthesis translate_off
            if(sample_tick && state!=WAIT_TICK)
                $fatal(1,"V3 sample_tick too early: previous sample unfinished");
            // synthesis translate_on
        end
    end
    piano_dds_oscillator #(.ROM_FILE(ROM_FILE)) u_v1 (
        .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.sample_tick(sample_tick),
        .note_on(note_on),.velocity(velocity),.fcw(fcw),.wt_sample(legacy_sample)
    );
    assign wt_sample=(fcw<=FCW_220_HZ) ? bass_sample : legacy_sample;
endmodule
