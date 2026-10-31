`timescale 1ns/1ps
// R13 R02 reserved display only. No PCM input, capture, FFT or audio feedback.
// One input tuple becomes RGB after EXACTLY FIVE rising-edge captures.
// rst_n: active-low asynchronous assertion, caller synchronizes deassertion.
// pixel_clk: existing 25 MHz; coordinates use the existing 640x480 raster.
module pro_reserved_analysis_page (
    input wire pixel_clk,
    input wire rst_n,
    input wire [15:0] pixel_x,
    input wire [15:0] pixel_y,
    input wire data_enable,
    input wire page_is_spectrum,
    input wire selected_timbre,
    output reg [7:0] rgb_r,
    output reg [7:0] rgb_g,
    output reg [7:0] rgb_b
);
    // BEGIN GENERATED FONT FUNCTIONS
    function automatic [15:0] han_row;
        input [1:0] glyph; input [3:0] row;
        begin case ({glyph,row})
            6'd0:han_row=16'h1820;
            6'd1:han_row=16'h1820;
            6'd2:han_row=16'h33fe;
            6'd3:han_row=16'h6020;
            6'd4:han_row=16'hc820;
            6'd5:han_row=16'h1fff;
            6'd6:han_row=16'h3000;
            6'd7:han_row=16'h3000;
            6'd8:han_row=16'h77ff;
            6'd9:han_row=16'hf008;
            6'd10:han_row=16'hb308;
            6'd11:han_row=16'h3188;
            6'd12:han_row=16'h3088;
            6'd13:han_row=16'h3008;
            6'd14:han_row=16'h3078;
            6'd15:han_row=16'h3000;
            6'd16:han_row=16'h0000;
            6'd17:han_row=16'h3060;
            6'd18:han_row=16'h3020;
            6'd19:han_row=16'h33fe;
            6'd20:han_row=16'hfd8c;
            6'd21:han_row=16'h3098;
            6'd22:han_row=16'h37ff;
            6'd23:han_row=16'h3840;
            6'd24:han_row=16'h78c0;
            6'd25:han_row=16'hf7ff;
            6'd26:han_row=16'h3188;
            6'd27:han_row=16'h31f8;
            6'd28:han_row=16'h30fc;
            6'd29:han_row=16'he78e;
            6'd30:han_row=16'h0000;
            6'd31:han_row=16'h0000;
            6'd32:han_row=16'h0000;
            6'd33:han_row=16'h0400;
            6'd34:han_row=16'h0600;
            6'd35:han_row=16'h0300;
            6'd36:han_row=16'h0180;
            6'd37:han_row=16'h0180;
            6'd38:han_row=16'h03c0;
            6'd39:han_row=16'h0240;
            6'd40:han_row=16'h0660;
            6'd41:han_row=16'h0420;
            6'd42:han_row=16'h0c30;
            6'd43:han_row=16'h1818;
            6'd44:han_row=16'h300c;
            6'd45:han_row=16'h6006;
            6'd46:han_row=16'h4002;
            6'd47:han_row=16'h0000;
            default:han_row=0;
        endcase end
    endfunction
    function automatic [15:0] ascii_row;
        input [6:0] character; input [2:0] row;
        begin case ({character,row})
            10'd384:ascii_row=16'h7000;
            10'd385:ascii_row=16'h8800;
            10'd386:ascii_row=16'h9800;
            10'd387:ascii_row=16'ha800;
            10'd388:ascii_row=16'hc800;
            10'd389:ascii_row=16'h8800;
            10'd390:ascii_row=16'h7000;
            10'd392:ascii_row=16'h2000;
            10'd393:ascii_row=16'h6000;
            10'd394:ascii_row=16'h2000;
            10'd395:ascii_row=16'h2000;
            10'd396:ascii_row=16'h2000;
            10'd397:ascii_row=16'h2000;
            10'd398:ascii_row=16'h7000;
            10'd520:ascii_row=16'h7000;
            10'd521:ascii_row=16'h8800;
            10'd522:ascii_row=16'h8800;
            10'd523:ascii_row=16'hf800;
            10'd524:ascii_row=16'h8800;
            10'd525:ascii_row=16'h8800;
            10'd526:ascii_row=16'h8800;
            10'd536:ascii_row=16'h7800;
            10'd537:ascii_row=16'h8000;
            10'd538:ascii_row=16'h8000;
            10'd539:ascii_row=16'h8000;
            10'd540:ascii_row=16'h8000;
            10'd541:ascii_row=16'h8000;
            10'd542:ascii_row=16'h7800;
            10'd552:ascii_row=16'hf800;
            10'd553:ascii_row=16'h8000;
            10'd554:ascii_row=16'h8000;
            10'd555:ascii_row=16'hf000;
            10'd556:ascii_row=16'h8000;
            10'd557:ascii_row=16'h8000;
            10'd558:ascii_row=16'hf800;
            10'd616:ascii_row=16'h8800;
            10'd617:ascii_row=16'hd800;
            10'd618:ascii_row=16'ha800;
            10'd619:ascii_row=16'ha800;
            10'd620:ascii_row=16'h8800;
            10'd621:ascii_row=16'h8800;
            10'd622:ascii_row=16'h8800;
            10'd624:ascii_row=16'h8800;
            10'd625:ascii_row=16'hc800;
            10'd626:ascii_row=16'ha800;
            10'd627:ascii_row=16'h9800;
            10'd628:ascii_row=16'h8800;
            10'd629:ascii_row=16'h8800;
            10'd630:ascii_row=16'h8800;
            10'd632:ascii_row=16'h7000;
            10'd633:ascii_row=16'h8800;
            10'd634:ascii_row=16'h8800;
            10'd635:ascii_row=16'h8800;
            10'd636:ascii_row=16'h8800;
            10'd637:ascii_row=16'h8800;
            10'd638:ascii_row=16'h7000;
            10'd640:ascii_row=16'hf000;
            10'd641:ascii_row=16'h8800;
            10'd642:ascii_row=16'h8800;
            10'd643:ascii_row=16'hf000;
            10'd644:ascii_row=16'h8000;
            10'd645:ascii_row=16'h8000;
            10'd646:ascii_row=16'h8000;
            10'd656:ascii_row=16'hf000;
            10'd657:ascii_row=16'h8800;
            10'd658:ascii_row=16'h8800;
            10'd659:ascii_row=16'hf000;
            10'd660:ascii_row=16'ha000;
            10'd661:ascii_row=16'h9000;
            10'd662:ascii_row=16'h8800;
            10'd664:ascii_row=16'h7800;
            10'd665:ascii_row=16'h8000;
            10'd666:ascii_row=16'h8000;
            10'd667:ascii_row=16'h7000;
            10'd668:ascii_row=16'h0800;
            10'd669:ascii_row=16'h0800;
            10'd670:ascii_row=16'hf000;
            10'd672:ascii_row=16'hf800;
            10'd673:ascii_row=16'h2000;
            10'd674:ascii_row=16'h2000;
            10'd675:ascii_row=16'h2000;
            10'd676:ascii_row=16'h2000;
            10'd677:ascii_row=16'h2000;
            10'd678:ascii_row=16'h2000;
            10'd680:ascii_row=16'h8800;
            10'd681:ascii_row=16'h8800;
            10'd682:ascii_row=16'h8800;
            10'd683:ascii_row=16'h8800;
            10'd684:ascii_row=16'h8800;
            10'd685:ascii_row=16'h8800;
            10'd686:ascii_row=16'h7000;
            10'd688:ascii_row=16'h8800;
            10'd689:ascii_row=16'h8800;
            10'd690:ascii_row=16'h8800;
            10'd691:ascii_row=16'h8800;
            10'd692:ascii_row=16'h8800;
            10'd693:ascii_row=16'h5000;
            10'd694:ascii_row=16'h2000;
            10'd696:ascii_row=16'h8800;
            10'd697:ascii_row=16'h8800;
            10'd698:ascii_row=16'h8800;
            10'd699:ascii_row=16'ha800;
            10'd700:ascii_row=16'ha800;
            10'd701:ascii_row=16'ha800;
            10'd702:ascii_row=16'h5000;
            default:ascii_row=0;
        endcase end
    endfunction
    // END GENERATED FONT FUNCTIONS

    function automatic [6:0] title_character;
        input spectrum;
        input [2:0] slot;
        begin
            title_character=7'd32;
            if (spectrum) begin
                case (slot)
                    0:title_character="S"; 1:title_character="P";
                    2:title_character="E"; 3:title_character="C";
                    4:title_character="T"; 5:title_character="R";
                    6:title_character="U"; 7:title_character="M";
                endcase
            end else begin
                case (slot)
                    0:title_character="W"; 1:title_character="A";
                    2:title_character="V"; 3:title_character="E";
                    default:title_character=7'd32;
                endcase
            end
        end
    endfunction
    function automatic [6:0] tone_character;
        input [2:0] slot;
        input tone;
        begin
            case (slot)
                0:tone_character="T"; 1:tone_character="O";
                2:tone_character="N"; 3:tone_character="E";
                5:tone_character=tone ? "1" : "0";
                default:tone_character=7'd32;
            endcase
        end
    endfunction

    wire active_pixel=data_enable && pixel_x<16'd640 && pixel_y<16'd480;
    wire in_card=pixel_x>=16'd64 && pixel_x<16'd576 &&
                 pixel_y>=16'd40 && pixel_y<16'd400;
    wire in_accent=(pixel_x>=16'd64 && pixel_x<16'd576 &&
                    pixel_y>=16'd40 && pixel_y<16'd44) ||
                   (pixel_x>=16'd96 && pixel_x<16'd544 &&
                    pixel_y>=16'd128 && pixel_y<16'd130);
    wire in_pill=pixel_x>=16'd208 && pixel_x<16'd432 &&
                 pixel_y>=16'd284 && pixel_y<16'd348;
    wire in_title_y=pixel_y>=16'd68 && pixel_y<16'd96;
    wire in_wave_title=pixel_x>=16'd256 && pixel_x<16'd384;
    wire in_spectrum_title=pixel_x>=16'd192 && pixel_x<16'd448;
    wire in_han_y=pixel_y>=16'd172 && pixel_y<16'd236;
    wire han0=pixel_x>=16'd208 && pixel_x<16'd272;
    wire han1=pixel_x>=16'd288 && pixel_x<16'd352;
    wire han2=pixel_x>=16'd368 && pixel_x<16'd432;
    wire in_tone=pixel_x>=16'd224 && pixel_x<16'd416 &&
                 pixel_y>=16'd300 && pixel_y<16'd328;
    // Only low coordinate bits are needed inside the bounded cells.
    wire [4:0] title_dx=pixel_x[4:0];
    wire [4:0] title_dy=pixel_y[4:0]-5'd4;
    wire [5:0] han_dy=pixel_y[5:0]-6'd44;
    wire [5:0] han_dx0=pixel_x[5:0]-6'd16;
    wire [5:0] han_dx1=pixel_x[5:0]-6'd32;
    wire [5:0] han_dx2=pixel_x[5:0]-6'd48;
    wire [4:0] tone_dx=pixel_x[4:0];
    wire [4:0] tone_dy=pixel_y[4:0]-5'd12;
    wire [2:0] wave_slot=pixel_x[7:5]; // x256 has slot0
    wire [2:0] spectrum_slot=pixel_x[7:5]-3'd6; // x192 has slot0
    wire [2:0] tone_slot=pixel_x[7:5]-3'd7; // x224 has slot0

    // S1: classify geometry, bounded power-of-two coordinates and character.
    reg s1_valid,s1_spectrum,s1_tone;
    reg [1:0] s1_base,s1_kind,s1_han;
    reg [6:0] s1_ascii;
    reg [3:0] s1_row,s1_col;
    // S2: one static glyph ROW, rather than a wide registered glyph bitmap.
    reg s2_valid,s2_spectrum,s2_tone;
    reg [1:0] s2_base,s2_kind;
    reg [15:0] s2_glyph_row;
    reg [3:0] s2_col;
    // S3: one 16:1 glyph-bit selection, separated from the font lookup.
    reg s3_valid,s3_spectrum,s3_tone,s3_dot;
    reg [1:0] s3_base,s3_kind;
    // S4: registered color; S5: final RGB alignment capture.
    reg [23:0] s4_color;
    reg [23:0] base_color,text_color;
    always @* begin
        case (s3_base)
            2'd1:base_color=24'h131f33;
            2'd2:base_color=s3_spectrum ? 24'ha78bfa : 24'h22d3ee;
            2'd3:base_color=s3_tone ? 24'h17463a : 24'h243a5e;
            default:base_color=24'h0b1220;
        endcase
        text_color=(s3_kind==2'd2) ? 24'hffd166 : 24'hf1f5f9;
    end
    always @(posedge pixel_clk or negedge rst_n) begin
        if (!rst_n) begin
            s1_valid<=0; s1_spectrum<=0; s1_tone<=0;
            s1_base<=0; s1_kind<=0; s1_han<=0; s1_ascii<=0;
            s1_row<=0; s1_col<=0;
            s2_valid<=0; s2_spectrum<=0; s2_tone<=0;
            s2_base<=0; s2_kind<=0; s2_glyph_row<=0; s2_col<=0;
            s3_valid<=0; s3_spectrum<=0; s3_tone<=0; s3_dot<=0;
            s3_base<=0; s3_kind<=0; s4_color<=0;
            rgb_r<=0; rgb_g<=0; rgb_b<=0;
        end else begin
            s1_valid<=active_pixel;
            s1_spectrum<=page_is_spectrum; s1_tone<=selected_timbre;
            s1_base<=in_accent ? 2'd2 : (in_pill ? 2'd3 :
                                           (in_card ? 2'd1 : 2'd0));
            s1_kind<=0; s1_ascii<=7'd32; s1_han<=0;
            s1_row<=0; s1_col<=0;
            // Regions do not overlap, so these are parallel decodes.
            if (in_title_y && (page_is_spectrum ? in_spectrum_title : in_wave_title)) begin
                s1_kind<=1;
                s1_ascii<=title_character(page_is_spectrum,
                                         page_is_spectrum ? spectrum_slot : wave_slot);
                s1_row<={1'b0,title_dy[4:2]};
                s1_col<={1'b0,title_dx[4:2]};
            end
            if (in_han_y && (han0 || han1 || han2)) begin
                s1_kind<=2;
                s1_han<=han0 ? 2'd0 : (han1 ? 2'd1 : 2'd2);
                s1_row<=han_dy[5:2];
                s1_col<=han0 ? han_dx0[5:2] :
                            (han1 ? han_dx1[5:2] : han_dx2[5:2]);
            end
            if (in_tone) begin
                s1_kind<=3; s1_ascii<=tone_character(tone_slot,selected_timbre);
                s1_row<={1'b0,tone_dy[4:2]}; s1_col<={1'b0,tone_dx[4:2]};
            end

            s2_valid<=s1_valid; s2_spectrum<=s1_spectrum; s2_tone<=s1_tone;
            s2_base<=s1_base; s2_kind<=s1_kind; s2_col<=s1_col;
            if (s1_kind==2'd2) s2_glyph_row<=han_row(s1_han,s1_row);
            else if (s1_kind!=0) s2_glyph_row<=ascii_row(s1_ascii,s1_row[2:0]);
            else s2_glyph_row<=0;

            s3_valid<=s2_valid; s3_spectrum<=s2_spectrum; s3_tone<=s2_tone;
            s3_base<=s2_base; s3_kind<=s2_kind;
            s3_dot<=s2_glyph_row[4'd15-s2_col];

            s4_color<=s3_valid ? (s3_dot ? text_color : base_color) : 24'd0;
            {rgb_r,rgb_g,rgb_b}<=s4_color;
        end
    end
endmodule
