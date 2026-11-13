// Observation-only; all captures are PRE_NBA on clk. No audio feedback.
module lean_trace_capture #(parameter integer CLK_HZ=40000000)(
 input wire clk,rst_n,
 input wire raw_rx_valid,raw_frame_err,input wire [7:0] raw_rx_data,
 input wire parser_valid,parser_ready,input wire [63:0] parser_data,
 input wire shared_valid,shared_ready,input wire [63:0] shared_data,
 input wire apply_valid,input wire [63:0] apply_data,input wire [31:0] apply_seq,
 input wire [3:0] apply_kind,apply_mask,
 input wire [127:0] generations,input wire [31:0] notes,
 input wire [15:0] sources,channels,
 input wire [3:0] occupied,key_down,deferred,sustain_releasing,router_releasing,
 input wire [3:0] note_on,note_off,retire,bank_phase,advance_mask,
 input wire [11:0] adsr_states,
 output wire [7:0] capture_valid,output wire [1023:0] capture_payload
);
 reg [31:0] second_count;
 wire periodic=second_count==CLK_HZ-1;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)second_count<=0;
  else if(periodic)second_count<=0;
  else second_count<=second_count+1'b1;
 assign capture_valid[0]=rst_n && raw_rx_valid;
 assign capture_valid[1]=rst_n && parser_valid && parser_ready;
 assign capture_valid[2]=rst_n && shared_valid && shared_ready;
 assign capture_valid[3]=rst_n && apply_valid;
 assign capture_payload[0+:128]={119'b0,raw_frame_err,raw_rx_data};
 assign capture_payload[128+:128]={64'b0,parser_data};
 assign capture_payload[256+:128]={64'b0,shared_data};
 assign capture_payload[384+:128]={24'b0,apply_mask,apply_kind,apply_seq,apply_data};
 for(genvar lane=0;lane<4;lane=lane+1)begin:g_lane
  reg [31:0] advance_count;
  reg [52:0] previous_state;
  reg [2:0] previous_adsr_state;
  wire [127:0] payload;
  assign payload={33'b0,adsr_states[lane*3+:3],advance_count,bank_phase,retire[lane],note_off[lane],note_on[lane],
   router_releasing[lane],sustain_releasing[lane],deferred[lane],key_down[lane],occupied[lane],
   channels[lane*4+:4],sources[lane*4+:4],notes[lane*8+:8],generations[lane*32+:32]};
  // R05 native hold failures terminate at previous_state. Keep this
  // consumer branch separate from the actual payload and audio signals.
  (* syn_keep=1, syn_dont_touch=1 *) wire [52:0] previous_state_hold_l0;
  (* syn_keep=1, syn_dont_touch=1 *) wire [52:0] previous_state_hold_l1;
  for(genvar hb=0;hb<53;hb=hb+1)begin:g_previous_state_hold
   (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_hold_0(
    .I0(payload[hb]),.F(previous_state_hold_l0[hb]));
   (* syn_keep=1, syn_dont_touch=1 *) LUT1 #(.INIT(2'h2)) u_hold_1(
    .I0(previous_state_hold_l0[hb]),.F(previous_state_hold_l1[hb]));
  end
  assign capture_payload[(lane+4)*128+:128]=payload;
  assign capture_valid[lane+4]=rst_n && (periodic || payload[52:0]!=previous_state ||
   payload[94:92]!=previous_adsr_state ||
   note_on[lane] || note_off[lane] || retire[lane]);
  always @(posedge clk or negedge rst_n)begin
   if(!rst_n)begin advance_count<=0;previous_state<=0;previous_adsr_state<=0;end
   else begin
    previous_state<=previous_state_hold_l1;
    previous_adsr_state<=payload[94:92];
    if(advance_mask[lane] && advance_count!=32'hffffffff)advance_count<=advance_count+1'b1;
   end
  end
 end
endmodule
