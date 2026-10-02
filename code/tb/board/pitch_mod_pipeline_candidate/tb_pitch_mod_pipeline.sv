// M2 independent latency scoreboard; accepted original is a cycle oracle.
`timescale 1ns/1ps
module tb_pitch_mod_pipeline #(
 parameter logic[9:0] DEPTH=10'd512,
 parameter logic[31:0] INC=32'd447392,
 parameter integer RUN_VECTORS=1
);
 logic sys_clk=0;always #10 sys_clk=~sys_clk;
 logic sys_rst_n=0,sample_enable=0,note_on=0;
 logic signed[11:0]bend=0;logic[11:0]modulation=0;
 logic[4:0]pitch_range=2;logic[31:0]base_fcw=0;
 wire[31:0]fcw_out,reference_fcw;wire fcw_valid,reference_valid;
 pitch_mod_fcw_pipeline #(.MOD_DEPTH_MAX_Q10(DEPTH),.LFO_INC(INC))dut(.*);
 pitch_mod_fcw #(.MOD_DEPTH_MAX_Q10(DEPTH),.LFO_INC(INC))reference(
  .sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.sample_enable(sample_enable),.note_on(note_on),
  .bend(bend),.modulation(modulation),.pitch_range(pitch_range),.base_fcw(base_fcw),
  .fcw_out(reference_fcw),.fcw_valid(reference_valid));
 logic[6:0]score_valid=0;logic[31:0]score_value[0:6];
 logic golden_mode=0;logic[31:0]golden_expected=0;
 logic[31:0]previous_output=0;
 integer checks=0,outputs=0,launched=0,cancelled=0,vectors=0,cycles=0,errors=0;
 integer f,r;integer v_base,v_bend,v_range,v_mod,v_on,v_expected;
 logic[31:0]random_state=32'h519973ab;
 string vectors_path;
 task automatic check(input logic condition,input string label);
  checks++;
  if(condition!==1'b1)begin
   errors++;if(errors<12)$display("FAIL %s cycle=%0d vectors=%0d out=%h valid=%b",label,cycles,vectors,fcw_out,fcw_valid);
  end
 endtask
 always @(posedge sys_clk)begin
  #2;cycles++;
  if(!sys_rst_n)begin
   for(integer j=0;j<7;j++)begin
    if(j<6 && score_valid[j])cancelled++;
    score_valid[j]=0;score_value[j]=0;
   end
   previous_output=0;
   check(fcw_out===0 && fcw_valid===0,"reset clears all output/valid");
  end else begin
   for(integer j=6;j>0;j--)begin score_valid[j]=score_valid[j-1];score_value[j]=score_value[j-1];end
   score_valid[0]=sample_enable;
   if(sample_enable)begin
    launched++;score_value[0]=reference_fcw;
    if(golden_mode)check(reference_fcw===golden_expected,"accepted original matches Python vector");
   end
   check(reference_valid===sample_enable,"original oracle capture valid");
   check(dut.lfo_phase===reference.lfo_phase,"LFO advances once per enabled input, not once per pipeline stage");
   check(fcw_valid===score_valid[6],"pipeline valid exactlyE+6 with bubbles");
   if(fcw_valid)begin outputs++;check(fcw_out===score_value[6],"exact delayed reference result/parameter alignment");end
   else check(fcw_out===previous_output,"invalid bubble holds result");
   previous_output=fcw_out;
  end
 end
 task automatic drive(input logic enable,input logic on,input logic[31:0]base,
                       input logic signed[11:0]bd,input logic[4:0]range_value,input logic[11:0]md);
  @(negedge sys_clk);sample_enable=enable;note_on=on;base_fcw=base;bend=bd;pitch_range=range_value;modulation=md;
 endtask
 task automatic reset_all;
  @(negedge sys_clk);sys_rst_n=0;sample_enable=0;note_on=0;
  #1;check(fcw_out===0 && fcw_valid===0,"async reset between clock edges");
  repeat(3)@(negedge sys_clk);sys_rst_n=1;
 endtask
 initial begin
  reset_all();
  if(RUN_VECTORS)begin
   if(!$value$plusargs("VECTORS=%s",vectors_path))$fatal(1,"missing vectors");
   f=$fopen(vectors_path,"r");if(!f)$fatal(1,"cannot read vectors");golden_mode=1;
   while(!$feof(f))begin
    r=$fscanf(f,"%h %h %h %h %d %h\n",v_base,v_bend,v_range,v_mod,v_on,v_expected);
    if(r==6)begin
     if(^{v_base,v_bend,v_range,v_mod,v_on,v_expected}===1'bx)$fatal(1,"unknown vector");
     drive(1,v_on[0],v_base[31:0],v_bend[11:0],v_range[4:0],v_mod[11:0]);golden_expected=v_expected[31:0];vectors++;
    end else if(r!=-1)$fatal(1,"malformed vector");
   end
   $fclose(f);drive(0,0,0,0,0,0);repeat(8)@(negedge sys_clk);
   check(vectors==62279,"all Python vectors exercised");golden_mode=0;
  end
  // Random controls change on every sys clock, including while bubbles hold.
  // New NoteOn does not cancel previously accepted results: surrounding
  // generation scheduler must discard them by ID when a voice is replaced.
  for(integer n=0;n<30000;n++)begin
   random_state=random_state^(random_state<<13);random_state=random_state^(random_state>>17);random_state=random_state^(random_state<<5);
   if(n%997==0)reset_all();
   drive(random_state[1:0]!=0,random_state[5:2]==0,random_state[30:0]%1122405053,
          random_state[15:4],5'(random_state[23:16]%25),random_state[27:16]);
  end
  drive(0,0,0,0,0,0);repeat(8)@(negedge sys_clk);
  // Sparse actual48k cadence; no held snapshot_valid drives input enable.
  for(integer n=0;n<128;n++)begin
   drive(1,n%11==0,32'd39370534,12'(n*31-2048),5'd24,12'(n*31));
   drive(0,0,32'd999999,12'sd0,5'd0,12'd0);repeat(n[0]?1040:1039)@(negedge sys_clk);
  end
  // NoteOn without sample must reset LFO and leave pipe/output bookkeeping alone.
  drive(0,1,39370534,2047,2,4095);drive(0,0,39370534,2047,2,4095);
  drive(1,0,39370534,2047,2,4095);drive(1,1,39370534,-2048,24,4095);
  drive(0,0,0,0,0,0);repeat(9)@(negedge sys_clk);
  // Asynchronous cancellation at each internal latency stage.
  for(integer j=0;j<7;j++)begin
   drive(1,1,1122405052,2047,24,4095);drive(0,0,0,0,0,0);
   repeat(j)@(negedge sys_clk);#3;sys_rst_n=0;#1;
   check(fcw_out===0 && fcw_valid===0,"midflight async reset");
   repeat(2)@(negedge sys_clk);sys_rst_n=1;
   drive(1,1,39370534,0,2,0);drive(0,0,0,0,0,0);repeat(8)@(negedge sys_clk);
  end
  check(outputs+cancelled==launched,"accepted tokens produce one output or are flushed by reset");
  check(checks>(RUN_VECTORS ? 700000 : 550000) && outputs>21000,"not empty/test truncated");
  if(errors)$fatal(1,"pipeline FAIL errors=%0d checks=%0d",errors,checks);
  $display("PASS pitchmod pipeline DEPTH=%0d INC=%0d vectors=%0d checks=%0d launches=%0d outputs=%0d cancelled=%0d E+6",DEPTH,INC,vectors,checks,launched,outputs,cancelled);$finish;
 end
 initial begin #10000000;$fatal(1,"pipelineTB timeout");end
endmodule
