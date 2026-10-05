// Isolated three-stage top-four RR selector. E capture, E+1 groups, E+2 result.
module control_snapshot_top4(
 input logic clk,rst_n,request_valid,output wire request_ready,
 input logic[31:0]request_mask,input logic[4:0]request_rr,
 output wire result_valid,input logic result_ready,
 output logic[3:0]winner_valid,output logic[19:0]winner_indices);
 localparam logic[1:0] IDLE=0,GROUP=1,MERGE=2,HOLD=3;
 logic[1:0]state;logic[31:0]high_mask,low_mask;
 logic[15:0]high_group[0:3],low_group[0:3];logic[63:0]high_pack,low_pack;
 logic[23:0]combined;
 assign request_ready=rst_n&&state==IDLE;
 assign result_valid=rst_n&&state==HOLD;
 function automatic logic[15:0]top4_local(input logic[7:0]bits_in);
  logic[15:0]p;integer count;
  begin p=0;count=0;for(integer k=0;k<8;k++)if(bits_in[k]&&count<4)begin
   p[count*3+:3]=3'(k);count=count+1;end
   p[14:12]=3'(count);top4_local=p;end
 endfunction
 always_comb begin
  high_pack=0;low_pack=0;
  for(integer g=0;g<4;g++)begin high_pack[16*g+:16]=high_group[g];low_pack[16*g+:16]=low_group[g];end
 end
 function automatic logic[23:0]merge_groups(input logic[63:0]hi,lo);
  logic[23:0]p;logic[15:0]v;integer count;
  begin p=0;v=0;count=0;
   for(integer half=0;half<2;half++)for(integer g=0;g<4;g++)begin
    v=half==0?hi[16*g+:16]:lo[16*g+:16];
    for(integer k=0;k<4;k++)if(k<v[14:12]&&count<4)begin
     p[20+count]=1;p[count*5+:5]={2'(g),v[k*3+:3]};count=count+1;end
   end
   merge_groups=p;
  end
 endfunction
 always_comb combined=merge_groups(high_pack,low_pack);
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin state<=IDLE;high_mask<=0;low_mask<=0;winner_valid<=0;winner_indices<=0;
   for(integer g=0;g<4;g++)begin high_group[g]<=0;low_group[g]<=0;end
  end else case(state)
   IDLE:if(request_valid)begin
    for(integer k=0;k<32;k++)begin high_mask[k]<=request_mask[k]&&(k>=request_rr);low_mask[k]<=request_mask[k]&&(k<request_rr);end
    state<=GROUP;
   end
   GROUP:begin for(integer g=0;g<4;g++)begin high_group[g]<=top4_local(high_mask[8*g+:8]);low_group[g]<=top4_local(low_mask[8*g+:8]);end state<=MERGE;end
   MERGE:begin winner_valid<=combined[23:20];winner_indices<=combined[19:0];state<=HOLD;end
   HOLD:if(result_ready)state<=IDLE;
   default:state<=IDLE;
  endcase
 end
endmodule
