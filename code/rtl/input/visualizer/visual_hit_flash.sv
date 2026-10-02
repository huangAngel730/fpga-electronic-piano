// Per-pitch hit feedback: immediate activation, small frame-stepped decay.
// Local bottom pixels may change midframe; geometry still uses frame snapshots.
`timescale 1ns/1ps
module visual_hit_flash #(
    parameter integer BASE_NOTE=36, NOTE_COUNT=49, FLASH_FRAMES=4
)(
    input logic clk,rst_n,frame_start,enabled,clear,
    input logic hit_pulse,
    input logic [6:0] hit_note_number,
    output wire [127:0] flash_active,
    output wire [255:0] flash_level
);
    localparam integer COUNT_BITS=(FLASH_FRAMES<2) ? 1 : $clog2(FLASH_FRAMES+1);
    localparam integer BRIGHT_MIN=(3*FLASH_FRAMES)/4+1;
    localparam integer MEDIUM_MIN=(2*FLASH_FRAMES)/4+1;
    localparam integer LOW_MIN=(FLASH_FRAMES+3)/4;
    logic [COUNT_BITS-1:0] count_q[0:NOTE_COUNT-1];
    for(genvar n=0;n<NOTE_COUNT;n=n+1)begin:g_pitch
        assign flash_active[BASE_NOTE+n]=count_q[n]!=0;
        assign flash_level[2*(BASE_NOTE+n)+:2]=
            (count_q[n]>=BRIGHT_MIN) ? 2'd3 :
            (count_q[n]>=MEDIUM_MIN) ? 2'd2 :
            (count_q[n]>LOW_MIN) ? 2'd1 : 2'd0;
        always_ff @(posedge clk or negedge rst_n)begin
            if(!rst_n)count_q[n]<=0;
            else if(!enabled || clear)count_q[n]<=0;
            else if(hit_pulse && hit_note_number==7'(BASE_NOTE+n))
                count_q[n]<=COUNT_BITS'(FLASH_FRAMES);
            else if(frame_start && count_q[n]!=0)count_q[n]<=count_q[n]-1'b1;
        end
    end
    for(genvar note=0;note<128;note=note+1)begin:g_unused
        if(note<BASE_NOTE || note>=BASE_NOTE+NOTE_COUNT)begin:g_outside
            assign flash_active[note]=1'b0;
            assign flash_level[2*note+:2]=2'd0;
        end
    end
`ifndef SYNTHESIS
    initial if(FLASH_FRAMES<1 || FLASH_FRAMES>255 || BASE_NOTE<0 || NOTE_COUNT<1 || BASE_NOTE+NOTE_COUNT>128)
        $fatal(1,"invalid hit flash parameters");
`endif
endmodule
