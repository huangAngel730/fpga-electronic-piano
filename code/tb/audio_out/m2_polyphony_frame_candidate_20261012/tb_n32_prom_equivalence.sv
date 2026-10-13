// New primitive implementation tests, not a replay of historical sound suites.
`timescale 1ns/1ps
module tb_n32_prom_equivalence;
    logic clk=0;
    always #12.5 clk=~clk;
    GSR GSR(.GSRI(1'b1));
    logic ce=0;
    logic [9:0] address=0;
    logic [5:0] octave_address=0;
    wire [9:0] encoded=address ^ {address[8:0],address[9]} ^ {address[6:0],address[9:7]};
    wire [15:0] gain,sine,wave;
    wire [19:0] octave,fraction;
    m2_prom_gain a(.clk(clk),.ce(ce),.addr(address),.data(gain));
    m2_prom_lfo b(.clk(clk),.ce(ce),.addr(address),.data(sine));
    m2_prom_wave c(.clk(clk),.ce(ce),.addr(address),.data(wave));
    m2_prom_oct d(.clk(clk),.ce(ce),.addr(octave_address),.data(octave));
    m2_prom_sub e(.clk(clk),.ce(ce),.addr(encoded),.data(fraction));
    reg [15:0] golden_gain[0:1023],golden_sine[0:1023],golden_wave[0:1023];
    reg [19:0] golden_oct[0:49],golden_sub[0:1023];
    logic rst_n=0,tick=0,on=0,off=0,sample_enable=0;
    logic [9:0] velocity=0;
    logic signed [11:0] bend=0;
    logic [11:0] modulation=0;
    logic [4:0] pitch_range=2;
    logic [31:0] base_fcw=32'd78741068;
    wire [15:0] env_original,env_candidate;
    wire [2:0] state_original,state_candidate;
    wire [31:0] fcw_original,fcw_candidate;
    wire valid_original,valid_candidate;
    adsr_piano_envelope ref_env(.sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(tick),.note_on(on),.note_off(off),.velocity(velocity),.envelope_level(env_original),.state_out(state_original));
    m2_adsr_piano_prom new_env(.sys_clk(clk),.sys_rst_n(rst_n),.sample_tick(tick),.note_on(on),.note_off(off),.velocity(velocity),.envelope_level(env_candidate),.state_out(state_candidate));
    pitch_mod_fcw_pipeline ref_pitch(.sys_clk(clk),.sys_rst_n(rst_n),.sample_enable(sample_enable),.note_on(on),.bend(bend),.modulation(modulation),.pitch_range(pitch_range),.base_fcw(base_fcw),.fcw_out(fcw_original),.fcw_valid(valid_original));
    m2_pitch_mod_prom new_pitch(.sys_clk(clk),.sys_rst_n(rst_n),.sample_enable(sample_enable),.note_on(on),.bend(bend),.modulation(modulation),.pitch_range(pitch_range),.base_fcw(base_fcw),.fcw_out(fcw_candidate),.fcw_valid(valid_candidate));
    logic compare_components=0;
    integer rom_checks=0,component_checks=0,valid_results=0,notes_on=0,notes_off=0,resets=0;
    logic [31:0] random_word=32'h7135abcd;
    always @(posedge clk) begin
        #2;
        if(compare_components) begin
            component_checks=component_checks+1;
            if({env_original,state_original,valid_original}!=={env_candidate,state_candidate,valid_candidate})
                $fatal(1,"PROM_COMPONENT_ENV_OR_VALID_MISMATCH");
            if(valid_original) begin
                valid_results=valid_results+1;
                if(fcw_original!==fcw_candidate) $fatal(1,"PROM_COMPONENT_FCW_MISMATCH");
            end
        end
    end
    integer i,k;
    logic [87:0] kept;
    initial begin
        $readmemh("rom/velocity_gain_rom.mem",golden_gain);
        $readmemh("rom/lfo_sine_q15.mem",golden_sine);
        $readmemh("rom/piano_band_4x256_8191.mem",golden_wave);
        $readmemh("rom/oct_ratio_q16.mem",golden_oct);
        $readmemh("rom/sub_ratio_q16.mem",golden_sub);
        repeat(3) @(negedge clk);
        for(i=0;i<1024;i=i+1) begin
            ce=1;address=10'(i);octave_address=6'(i%50);
            @(posedge clk);#3;
            if(gain!==golden_gain[i] || sine!==golden_sine[i] || wave!==golden_wave[i] ||
               octave!==golden_oct[i%50] || fraction!==golden_sub[i])
                $fatal(1,"PROM_FULL_ADDRESS_OR_SINGLE_CYCLE_MISMATCH addr=%0d",i);
            rom_checks=rom_checks+5;
            kept={gain,sine,wave,octave,fraction};
            @(negedge clk);ce=0;address=10'(1023-i);octave_address=6'((i+17)%50);
            @(posedge clk);#3;
            if({gain,sine,wave,octave,fraction}!==kept) $fatal(1,"PROM_CE_HOLD_CHANGED");
            rom_checks=rom_checks+5;
            @(negedge clk);
        end
        compare_components=1;rst_n=1;
        for(k=0;k<6000;k=k+1) begin
            @(negedge clk);
            random_word={random_word[30:0],random_word[31]^random_word[21]^random_word[1]^random_word[0]};
            rst_n=!(k==900 || k==901 || k==3700 || k==3701);
            if(!rst_n)resets=resets+1;
            tick=k%13==0;sample_enable=(k%19<11);
            on=k%337==0;off=k%337==220;
            if(on)notes_on=notes_on+1;
            if(off)notes_off=notes_off+1;
            velocity=10'(random_word);bend=12'(random_word>>10);
            modulation=12'(random_word>>20);pitch_range=5'(k%25);
            base_fcw=k%2 ? 32'd78741068 : 32'd39370534;
        end
        @(negedge clk);on=0;off=0;sample_enable=0;tick=0;
        repeat(10) @(negedge clk);
        if(rom_checks!=10240 || component_checks<6000 || valid_results<3000 || notes_on<10 || notes_off<10 || resets!=4)
            $fatal(1,"PROM_EQUIVALENCE_COVERAGE_MISSING");
        $display("END rom_checks=%0d component_edges=%0d pitch_valid=%0d note_on=%0d note_off=%0d reset_edges=%0d",rom_checks,component_checks,valid_results,notes_on,notes_off,resets);
        $display("PASS PROM_VENDOR_ALL_ADDRESS_CE_AND_COMPONENT_EQUIVALENCE");$finish;
    end
    initial begin #1ms;$fatal(1,"PROM_COMPONENT_TIMEOUT");end
endmodule
