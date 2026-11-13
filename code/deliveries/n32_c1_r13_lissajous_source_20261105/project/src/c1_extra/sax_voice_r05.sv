// Independent R05 draft; immutable R04 sources and production remain untouched.
// SAX_R05_LOCAL_CONTRACT_V1: E0 request, E9 leaf result, E11 quad result.
// Accepted tick spacing>=12 leaf, >=14 quad; no overlapped transactions.
// Three regions x4 temporal snapshots x8 banks x256 phase samples, per dynamic.
// Two signed16 ROMs:96KiB/leaf,384KiB/four lanes logical, mapping UNKNOWN.
// gain UQ1.16, expanded velocity10, time/velocity weights unsigned9 in0..256.
// Active/busy omit final output-valid retirement; consume a valid zero tail.
module sax_voice_r05 #(
    parameter SOFT_ROM_FILE="rom/sax_soft.hex",
    parameter HARD_ROM_FILE="rom/sax_hard.hex",
    parameter NOISE_ROM_FILE="rom/noise_levels.hex",
    parameter [22:0] NOISE_SEED=23'd5902900, // domain: nonzero
    parameter integer ATTACK_SAMPLES=720,
    parameter integer RELEASE_SAMPLES=3840,
    parameter integer RETRIGGER_SAMPLES=240
)(
    input wire clk, input wire rst_n, input wire sample_tick,
    input wire note_on, input wire note_off, input wire kill,
    input wire [6:0] velocity, input wire [31:0] fcw,
    output reg signed [23:0] pcm, output reg pcm_valid,
    output wire busy, output wire active,
    output reg protocol_error, output reg invalid_pitch
);
    // Envelope sample parameters retain R02's supported integer1..65536 domain.
    localparam integer ATTACK_STEP=(65536+ATTACK_SAMPLES-1)/ATTACK_SAMPLES;
    localparam integer RELEASE_STEP=(65536+RELEASE_SAMPLES-1)/RELEASE_SAMPLES;
    localparam integer FADE_STEP=(65536+RETRIGGER_SAMPLES-1)/RETRIGGER_SAMPLES;
    localparam [2:0] OFF=0, ATTACK=1, HOLD=2, RELEASE=3, FADE=4;
    reg signed [15:0] soft_rom_lo [0:16383] /* synthesis syn_romstyle = "block_rom" */;
    reg signed [15:0] soft_rom_hi [0:8191] /* synthesis syn_romstyle = "block_rom" */;
    localparam SOFT_ROM_LO = {SOFT_ROM_FILE,".lo"};
    localparam SOFT_ROM_HI = {SOFT_ROM_FILE,".hi"};
    reg signed [15:0] hard_rom_lo [0:16383] /* synthesis syn_romstyle = "block_rom" */;
    reg signed [15:0] hard_rom_hi [0:8191] /* synthesis syn_romstyle = "block_rom" */;
    localparam HARD_ROM_LO = {HARD_ROM_FILE,".lo"};
    localparam HARD_ROM_HI = {HARD_ROM_FILE,".hi"};
    reg [7:0] noise_levels [0:5]; // soft regions0..2, then hard0..2; legal0..32
    initial begin
        $readmemh(SOFT_ROM_LO,soft_rom_lo);
        $readmemh(SOFT_ROM_HI,soft_rom_hi);
        $readmemh(HARD_ROM_LO,hard_rom_lo);
        $readmemh(HARD_ROM_HI,hard_rom_hi);
        $readmemh(NOISE_ROM_FILE,noise_levels);
    end
    reg [2:0] mode;
    reg [16:0] gain;
    reg [31:0] phase, active_fcw, pending_fcw;
    reg [9:0] active_velocity,pending_velocity;
    reg pending;
    reg [13:0] note_age;
    reg [15:0] sustain_phase;
    reg [3:0] stage;
    reg [14:0] addr_a0,addr_a1,addr_b0,addr_b1;
    reg [2:0] rom_step;
    reg [14:0] rom_addr;
    reg signed [15:0] soft_lo,soft_hi,hard_lo,hard_hi;
    reg rom_upper_q;
    wire signed [15:0] soft_read=rom_upper_q ? soft_hi : soft_lo;
    wire signed [15:0] hard_read=rom_upper_q ? hard_hi : hard_lo;
    always_comb begin
        case(rom_step)
            0: rom_addr=addr_a0;
            1: rom_addr=addr_a1;
            2: rom_addr=addr_b0;
            default: rom_addr=addr_b1;
        endcase
    end
    // Use exact power-of-two banks for the 24K-word layer.
    // Bit 14 selects the 8K tail; only one bank per layer reads each cycle.
    always @(posedge clk) if(stage==1 && rom_step<4) begin
        rom_upper_q<=rom_addr[14];
        if(rom_addr[14]) begin
            soft_hi<=soft_rom_hi[rom_addr[12:0]];
            hard_hi<=hard_rom_hi[rom_addr[12:0]];
        end else begin
            soft_lo<=soft_rom_lo[rom_addr[13:0]];
            hard_lo<=hard_rom_lo[rom_addr[13:0]];
        end
    end
    reg [15:0] fraction;
    reg [16:0] gain_snapshot;
    reg [9:0] velocity_snapshot;
    reg [8:0] mix_snapshot,time_snapshot;
    reg [26:0] joint_gain;
    // Lanes:0 soft/timeA,1 soft/timeB,2 hard/timeA,3 hard/timeB.
    reg signed [15:0] sample0[0:3],sample1[0:3],phase_base[0:3];
    reg signed [16:0] phase_difference[0:3];
    reg signed [33:0] phase_product[0:3];
    reg signed [17:0] phase_interp[0:3];
    wire signed [18:0] time_difference[0:1];
    assign time_difference[0]=$signed({phase_interp[1][17],phase_interp[1]})-
                               $signed({phase_interp[0][17],phase_interp[0]});
    assign time_difference[1]=$signed({phase_interp[3][17],phase_interp[3]})-
                               $signed({phase_interp[2][17],phase_interp[2]});
    reg signed [28:0] time_product[0:1];
    reg signed [17:0] time_base[0:1],time_interp[0:1];
    wire signed [28:0] time_wide[0:1];
    assign time_wide[0]=$signed({{11{time_base[0][17]}},time_base[0]})+(time_product[0]>>>8);
    assign time_wide[1]=$signed({{11{time_base[1][17]}},time_base[1]})+(time_product[1]>>>8);
    wire signed [18:0] morph_difference=$signed({time_interp[1][17],time_interp[1]})-
                                         $signed({time_interp[0][17],time_interp[0]});
    reg signed [17:0] morph_base;
    reg signed [28:0] morph_product;
    wire signed [28:0] blend_wide=
        $signed({{11{morph_base[17]}},morph_base})+(morph_product>>>8);
    // All convex lerps stay within +/-24500. Breath adds at most512;
    // signed18 narrowing below removes sign extension only (abs<=25012).
    wire signed [17:0] blend=blend_wide[17:0];
    reg signed [46:0] velocity_product;
    wire signed [47:0] extended_product={velocity_product[46],velocity_product};
    // Divide by2^18: gain16 fractional + expanded velocity /1024 + PCM24 scale.
    // Symmetric ties away from zero, followed by saturation, as in R02.
    wire signed [47:0] rounded_product=extended_product>=0 ?
        ((extended_product+48'sd131072)>>>18) :
        -(((-extended_product)+48'sd131072)>>>18);
    wire valid_input_pitch=(fcw!=0 && fcw<=32'h40000000);
    wire release_event=note_off || (note_on && velocity==0);
    // Persistent velocity layer ratio: no R04 artificial attack-bias term.
    wire [6:0] note_velocity=active_velocity[9:3];
    wire [8:0] mix9=(note_velocity<=7'd40) ? 9'd0 :
        (note_velocity>=7'd104) ? 9'd256 : (({2'b00,note_velocity}-9'd40)<<2);
    wire [1:0] time_a=(note_age<14'd4096) ? 2'd0 :
        (note_age<14'd8192) ? 2'd1 : 2'd2;
    wire [1:0] time_b=time_a+2'd1;
    wire [8:0] sustain_mix=sustain_phase[15] ?
        (9'd256-{1'b0,sustain_phase[14:7]}) : {1'b0,sustain_phase[14:7]};
    // In both initial intervals bits11:4 equal the interval-relative age>>4.
    wire [8:0] time_mix=(note_age<14'd8192) ? {1'b0,note_age[11:4]} : sustain_mix;
    wire [1:0] region=(active_fcw<=32'd16553270) ? 2'd0 :
        (active_fcw<=32'd33106541) ? 2'd1 : 2'd2;
    // Persistent synthetic band-limited breath; never restarted at NoteOn.
    // Q8 states use OLD fast in both parallel updates (not fast_next).
    reg [22:0] noise_lfsr;
    reg signed [25:0] fast_q8,slow_q8;
    wire signed [15:0] white=$signed(noise_lfsr[22:7]);
    wire signed [25:0] white_q8=$signed({{2{white[15]}},white,8'b0});
    wire signed [25:0] fast_delta=white_q8-fast_q8;
    wire signed [25:0] slow_delta=fast_q8-slow_q8;
    wire signed [25:0] fast_next=fast_q8+(fast_delta>>>1);
    wire signed [25:0] slow_next=slow_q8+(slow_delta>>>4);
    wire signed [25:0] old_band_q8=fast_q8-slow_q8;
    wire signed [18:0] old_band=old_band_q8>>>8;
    wire [7:0] soft_level=noise_levels[region];
    wire [7:0] hard_level=noise_levels[{1'b0,region}+3'd3];
    wire signed [8:0] level_delta=$signed({1'b0,hard_level})-$signed({1'b0,soft_level});
    wire signed [18:0] level_product=level_delta*$signed({1'b0,mix9});
    wire signed [18:0] level_interp=$signed({11'b0,soft_level})+(level_product>>>8);
    // Legal table levels0..32 and convex interpolation fit unsigned6 exactly.
    wire [5:0] noise_level=level_interp[5:0];
    reg signed [18:0] band_snapshot;
    reg [5:0] noise_level_snapshot;
    reg signed [25:0] noise_product;
    wire signed [26:0] noise_extended={noise_product[25],noise_product};
    // Integer ties-away rounding is floor((n+2048)/4096) for n>=0,
    // floor((n+2047)/4096) for n<0. One adder, no abs/negation carry chain.
    wire signed [26:0] noise_round_bias=noise_extended>=0 ? 27'sd2048 : 27'sd2047;
    wire signed [26:0] rounded_noise=(noise_extended+noise_round_bias)>>>12;
    reg signed [18:0] noise_word;
    // Abs noise<=512; ROM<=24500 => abs blend<=25012. No intermediate clipping.
    wire signed [27:0] noisy_soft_wide=
        $signed({{10{time_interp[0][17]}},time_interp[0]})+
        $signed({{9{noise_word[18]}},noise_word});
    assign busy=(stage!=0);
    assign active=(gain!=0 || pending || mode!=OFF);
    function [2:0] choose_bank(input [31:0] step);
        begin
            if      (step<=32'd16647160) choose_bank=0;
            else if (step<=32'd33038209) choose_bank=1;
            else if (step<=32'd65075262) choose_bank=2;
            else if (step<=32'd126322567) choose_bank=3;
            else if (step<=32'd238609294) choose_bank=4;
            else if (step<=32'd429496729) choose_bank=5;
            else if (step<=32'd715827882) choose_bank=6;
            else choose_bank=7;
        end
    endfunction
    wire [2:0] bank=choose_bank(active_fcw);
    wire [7:0] phase_index=phase[31:24];
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pcm<=0;pcm_valid<=0;protocol_error<=0;invalid_pitch<=0;
            mode<=OFF;gain<=0;phase<=0;active_fcw<=0;pending_fcw<=0;
            active_velocity<=0;pending_velocity<=0;pending<=0;stage<=0;note_age<=0;
            sustain_phase<=0;rom_step<=0;
            addr_a0<=0;addr_a1<=0;addr_b0<=0;addr_b1<=0;
            fraction<=0;gain_snapshot<=0;velocity_snapshot<=0;
            mix_snapshot<=0;time_snapshot<=0;joint_gain<=0;
            for(i=0;i<4;i=i+1) begin
                sample0[i]<=0;sample1[i]<=0;phase_base[i]<=0;
                phase_difference[i]<=0;phase_product[i]<=0;phase_interp[i]<=0;
            end
            for(i=0;i<2;i=i+1) begin
                time_base[i]<=0;time_product[i]<=0;time_interp[i]<=0;
            end
            morph_base<=0;morph_product<=0;
            velocity_product<=0;
            noise_lfsr<=NOISE_SEED;fast_q8<=0;slow_q8<=0;
            band_snapshot<=0;noise_level_snapshot<=0;noise_product<=0;noise_word<=0;
        end else begin
            pcm_valid<=0;
            if (sample_tick && busy) protocol_error<=1;
            case(stage)
                0: if(sample_tick) begin
                    // All snapshots read OLD state, including an OFF install tick.
                    addr_a0<={region,time_a,bank,phase_index};
                    addr_a1<={region,time_a,bank,(phase_index+8'd1)};
                    addr_b0<={region,time_b,bank,phase_index};
                    addr_b1<={region,time_b,bank,(phase_index+8'd1)};
                    fraction<=phase[23:8];gain_snapshot<=gain;
                    velocity_snapshot<=active_velocity;mix_snapshot<=mix9;
                    time_snapshot<=time_mix;rom_step<=0;stage<=1;
                    band_snapshot<=old_band;noise_level_snapshot<=noise_level;
                    phase<=phase+active_fcw;
                end
                1: begin
                    case(rom_step)
                        0: begin
                            joint_gain<=gain_snapshot*velocity_snapshot;
                            noise_product<=band_snapshot*$signed({1'b0,noise_level_snapshot});
                        end
                        1: begin sample0[0]<=soft_read;sample0[2]<=hard_read;end
                        2: begin sample1[0]<=soft_read;sample1[2]<=hard_read;end
                        3: begin sample0[1]<=soft_read;sample0[3]<=hard_read;end
                        4: begin sample1[1]<=soft_read;sample1[3]<=hard_read;stage<=2;end
                        default: begin stage<=0;protocol_error<=1;end
                    endcase
                    rom_step<=rom_step+1'b1;
                end
                2: begin
                    noise_word<=rounded_noise[18:0]; // exact sign-only narrowing
                    for(i=0;i<4;i=i+1) begin
                        phase_difference[i]<=$signed({sample1[i][15],sample1[i]})-
                                             $signed({sample0[i][15],sample0[i]});
                        phase_base[i]<=sample0[i];
                    end
                    stage<=3;
                end
                3: begin
                    for(i=0;i<4;i=i+1)
                        phase_product[i]<=phase_difference[i]*$signed({1'b0,fraction});
                    stage<=4;
                end
                4: begin
                    // Signed >>> floors: retain all precision except specified fraction.
                    for(i=0;i<4;i=i+1)
                        phase_interp[i]<=$signed(phase_base[i])+(phase_product[i]>>>16);
                    stage<=5;
                end
                5: begin
                    time_product[0]<=time_difference[0]*$signed({1'b0,time_snapshot});
                    time_product[1]<=time_difference[1]*$signed({1'b0,time_snapshot});
                    time_base[0]<=phase_interp[0];time_base[1]<=phase_interp[2];stage<=6;
                end
                6: begin
                    // Convex time lerps fit signed18; remove sign bits only.
                    time_interp[0]<=time_wide[0][17:0];
                    time_interp[1]<=time_wide[1][17:0];stage<=7;
                end
                7: begin
                    morph_product<=morph_difference*$signed({1'b0,mix_snapshot});
                    morph_base<=noisy_soft_wide[17:0];stage<=8;
                end
                8: begin
                    velocity_product<=blend*$signed({1'b0,joint_gain});stage<=9;
                end
                9: begin
                    if(rounded_product>48'sd8388607) pcm<=24'sh7fffff;
                    else if(rounded_product< -48'sd8388608) pcm<=24'sh800000;
                    else pcm<=rounded_product[23:0];
                    pcm_valid<=1;stage<=0;
                end
                default:begin stage<=0;protocol_error<=1;end
            endcase
            // Preserve R02 zero-gain install and control priority. Only accepted
            // ticks advance age; pending installation is its sole note restart.
            if (sample_tick && !busy) begin
                noise_lfsr<={noise_lfsr[21:0],noise_lfsr[22]^noise_lfsr[17]};
                fast_q8<=fast_next;slow_q8<=slow_next;
                if(mode!=OFF && note_age<14'd8192) note_age<=note_age+14'd1;
                if(mode!=OFF && note_age>=14'd8192) sustain_phase<=sustain_phase+16'd1;
                case(mode)
                    OFF: if(pending) begin
                        phase<=0;gain<=0;active_fcw<=pending_fcw;
                        active_velocity<=pending_velocity;pending<=0;mode<=ATTACK;
                        note_age<=0;sustain_phase<=0;
                    end
                    ATTACK:if(gain>=65536-ATTACK_STEP) begin gain<=65536;mode<=HOLD;end
                           else gain<=gain+ATTACK_STEP;
                    HOLD:gain<=65536;
                    RELEASE:if(gain<=RELEASE_STEP) begin gain<=0;mode<=OFF;end
                            else gain<=gain-RELEASE_STEP;
                    FADE:if(gain<=FADE_STEP) begin gain<=0;mode<=OFF;end
                         else gain<=gain-FADE_STEP;
                    default:begin mode<=OFF;gain<=0;end
                endcase
            end
            if(kill) begin pending<=0;mode<=FADE;end
            else if(release_event) begin pending<=0;mode<=RELEASE;end
            else if(note_on) begin
                if(valid_input_pitch) begin
                    pending<=1;pending_fcw<=fcw;
                    pending_velocity<={velocity,velocity[6:4]};
                end else begin pending<=0;invalid_pitch<=1;end
                mode<=FADE;
            end
        end
    end
endmodule
