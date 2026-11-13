// R17 decoration only. No frame/audio state, RAM writes or new clocks.
// Input token -> position -> ASCII ROM -> glyph ROM -> RGB -> outputs:
// exactly FIVE captured pixel_clk edges, inclusive of first input capture.
// rst_n asynchronously clears all tokens; release in the caller's pixel domain.
// Font:5x7, scale2,12x16 cell. Full32/16-bit coordinates never wrap into labels.
module analysis_graph_overlay(
 input wire pixel_clk,rst_n,
 input wire [15:0] pixel_x,pixel_y,
 input wire data_enable,input wire [1:0] page,
 output reg graph_mask,output reg [23:0] graph_rgb,
 output reg grid_mask,output reg [23:0] grid_rgb
);
 localparam [23:0] TEXT_RGB=24'hd4e2ec,UNIT_RGB=24'haac4d5,
  TITLE_RGB=24'he1edf5,AXIS_RGB=24'h7294aa,
  MINOR_RGB=24'h102330,MAJOR_RGB=24'h263e50,ZERO_RGB=24'h34566a;
 wire wave_page=page==2;
 wire active=data_enable && (page==2 || page==3) && pixel_x<640 && pixel_y<480;
 // All boxes are disjoint. OR reduction selects coordinates, not a priority
 // chain over font bits. No division/sqrt/log or column reduction in this stage.
 function automatic [16:0] text_box(input [15:0] x,y,left,top,width,
                                    input [3:0] id);
  reg [15:0] dx,dy;
  begin
   dx=x-left;dy=y-top;text_box=0;
   if(x>=left && x<left+width && y>=top && y<top+16)
    text_box={1'b1,id,dx[7:0],dy[3:0]};
  end
 endfunction
 wire [16:0] text_position=
  text_box(pixel_x,pixel_y,64,24,wave_page?168:144,1) |
  text_box(pixel_x,pixel_y,480,24,96,2) |
  text_box(pixel_x,pixel_y,wave_page?266:236,374,wave_page?108:168,3) |
  text_box(pixel_x,pixel_y,wave_page?0:48,56,wave_page?60:12,4) |
  text_box(pixel_x,pixel_y,wave_page?12:24,wave_page?119:120,wave_page?48:36,5) |
  text_box(pixel_x,pixel_y,wave_page?48:24,wave_page?183:184,wave_page?12:36,6) |
  text_box(pixel_x,pixel_y,wave_page?12:24,wave_page?247:248,wave_page?48:36,7) |
  text_box(pixel_x,pixel_y,wave_page?0:24,wave_page?311:312,wave_page?60:36,8) |
  text_box(pixel_x,pixel_y,58,336,12,9) |
  text_box(pixel_x,pixel_y,168,336,48,10) |
  text_box(pixel_x,pixel_y,296,336,48,11) |
  text_box(pixel_x,pixel_y,424,336,48,12) |
  text_box(pixel_x,pixel_y,552,336,48,13);
 wire x_tick=pixel_x==64 || pixel_x==192 || pixel_x==320 || pixel_x==448 || pixel_x==576;
 wire y_tick=wave_page ? (pixel_y==64 || pixel_y==127 || pixel_y==191 || pixel_y==255 || pixel_y==319) :
                            (pixel_y==64 || pixel_y==128 || pixel_y==192 || pixel_y==256 || pixel_y==320);
 wire border=((pixel_x==64 || pixel_x==576) && pixel_y>=64 && pixel_y<=320) ||
             ((pixel_y==64 || pixel_y==320) && pixel_x>=64 && pixel_x<=576);
 wire ticks=(x_tick && pixel_y>=321 && pixel_y<=325) ||
            (y_tick && pixel_x>=60 && pixel_x<=63);
 wire interior=pixel_x>64 && pixel_x<576 && pixel_y>64 && pixel_y<320;
 wire major_x=pixel_x==192 || pixel_x==320 || pixel_x==448;
 wire major_y=wave_page ? (pixel_y==127 || pixel_y==191 || pixel_y==255 || pixel_y==319) :
                             (pixel_y==128 || pixel_y==192 || pixel_y==256);
 wire minor_y=wave_page ? (pixel_y==95 || pixel_y==159 || pixel_y==223 || pixel_y==287) :
                             (pixel_y==96 || pixel_y==160 || pixel_y==224 || pixel_y==288);
 wire any_grid=(pixel_x[4:0]==0) || major_y || minor_y;
 wire grid_major=major_x || major_y;
 wire grid_zero=wave_page && pixel_y==191;

 // Capture1: geometry and the original DE/page token.
 reg s1_active,s1_wave,s1_text,s1_axis,s1_grid,s1_major,s1_zero;
 reg [3:0] s1_id,s1_dy;
 reg [7:0] s1_dx;
 // Capture2: bounded8-bit constant cell decode + ASCII ROM.
 reg s2_active,s2_text,s2_axis,s2_grid,s2_major,s2_zero;
 reg [7:0] s2_char;
 reg [2:0] s2_col,s2_row;
 reg [23:0] s2_text_rgb;
 wire [4:0] cell_index=s1_dx/8'd12;
 wire [3:0] cell_remainder=s1_dx-cell_index*8'd12;
 function automatic [7:0] character_rom(input wave,input [3:0] id,input [4:0] idx);
  begin
   character_rom=8'h20;
   case({wave,id,idx})
    10'h020:character_rom=8'h4c;
    10'h021:character_rom=8'h45;
    10'h022:character_rom=8'h56;
    10'h023:character_rom=8'h45;
    10'h024:character_rom=8'h4c;
    10'h025:character_rom=8'h20;
    10'h026:character_rom=8'h28;
    10'h027:character_rom=8'h64;
    10'h028:character_rom=8'h42;
    10'h029:character_rom=8'h46;
    10'h02a:character_rom=8'h53;
    10'h02b:character_rom=8'h29;
    10'h220:character_rom=8'h41;
    10'h221:character_rom=8'h4d;
    10'h222:character_rom=8'h50;
    10'h223:character_rom=8'h4c;
    10'h224:character_rom=8'h49;
    10'h225:character_rom=8'h54;
    10'h226:character_rom=8'h55;
    10'h227:character_rom=8'h44;
    10'h228:character_rom=8'h45;
    10'h229:character_rom=8'h20;
    10'h22a:character_rom=8'h28;
    10'h22b:character_rom=8'h46;
    10'h22c:character_rom=8'h53;
    10'h22d:character_rom=8'h29;
    10'h040:character_rom=8'h53;
    10'h041:character_rom=8'h50;
    10'h042:character_rom=8'h45;
    10'h043:character_rom=8'h43;
    10'h044:character_rom=8'h54;
    10'h045:character_rom=8'h52;
    10'h046:character_rom=8'h55;
    10'h047:character_rom=8'h4d;
    10'h240:character_rom=8'h57;
    10'h241:character_rom=8'h41;
    10'h242:character_rom=8'h56;
    10'h243:character_rom=8'h45;
    10'h244:character_rom=8'h46;
    10'h245:character_rom=8'h4f;
    10'h246:character_rom=8'h52;
    10'h247:character_rom=8'h4d;
    10'h060:character_rom=8'h46;
    10'h061:character_rom=8'h52;
    10'h062:character_rom=8'h45;
    10'h063:character_rom=8'h51;
    10'h064:character_rom=8'h55;
    10'h065:character_rom=8'h45;
    10'h066:character_rom=8'h4e;
    10'h067:character_rom=8'h43;
    10'h068:character_rom=8'h59;
    10'h069:character_rom=8'h20;
    10'h06a:character_rom=8'h28;
    10'h06b:character_rom=8'h48;
    10'h06c:character_rom=8'h7a;
    10'h06d:character_rom=8'h29;
    10'h260:character_rom=8'h54;
    10'h261:character_rom=8'h49;
    10'h262:character_rom=8'h4d;
    10'h263:character_rom=8'h45;
    10'h264:character_rom=8'h20;
    10'h265:character_rom=8'h28;
    10'h266:character_rom=8'h6d;
    10'h267:character_rom=8'h73;
    10'h268:character_rom=8'h29;
    10'h080:character_rom=8'h30;
    10'h280:character_rom=8'h2b;
    10'h281:character_rom=8'h30;
    10'h282:character_rom=8'h2e;
    10'h283:character_rom=8'h39;
    10'h284:character_rom=8'h39;
    10'h0a0:character_rom=8'h2d;
    10'h0a1:character_rom=8'h31;
    10'h0a2:character_rom=8'h38;
    10'h2a0:character_rom=8'h2b;
    10'h2a1:character_rom=8'h2e;
    10'h2a2:character_rom=8'h35;
    10'h2a3:character_rom=8'h30;
    10'h0c0:character_rom=8'h2d;
    10'h0c1:character_rom=8'h33;
    10'h0c2:character_rom=8'h36;
    10'h2c0:character_rom=8'h30;
    10'h0e0:character_rom=8'h2d;
    10'h0e1:character_rom=8'h35;
    10'h0e2:character_rom=8'h34;
    10'h2e0:character_rom=8'h2d;
    10'h2e1:character_rom=8'h2e;
    10'h2e2:character_rom=8'h35;
    10'h2e3:character_rom=8'h30;
    10'h100:character_rom=8'h2d;
    10'h101:character_rom=8'h37;
    10'h102:character_rom=8'h32;
    10'h300:character_rom=8'h2d;
    10'h301:character_rom=8'h31;
    10'h302:character_rom=8'h2e;
    10'h303:character_rom=8'h30;
    10'h304:character_rom=8'h30;
    10'h120:character_rom=8'h30;
    10'h320:character_rom=8'h30;
    10'h140:character_rom=8'h31;
    10'h141:character_rom=8'h35;
    10'h142:character_rom=8'h30;
    10'h143:character_rom=8'h30;
    10'h340:character_rom=8'h31;
    10'h341:character_rom=8'h30;
    10'h342:character_rom=8'h2e;
    10'h343:character_rom=8'h37;
    10'h160:character_rom=8'h33;
    10'h161:character_rom=8'h30;
    10'h162:character_rom=8'h30;
    10'h163:character_rom=8'h30;
    10'h360:character_rom=8'h32;
    10'h361:character_rom=8'h31;
    10'h362:character_rom=8'h2e;
    10'h363:character_rom=8'h33;
    10'h180:character_rom=8'h34;
    10'h181:character_rom=8'h35;
    10'h182:character_rom=8'h30;
    10'h183:character_rom=8'h30;
    10'h380:character_rom=8'h33;
    10'h381:character_rom=8'h32;
    10'h382:character_rom=8'h2e;
    10'h383:character_rom=8'h30;
    10'h1a0:character_rom=8'h36;
    10'h1a1:character_rom=8'h30;
    10'h1a2:character_rom=8'h30;
    10'h1a3:character_rom=8'h30;
    10'h3a0:character_rom=8'h34;
    10'h3a1:character_rom=8'h32;
    10'h3a2:character_rom=8'h2e;
    10'h3a3:character_rom=8'h37;
    default:character_rom=8'h20;
   endcase
  end
 endfunction
 function automatic [4:0] glyph_row(input [7:0] char_code,input [2:0] row);
  reg [34:0] bits;
  begin
   bits=0;
   case(char_code)
    8'h20:bits=35'b00000000000000000000000000000000000;
    8'h28:bits=35'b00010001000100001000010000010000010;
    8'h29:bits=35'b01000001000001000010000100010001000;
    8'h2b:bits=35'b00000001000010011111001000010000000;
    8'h2d:bits=35'b00000000000000011111000000000000000;
    8'h2e:bits=35'b00000000000000000000000000010000100;
    8'h30:bits=35'b01110100011001110101110011000101110;
    8'h31:bits=35'b00100011000010000100001000010001110;
    8'h32:bits=35'b01110100010000100010001000100011111;
    8'h33:bits=35'b11110000010000101110000010000111110;
    8'h34:bits=35'b00010001100101010010111110001000010;
    8'h35:bits=35'b11111100001000011110000010000111110;
    8'h36:bits=35'b01110100001000011110100011000101110;
    8'h37:bits=35'b11111000010001000100010000100001000;
    8'h38:bits=35'b01110100011000101110100011000101110;
    8'h39:bits=35'b01110100011000101111000010000101110;
    8'h41:bits=35'b01110100011000111111100011000110001;
    8'h42:bits=35'b11110100011000111110100011000111110;
    8'h43:bits=35'b01111100001000010000100001000001111;
    8'h44:bits=35'b11110100011000110001100011000111110;
    8'h45:bits=35'b11111100001000011110100001000011111;
    8'h46:bits=35'b11111100001000011110100001000010000;
    8'h48:bits=35'b10001100011000111111100011000110001;
    8'h49:bits=35'b01110001000010000100001000010001110;
    8'h4c:bits=35'b10000100001000010000100001000011111;
    8'h4d:bits=35'b10001110111010110101100011000110001;
    8'h4e:bits=35'b10001110011010110011100011000110001;
    8'h4f:bits=35'b01110100011000110001100011000101110;
    8'h50:bits=35'b11110100011000111110100001000010000;
    8'h51:bits=35'b01110100011000110001101011001001101;
    8'h52:bits=35'b11110100011000111110101001001010001;
    8'h53:bits=35'b01111100001000001110000010000111110;
    8'h54:bits=35'b11111001000010000100001000010000100;
    8'h55:bits=35'b10001100011000110001100011000101110;
    8'h56:bits=35'b10001100011000110001100010101000100;
    8'h57:bits=35'b10001100011000110101101011010101010;
    8'h59:bits=35'b10001100010101000100001000010000100;
    8'h64:bits=35'b00001000010110110011100011000101111;
    8'h6d:bits=35'b00000000001101010101101011010110101;
    8'h73:bits=35'b00000000000111110000011100000111110;
    8'h7a:bits=35'b00000000001111100010001000100011111;
    default:bits=0;
   endcase
   case(row)
    0:glyph_row=bits[34:30];1:glyph_row=bits[29:25];
    2:glyph_row=bits[24:20];3:glyph_row=bits[19:15];
    4:glyph_row=bits[14:10];5:glyph_row=bits[9:5];
    6:glyph_row=bits[4:0];default:glyph_row=0;
   endcase
  end
 endfunction
 // Capture3: registered glyph row, with every non-font token aligned.
 reg s3_active,s3_text,s3_axis,s3_grid,s3_major,s3_zero;
 reg [4:0] s3_bits;
 reg [2:0] s3_col;
 reg [23:0] s3_text_rgb;
 // Capture4: single-bit glyph selection, masks and colour.
 reg s4_graph,s4_grid;
 reg [23:0] s4_graph_rgb,s4_grid_rgb;
 wire glyph_pixel=s3_text && s3_col<5 && s3_bits[4-s3_col];
 always @(posedge pixel_clk or negedge rst_n)begin
  if(!rst_n)begin
   s1_active<=0;s1_wave<=0;s1_text<=0;s1_axis<=0;s1_grid<=0;s1_major<=0;s1_zero<=0;
   s1_id<=0;s1_dx<=0;s1_dy<=0;
   s2_active<=0;s2_text<=0;s2_axis<=0;s2_grid<=0;s2_major<=0;s2_zero<=0;
   s2_char<=0;s2_col<=0;s2_row<=0;s2_text_rgb<=0;
   s3_active<=0;s3_text<=0;s3_axis<=0;s3_grid<=0;s3_major<=0;s3_zero<=0;
   s3_bits<=0;s3_col<=0;s3_text_rgb<=0;
   s4_graph<=0;s4_grid<=0;s4_graph_rgb<=0;s4_grid_rgb<=0;
   graph_mask<=0;graph_rgb<=0;grid_mask<=0;grid_rgb<=0;
  end else begin
   s1_active<=active;s1_wave<=wave_page;
   s1_text<=text_position[16];s1_id<=text_position[15:12];
   s1_dx<=text_position[11:4];s1_dy<=text_position[3:0];
   s1_axis<=border || ticks;s1_grid<=interior && any_grid;
   s1_major<=grid_major;s1_zero<=grid_zero;
   s2_active<=s1_active;s2_axis<=s1_axis;s2_grid<=s1_grid;s2_major<=s1_major;s2_zero<=s1_zero;
   s2_text<=s1_text && cell_remainder>=1 && cell_remainder<=10 && s1_dy>=1 && s1_dy<=14;
   s2_char<=character_rom(s1_wave,s1_id,cell_index);
   s2_col<=(cell_remainder-1)>>1;s2_row<=(s1_dy-1)>>1;
   s2_text_rgb<=s1_id==2 ? TITLE_RGB : (s1_id==1 || s1_id==3) ? UNIT_RGB : TEXT_RGB;
   s3_active<=s2_active;s3_axis<=s2_axis;s3_grid<=s2_grid;s3_major<=s2_major;s3_zero<=s2_zero;
   s3_text<=s2_text;s3_bits<=glyph_row(s2_char,s2_row);s3_col<=s2_col;s3_text_rgb<=s2_text_rgb;
   s4_graph<=s3_active && (s3_axis || glyph_pixel);
   s4_grid<=s3_active && s3_grid;
   s4_graph_rgb<=s3_active && (s3_axis || glyph_pixel) ? (s3_axis ? AXIS_RGB : s3_text_rgb) : 24'b0;
   s4_grid_rgb<=s3_active && s3_grid ? (s3_zero ? ZERO_RGB : s3_major ? MAJOR_RGB : MINOR_RGB) : 24'b0;
   // Capture5: public outputs; never gate with the current input DE/page.
   graph_mask<=s4_graph;graph_rgb<=s4_graph_rgb;
   grid_mask<=s4_grid;grid_rgb<=s4_grid_rgb;
  end
 end
endmodule
