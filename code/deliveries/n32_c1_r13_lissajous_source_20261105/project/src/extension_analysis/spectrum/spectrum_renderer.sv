`timescale 1ns/1ps
// R17 display-only spectrum curve: x64..575, y64..319.
// Fs48k/N2048, nearest-bin k=(column+1)>>1, DC column0 transparent.
// Root-confirmed Hann gain0.4999999888241291; interior peak dBFS from
// actual power=re^2+im^2, P0=1073741776.0000005. No audio/FFT change.
// Fixed -72..0dBFS,18dB/div, no automatic normalization or temporal averaging.
// Eight serialized threshold comparisons per unique positive bin; registered
// threshold ROM separates address/decode and37bit compare. No sqrt/log tree.
// Two complete512x19 span caches: BACK only, then frame-boundary FRONT swap.
// Curve spans are precomputed between valid adjacent columns, never pixels.
// Two input pixel captures, unchanged public ports; engine adds original3.
module spectrum_renderer (
    input  wire        pixel_clk,
    input  wire        pixel_rst_n,
    input  wire [15:0] pixel_x,
    input  wire [15:0] pixel_y,
    input  wire        data_enable,
    input  wire        frame_start,
    input  wire        page_enable,

    input  wire        spectrum_available,
    input  wire [31:0] display_generation,
    output reg         snapshot_read_enable,
    output reg  [10:0] snapshot_read_index,
    input  wire        snapshot_read_valid,
    input  wire [36:0] snapshot_read_power,

    output reg         spectrum_mask,
    output reg  [7:0]  rgb_r,
    output reg  [7:0]  rgb_g,
    output reg  [7:0]  rgb_b,
    output reg         data_enable_out,
    output reg         page_enable_out,
    output reg  [15:0] pixel_x_out,
    output reg  [15:0] pixel_y_out,
    output reg  [31:0] generation_out,

    output reg  [31:0] prefetch_complete_count,
    output reg  [31:0] prefetch_abort_count,
    output reg  [31:0] generation_change_error_count,
    output wire        render_available,
    output reg  [31:0] cache_commit_count
);

    localparam [15:0] PLOT_X0=16'd64, PLOT_Y0=16'd64;
    localparam [15:0] PLOT_WIDTH=16'd512, PLOT_HEIGHT=16'd256;
    localparam [36:0] FLOOR_POWER=37'd68;
    localparam [36:0] TOP_POWER=37'd1073741777;
    localparam [3:0] PF_IDLE=0, PF_ARM=1, PF_CLEAR_DC=2,
        PF_ISSUE=3, PF_WAIT=4, PF_RANGE=5,
        PF_LUT_ISSUE=6, PF_LUT_COMPARE=7, PF_WRITE_A=8, PF_WRITE_B=9;

    // Bit18 valid, bits17:9 first/low row, bits8:0 last/high row.
    // Rows0..256 represent y64..320. The floor at row256 is deliberately
    // outside the256-pixel data viewport, not wrapped to the top or raised.
    reg [18:0] curve_span0[0:511], curve_span1[0:511];
    reg [18:0] curve_read0,curve_read1;
    reg [3:0] prefetch_state;
    reg [8:0] prefetch_column;
    reg [10:0] prefetch_bin;
    reg [36:0] power_q;
    reg [8:0] current_row,previous_row;
    reg current_valid,previous_valid;
    reg [7:0] search_height,search_bit;
    reg [31:0] prefetch_generation;
    reg front_bank,write_bank,front_valid,pending_valid;
    reg [31:0] front_generation,pending_generation;

    // T[h]=ceil(P0*10^((-72+72*h/256)/10)),h0..255.
    // T[256] is the separate TOP_POWER above. Exact source table is sealed.
    reg [31:0] threshold_rom[0:255];
    reg [31:0] threshold_q;
    wire [7:0] threshold_address=search_height | search_bit;
    initial begin
        threshold_rom[0]=32'h00000044;
        threshold_rom[1]=32'h00000049;
        threshold_rom[2]=32'h0000004e;
        threshold_rom[3]=32'h00000053;
        threshold_rom[4]=32'h00000058;
        threshold_rom[5]=32'h0000005e;
        threshold_rom[6]=32'h00000064;
        threshold_rom[7]=32'h0000006b;
        threshold_rom[8]=32'h00000072;
        threshold_rom[9]=32'h0000007a;
        threshold_rom[10]=32'h00000082;
        threshold_rom[11]=32'h0000008b;
        threshold_rom[12]=32'h00000094;
        threshold_rom[13]=32'h0000009e;
        threshold_rom[14]=32'h000000a8;
        threshold_rom[15]=32'h000000b3;
        threshold_rom[16]=32'h000000bf;
        threshold_rom[17]=32'h000000cc;
        threshold_rom[18]=32'h000000da;
        threshold_rom[19]=32'h000000e8;
        threshold_rom[20]=32'h000000f8;
        threshold_rom[21]=32'h00000108;
        threshold_rom[22]=32'h0000011a;
        threshold_rom[23]=32'h0000012d;
        threshold_rom[24]=32'h00000141;
        threshold_rom[25]=32'h00000156;
        threshold_rom[26]=32'h0000016d;
        threshold_rom[27]=32'h00000186;
        threshold_rom[28]=32'h000001a0;
        threshold_rom[29]=32'h000001bc;
        threshold_rom[30]=32'h000001d9;
        threshold_rom[31]=32'h000001f9;
        threshold_rom[32]=32'h0000021b;
        threshold_rom[33]=32'h0000023f;
        threshold_rom[34]=32'h00000265;
        threshold_rom[35]=32'h0000028e;
        threshold_rom[36]=32'h000002ba;
        threshold_rom[37]=32'h000002e8;
        threshold_rom[38]=32'h0000031a;
        threshold_rom[39]=32'h0000034f;
        threshold_rom[40]=32'h00000388;
        threshold_rom[41]=32'h000003c4;
        threshold_rom[42]=32'h00000405;
        threshold_rom[43]=32'h0000044a;
        threshold_rom[44]=32'h00000493;
        threshold_rom[45]=32'h000004e1;
        threshold_rom[46]=32'h00000535;
        threshold_rom[47]=32'h0000058e;
        threshold_rom[48]=32'h000005ed;
        threshold_rom[49]=32'h00000653;
        threshold_rom[50]=32'h000006bf;
        threshold_rom[51]=32'h00000732;
        threshold_rom[52]=32'h000007ae;
        threshold_rom[53]=32'h00000831;
        threshold_rom[54]=32'h000008bd;
        threshold_rom[55]=32'h00000953;
        threshold_rom[56]=32'h000009f3;
        threshold_rom[57]=32'h00000a9d;
        threshold_rom[58]=32'h00000b53;
        threshold_rom[59]=32'h00000c15;
        threshold_rom[60]=32'h00000ce4;
        threshold_rom[61]=32'h00000dc0;
        threshold_rom[62]=32'h00000eac;
        threshold_rom[63]=32'h00000fa7;
        threshold_rom[64]=32'h000010b3;
        threshold_rom[65]=32'h000011d1;
        threshold_rom[66]=32'h00001302;
        threshold_rom[67]=32'h00001448;
        threshold_rom[68]=32'h000015a3;
        threshold_rom[69]=32'h00001716;
        threshold_rom[70]=32'h000018a1;
        threshold_rom[71]=32'h00001a47;
        threshold_rom[72]=32'h00001c09;
        threshold_rom[73]=32'h00001de9;
        threshold_rom[74]=32'h00001fe9;
        threshold_rom[75]=32'h0000220c;
        threshold_rom[76]=32'h00002453;
        threshold_rom[77]=32'h000026c1;
        threshold_rom[78]=32'h00002959;
        threshold_rom[79]=32'h00002c1d;
        threshold_rom[80]=32'h00002f10;
        threshold_rom[81]=32'h00003236;
        threshold_rom[82]=32'h00003592;
        threshold_rom[83]=32'h00003928;
        threshold_rom[84]=32'h00003cfa;
        threshold_rom[85]=32'h0000410f;
        threshold_rom[86]=32'h00004569;
        threshold_rom[87]=32'h00004a0e;
        threshold_rom[88]=32'h00004f02;
        threshold_rom[89]=32'h0000544b;
        threshold_rom[90]=32'h000059ef;
        threshold_rom[91]=32'h00005ff3;
        threshold_rom[92]=32'h0000665e;
        threshold_rom[93]=32'h00006d38;
        threshold_rom[94]=32'h00007486;
        threshold_rom[95]=32'h00007c52;
        threshold_rom[96]=32'h000084a3;
        threshold_rom[97]=32'h00008d83;
        threshold_rom[98]=32'h000096fb;
        threshold_rom[99]=32'h0000a114;
        threshold_rom[100]=32'h0000abdb;
        threshold_rom[101]=32'h0000b75b;
        threshold_rom[102]=32'h0000c39f;
        threshold_rom[103]=32'h0000d0b5;
        threshold_rom[104]=32'h0000deac;
        threshold_rom[105]=32'h0000ed91;
        threshold_rom[106]=32'h0000fd76;
        threshold_rom[107]=32'h00010e6b;
        threshold_rom[108]=32'h00012083;
        threshold_rom[109]=32'h000133d0;
        threshold_rom[110]=32'h00014868;
        threshold_rom[111]=32'h00015e61;
        threshold_rom[112]=32'h000175d2;
        threshold_rom[113]=32'h00018ed4;
        threshold_rom[114]=32'h0001a983;
        threshold_rom[115]=32'h0001c5fb;
        threshold_rom[116]=32'h0001e45a;
        threshold_rom[117]=32'h000204c2;
        threshold_rom[118]=32'h00022754;
        threshold_rom[119]=32'h00024c37;
        threshold_rom[120]=32'h00027392;
        threshold_rom[121]=32'h00029d8e;
        threshold_rom[122]=32'h0002ca5a;
        threshold_rom[123]=32'h0002fa24;
        threshold_rom[124]=32'h00032d22;
        threshold_rom[125]=32'h00036388;
        threshold_rom[126]=32'h00039d93;
        threshold_rom[127]=32'h0003db7f;
        threshold_rom[128]=32'h00041d90;
        threshold_rom[129]=32'h0004640d;
        threshold_rom[130]=32'h0004af41;
        threshold_rom[131]=32'h0004ff7c;
        threshold_rom[132]=32'h00055516;
        threshold_rom[133]=32'h0005b06b;
        threshold_rom[134]=32'h000611db;
        threshold_rom[135]=32'h000679d0;
        threshold_rom[136]=32'h0006e8ba;
        threshold_rom[137]=32'h00075f0f;
        threshold_rom[138]=32'h0007dd4f;
        threshold_rom[139]=32'h00086401;
        threshold_rom[140]=32'h0008f3b7;
        threshold_rom[141]=32'h00098d09;
        threshold_rom[142]=32'h000a309e;
        threshold_rom[143]=32'h000adf24;
        threshold_rom[144]=32'h000b9957;
        threshold_rom[145]=32'h000c6000;
        threshold_rom[146]=32'h000d33f3;
        threshold_rom[147]=32'h000e1614;
        threshold_rom[148]=32'h000f0756;
        threshold_rom[149]=32'h001008bc;
        threshold_rom[150]=32'h00111b5b;
        threshold_rom[151]=32'h00124059;
        threshold_rom[152]=32'h001378f1;
        threshold_rom[153]=32'h0014c673;
        threshold_rom[154]=32'h00162a45;
        threshold_rom[155]=32'h0017a5e6;
        threshold_rom[156]=32'h00193aec;
        threshold_rom[157]=32'h001aeb0b;
        threshold_rom[158]=32'h001cb814;
        threshold_rom[159]=32'h001ea3f4;
        threshold_rom[160]=32'h0020b0bd;
        threshold_rom[161]=32'h0022e0a2;
        threshold_rom[162]=32'h002535fd;
        threshold_rom[163]=32'h0027b34e;
        threshold_rom[164]=32'h002a5b43;
        threshold_rom[165]=32'h002d30b6;
        threshold_rom[166]=32'h003036b2;
        threshold_rom[167]=32'h00337075;
        threshold_rom[168]=32'h0036e178;
        threshold_rom[169]=32'h003a8d6d;
        threshold_rom[170]=32'h003e7843;
        threshold_rom[171]=32'h0042a632;
        threshold_rom[172]=32'h00471bb6;
        threshold_rom[173]=32'h004bdd99;
        threshold_rom[174]=32'h0050f0f6;
        threshold_rom[175]=32'h00565b43;
        threshold_rom[176]=32'h005c224e;
        threshold_rom[177]=32'h00624c4e;
        threshold_rom[178]=32'h0068dfe0;
        threshold_rom[179]=32'h006fe415;
        threshold_rom[180]=32'h00776076;
        threshold_rom[181]=32'h007f5d0e;
        threshold_rom[182]=32'h0087e26f;
        threshold_rom[183]=32'h0090f9c2;
        threshold_rom[184]=32'h009aacc9;
        threshold_rom[185]=32'h00a505ef;
        threshold_rom[186]=32'h00b01052;
        threshold_rom[187]=32'h00bbd7cd;
        threshold_rom[188]=32'h00c86906;
        threshold_rom[189]=32'h00d5d17e;
        threshold_rom[190]=32'h00e41f9b;
        threshold_rom[191]=32'h00f362b9;
        threshold_rom[192]=32'h0103ab3d;
        threshold_rom[193]=32'h01150aa4;
        threshold_rom[194]=32'h01279397;
        threshold_rom[195]=32'h013b59fd;
        threshold_rom[196]=32'h01507315;
        threshold_rom[197]=32'h0166f585;
        threshold_rom[198]=32'h017ef97d;
        threshold_rom[199]=32'h019898c6;
        threshold_rom[200]=32'h01b3eee5;
        threshold_rom[201]=32'h01d11936;
        threshold_rom[202]=32'h01f0370d;
        threshold_rom[203]=32'h021169d4;
        threshold_rom[204]=32'h0234d534;
        threshold_rom[205]=32'h025a9f36;
        threshold_rom[206]=32'h0282f071;
        threshold_rom[207]=32'h02adf432;
        threshold_rom[208]=32'h02dbd8ac;
        threshold_rom[209]=32'h030ccf28;
        threshold_rom[210]=32'h03410c3d;
        threshold_rom[211]=32'h0378c805;
        threshold_rom[212]=32'h03b43e5d;
        threshold_rom[213]=32'h03f3af21;
        threshold_rom[214]=32'h04375e74;
        threshold_rom[215]=32'h047f9507;
        threshold_rom[216]=32'h04cca06b;
        threshold_rom[217]=32'h051ed35c;
        threshold_rom[218]=32'h05768625;
        threshold_rom[219]=32'h05d416f4;
        threshold_rom[220]=32'h0637ea49;
        threshold_rom[221]=32'h06a26b59;
        threshold_rom[222]=32'h07140c87;
        threshold_rom[223]=32'h078d47de;
        threshold_rom[224]=32'h080e9f91;
        threshold_rom[225]=32'h08989e8c;
        threshold_rom[226]=32'h092bd903;
        threshold_rom[227]=32'h09c8ed16;
        threshold_rom[228]=32'h0a70837a;
        threshold_rom[229]=32'h0b23502c;
        threshold_rom[230]=32'h0be21335;
        threshold_rom[231]=32'h0cad9975;
        threshold_rom[232]=32'h0d86bd84;
        threshold_rom[233]=32'h0e6e6897;
        threshold_rom[234]=32'h0f65937e;
        threshold_rom[235]=32'h106d47b0;
        threshold_rom[236]=32'h1186a065;
        threshold_rom[237]=32'h12b2cbc7;
        threshold_rom[238]=32'h13f30c3b;
        threshold_rom[239]=32'h1548b9b3;
        threshold_rom[240]=32'h16b54327;
        threshold_rom[241]=32'h183a301b;
        threshold_rom[242]=32'h19d92245;
        threshold_rom[243]=32'h1b93d74c;
        threshold_rom[244]=32'h1d6c2aaa;
        threshold_rom[245]=32'h1f6417a6;
        threshold_rom[246]=32'h217dbb79;
        threshold_rom[247]=32'h23bb5792;
        threshold_rom[248]=32'h261f5400;
        threshold_rom[249]=32'h28ac420b;
        threshold_rom[250]=32'h2b64def4;
        threshold_rom[251]=32'h2e4c16e6;
        threshold_rom[252]=32'h31650819;
        threshold_rom[253]=32'h34b30630;
        threshold_rom[254]=32'h38399dc3;
        threshold_rom[255]=32'h3bfc9839;
    end
    always @(posedge pixel_clk) begin
        threshold_q <= threshold_rom[threshold_address];
    end
    wire threshold_pass=power_q >= {5'd0,threshold_q};
    wire [7:0] accepted_height=threshold_pass ? threshold_address : search_height;
    wire commit_cache=frame_start && pending_valid;
    wire read_bank_input=commit_cache ? write_bank : front_bank;
    wire read_valid_input=front_valid || commit_cache;
    wire [31:0] read_generation_input=commit_cache ? pending_generation : front_generation;
    wire prefetch_source_current=spectrum_available && display_generation==prefetch_generation;
    assign render_available=front_valid;

    function automatic [31:0] sat_inc;
        input [31:0] value;
        begin sat_inc=(&value) ? value : value+32'd1; end
    endfunction

    always @* begin
        snapshot_read_enable=1'b0;
        snapshot_read_index=11'd0;
        if(pixel_rst_n && !frame_start && prefetch_source_current && prefetch_state==PF_ISSUE) begin
            snapshot_read_enable=1'b1;
            snapshot_read_index=prefetch_bin;
        end
    end

    reg span_write_enable;
    reg [18:0] span_write_data;
    reg [8:0] span_low,span_high;
    always @* begin
        span_write_enable=1'b0;
        span_write_data=19'd0;
        span_low=current_row;
        span_high=current_row;
        if(previous_valid) begin
            span_low=(previous_row<current_row) ? previous_row : current_row;
            span_high=(previous_row>current_row) ? previous_row : current_row;
        end
        if(pixel_rst_n && !frame_start && prefetch_source_current && write_bank!=front_bank) begin
            case(prefetch_state)
                PF_CLEAR_DC: begin
                    span_write_enable=1'b1;
                    span_write_data=19'd0;
                end
                PF_WRITE_A: begin
                    span_write_enable=1'b1;
                    span_write_data=current_valid ? {1'b1,span_low,span_high} : 19'd0;
                end
                PF_WRITE_B: begin
                    // Duplicate nearest-bin column is a point at this row.
                    span_write_enable=1'b1;
                    span_write_data=current_valid ? {1'b1,current_row,current_row} : 19'd0;
                end
                default: begin
                    span_write_enable=1'b0;
                    span_write_data=19'd0;
                end
            endcase
        end
    end

    wire inside_active_input=data_enable && pixel_x<16'd640 && pixel_y<16'd480;
    wire inside_plot_input=inside_active_input && pixel_x>=PLOT_X0 &&
        pixel_x<PLOT_X0+PLOT_WIDTH && pixel_y>=PLOT_Y0 && pixel_y<PLOT_Y0+PLOT_HEIGHT;
    wire [15:0] plot_column_input=pixel_x-PLOT_X0;
    wire [15:0] plot_row_input=pixel_y-PLOT_Y0;
    always @(posedge pixel_clk) begin
        if(span_write_enable && !write_bank)
            curve_span0[prefetch_column] <= span_write_data;
        if(span_write_enable && write_bank)
            curve_span1[prefetch_column] <= span_write_data;
        curve_read0 <= curve_span0[plot_column_input[8:0]];
        curve_read1 <= curve_span1[plot_column_input[8:0]];
    end

    reg data_enable_s1,page_enable_s1;
    reg [15:0] pixel_x_s1,pixel_y_s1;
    reg [31:0] generation_s1;
    reg inside_plot_s1,cache_current_s1,read_bank_s1;
    reg [15:0] plot_column_s1,plot_row_s1;
    wire [18:0] span_s1=read_bank_s1 ? curve_read1 : curve_read0;
    wire trace_pixel_s1=span_s1[18] && plot_row_s1 >= {7'd0,span_s1[17:9]} &&
        plot_row_s1 <= {7'd0,span_s1[8:0]};
    reg render_mask_comb;
    reg [7:0] render_r_comb,render_g_comb,render_b_comb;
    always @* begin
        render_mask_comb=1'b0;
        render_r_comb=8'd0;render_g_comb=8'd0;render_b_comb=8'd0;
        if(page_enable_s1 && inside_plot_s1) begin
            if(!cache_current_s1) begin
                // Missing complete FRONT is distinct from valid silent/zero.
                render_mask_comb=1'b1;
                render_r_comb=8'h20;
                if({1'b0,plot_column_s1[8:1]}==plot_row_s1[8:0] ||
                   {1'b0,plot_column_s1[8:1]}+plot_row_s1[8:0]==9'd255) begin
                    render_r_comb=8'hff;render_g_comb=8'h50;
                end
            end else if(trace_pixel_s1) begin
                render_mask_comb=1'b1;
                render_r_comb=8'h20;render_g_comb=8'he0;render_b_comb=8'hff;
            end
            // Normal non-curve pixels stay transparent for task4 grid.
        end
    end

    always @(posedge pixel_clk or negedge pixel_rst_n) begin
        if(!pixel_rst_n) begin
            prefetch_state<=PF_IDLE;prefetch_column<=0;prefetch_bin<=1;
            power_q<=0;current_row<=9'd256;previous_row<=9'd256;
            current_valid<=0;previous_valid<=0;search_height<=0;search_bit<=0;
            prefetch_generation<=0;front_bank<=0;write_bank<=1;
            front_valid<=0;pending_valid<=0;front_generation<=0;pending_generation<=0;
            prefetch_complete_count<=0;prefetch_abort_count<=0;
            generation_change_error_count<=0;cache_commit_count<=0;
            data_enable_s1<=0;page_enable_s1<=0;pixel_x_s1<=0;pixel_y_s1<=0;generation_s1<=0;
            inside_plot_s1<=0;cache_current_s1<=0;read_bank_s1<=0;plot_column_s1<=0;plot_row_s1<=0;
            spectrum_mask<=0;rgb_r<=0;rgb_g<=0;rgb_b<=0;
            data_enable_out<=0;page_enable_out<=0;pixel_x_out<=0;pixel_y_out<=0;generation_out<=0;
        end else begin
            data_enable_s1<=data_enable;page_enable_s1<=page_enable;
            pixel_x_s1<=pixel_x;pixel_y_s1<=pixel_y;generation_s1<=read_generation_input;
            inside_plot_s1<=inside_plot_input;cache_current_s1<=read_valid_input;
            read_bank_s1<=read_bank_input;plot_column_s1<=plot_column_input;plot_row_s1<=plot_row_input;
            spectrum_mask<=render_mask_comb;rgb_r<=render_r_comb;rgb_g<=render_g_comb;rgb_b<=render_b_comb;
            data_enable_out<=data_enable_s1;page_enable_out<=page_enable_s1;
            pixel_x_out<=pixel_x_s1;pixel_y_out<=pixel_y_s1;generation_out<=generation_s1;

            if(frame_start) begin
                if(prefetch_state!=PF_IDLE && prefetch_state!=PF_ARM)
                    prefetch_abort_count<=sat_inc(prefetch_abort_count);
                if(pending_valid) begin
                    front_bank<=write_bank;front_generation<=pending_generation;front_valid<=1'b1;
                    cache_commit_count<=sat_inc(cache_commit_count);
                end
                pending_valid<=1'b0;previous_valid<=1'b0;
                prefetch_column<=0;prefetch_state<=PF_ARM;
            end else begin
                case(prefetch_state)
                    PF_IDLE: prefetch_state<=PF_IDLE;
                    PF_ARM: begin
                        previous_valid<=1'b0;previous_row<=9'd256;
                        if(spectrum_available) begin
                            write_bank<=~front_bank;prefetch_generation<=display_generation;
                            prefetch_column<=0;prefetch_bin<=11'd1;
                            prefetch_state<=PF_CLEAR_DC;
                        end else prefetch_state<=PF_IDLE;
                    end
                    default: begin
                        if(!prefetch_source_current) begin
                            generation_change_error_count<=sat_inc(generation_change_error_count);
                            prefetch_abort_count<=sat_inc(prefetch_abort_count);
                            pending_valid<=1'b0;previous_valid<=1'b0;prefetch_state<=PF_IDLE;
                        end else begin
                            case(prefetch_state)
                                PF_CLEAR_DC: begin
                                    prefetch_column<=9'd1;previous_valid<=1'b0;
                                    prefetch_state<=PF_ISSUE;
                                end
                                PF_ISSUE: prefetch_state<=PF_WAIT;
                                PF_WAIT: begin
                                    if(snapshot_read_valid) begin
                                        power_q<=snapshot_read_power;prefetch_state<=PF_RANGE;
                                    end
                                end
                                PF_RANGE: begin
                                    if(power_q<FLOOR_POWER) begin
                                        current_valid<=1'b0;current_row<=9'd256;prefetch_state<=PF_WRITE_A;
                                    end else if(power_q>=TOP_POWER) begin
                                        current_valid<=1'b1;current_row<=9'd0;prefetch_state<=PF_WRITE_A;
                                    end else begin
                                        current_valid<=1'b1;search_height<=8'd0;search_bit<=8'h80;
                                        prefetch_state<=PF_LUT_ISSUE;
                                    end
                                end
                                PF_LUT_ISSUE: prefetch_state<=PF_LUT_COMPARE;
                                PF_LUT_COMPARE: begin
                                    search_height<=accepted_height;
                                    if(search_bit==8'd1) begin
                                        current_row<=9'd256-{1'b0,accepted_height};prefetch_state<=PF_WRITE_A;
                                    end else begin
                                        search_bit<=search_bit>>1;prefetch_state<=PF_LUT_ISSUE;
                                    end
                                end
                                PF_WRITE_A: begin
                                    previous_row<=current_row;previous_valid<=current_valid;
                                    if(prefetch_bin==11'd256) begin
                                        pending_generation<=prefetch_generation;pending_valid<=1'b1;
                                        prefetch_complete_count<=sat_inc(prefetch_complete_count);
                                        prefetch_state<=PF_IDLE;
                                    end else begin
                                        prefetch_column<=prefetch_column+1'b1;prefetch_state<=PF_WRITE_B;
                                    end
                                end
                                PF_WRITE_B: begin
                                    previous_row<=current_row;previous_valid<=current_valid;
                                    prefetch_column<=prefetch_column+1'b1;prefetch_bin<=prefetch_bin+1'b1;
                                    prefetch_state<=PF_ISSUE;
                                end
                                default: begin
                                    pending_valid<=1'b0;previous_valid<=1'b0;
                                    prefetch_abort_count<=sat_inc(prefetch_abort_count);prefetch_state<=PF_IDLE;
                                end
                            endcase
                        end
                    end
                endcase
            end
        end
    end
endmodule
