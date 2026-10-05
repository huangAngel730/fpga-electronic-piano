// Independent 32-slot round-robin snapshot selector. NOT a production parser.
// Three register boundaries: captured eligibility -> 4x8 local top-two ->
// global top-two/result. No live MIDI update, ready or old grant feeds selection.
// E request capture, E+1 groups, E+2 result_valid; min request spacing 4clk.
// Caller must revalidate snapshot epoch/candidate before freezing event payload.
module control_snapshot_selector (
 input logic clk,rst_n,cancel,request_valid,output wire request_ready,
 input logic[31:0]request_mask,input logic[4:0]request_rr,
 input logic[31:0]request_id,request_epoch,
 output wire result_valid,input logic result_ready,
 output logic first_valid,second_valid,output logic[4:0]first_index,second_index,
 output logic[31:0]result_id,result_epoch);
 localparam logic[1:0]IDLE=0,GROUPS=1,COMBINE=2,HOLD=3;
 logic[1:0]state;
 logic[31:0]higher_mask,lower_mask;
 logic[7:0]higher_group[0:3],lower_group[0:3];
 logic[31:0]higher_pack,lower_pack;
 logic[11:0]higher_pair,lower_pair;
 assign request_ready=rst_n&&!cancel&&state==IDLE;
 assign result_valid=rst_n&&!cancel&&state==HOLD;
 function automatic logic[7:0]local_pair(input logic[7:0]bits_in);
  logic[7:0]pair;
  begin
   pair=0;
   for(integer k=0;k<8;k++)if(bits_in[k])begin
    if(!pair[7])begin pair[7]=1;pair[5:3]=3'(k);end
    else if(!pair[6])begin pair[6]=1;pair[2:0]=3'(k);end
   end
   local_pair=pair;
  end
 endfunction
 function automatic logic[11:0]group_pair(input logic[31:0]packed_groups);
  logic[11:0]pair;logic[7:0]value;
  begin
   pair=0;value=0;
   for(integer g=0;g<4;g++)begin
    value=packed_groups[8*g+:8];
    if(value[7])begin
     if(!pair[11])begin
      pair[11]=1;pair[9:5]={2'(g),value[5:3]};
      if(value[6])begin pair[10]=1;pair[4:0]={2'(g),value[2:0]};end
     end else if(!pair[10])begin pair[10]=1;pair[4:0]={2'(g),value[5:3]};end
    end
   end
   group_pair=pair;
  end
 endfunction
 always_comb begin
  higher_pack=0;lower_pack=0;
  for(integer g=0;g<4;g++)begin
   higher_pack[8*g+:8]=higher_group[g];lower_pack[8*g+:8]=lower_group[g];
  end
  higher_pair=group_pair(higher_pack);lower_pair=group_pair(lower_pack);
 end
 always_ff @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=IDLE;higher_mask<=0;lower_mask<=0;
   result_id<=0;result_epoch<=0;first_valid<=0;second_valid<=0;first_index<=0;second_index<=0;
   for(integer g=0;g<4;g++)begin higher_group[g]<=0;lower_group[g]<=0;end
  end else if(cancel)begin
   state<=IDLE;first_valid<=0;second_valid<=0;first_index<=0;second_index<=0;
  end else case(state)
   IDLE:if(request_valid)begin
    for(integer k=0;k<32;k++)begin
     higher_mask[k]<=request_mask[k]&&(k>=request_rr);
     lower_mask[k]<=request_mask[k]&&(k<request_rr);
    end
    result_id<=request_id;result_epoch<=request_epoch;state<=GROUPS;
   end
   GROUPS:begin
    for(integer g=0;g<4;g++)begin
     higher_group[g]<=local_pair(higher_mask[8*g+:8]);
     lower_group[g]<=local_pair(lower_mask[8*g+:8]);
    end
    state<=COMBINE;
   end
   COMBINE:begin
    if(higher_pair[11])begin
     first_valid<=1;first_index<=higher_pair[9:5];
     second_valid<=higher_pair[10]||lower_pair[11];
     second_index<=higher_pair[10]?higher_pair[4:0]:(lower_pair[11]?lower_pair[9:5]:5'd0);
    end else begin
     first_valid<=lower_pair[11];first_index<=lower_pair[11]?lower_pair[9:5]:5'd0;
     second_valid<=lower_pair[10];second_index<=lower_pair[10]?lower_pair[4:0]:5'd0;
    end
    state<=HOLD;
   end
   HOLD:if(result_ready)state<=IDLE;
   default:state<=IDLE;
  endcase
 end
endmodule
