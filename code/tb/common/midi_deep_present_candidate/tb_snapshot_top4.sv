`timescale 1ns/1ps
module tb_snapshot_top4;
 logic clk=0,rst_n=0,request_valid=0,result_ready=0;always #10 clk=~clk;
 logic[31:0]request_mask;logic[4:0]request_rr;
 wire request_ready,result_valid;wire[3:0]winner_valid;wire[19:0]winner_indices;
 control_snapshot_top4 dut(.*);
 integer fd,scan,rr,ordinal,expected_ordinal=0,checks=0;
 logic[31:0]mask;logic[3:0]expected_valid;logic[19:0]expected_indices;
 string path;
 task automatic check(input bit ok,input string reason);begin checks++;if(!ok)$fatal(1,"top4 oracle %0d %s",expected_ordinal,reason);end endtask
 initial begin
  if(!$value$plusargs("VECTORS=%s",path))$fatal(1,"missing vectors");
  fd=$fopen(path,"r");if(!fd)$fatal(1,"missing vectors file");
  repeat(3)@(negedge clk);rst_n=1;
  while(!$feof(fd))begin
   scan=$fscanf(fd,"%d %h %d %h %h\n",ordinal,mask,rr,expected_valid,expected_indices);
   if(scan==-1&&$feof(fd))begin end
   else begin
    if(scan!=5)$fatal(1,"bad vector count");check(ordinal==expected_ordinal,"vector order");
    @(negedge clk);check(request_ready,"request ready");request_mask=mask;request_rr=5'(rr);request_valid=1;
    @(posedge clk);#1;check(!result_valid,"E capture no premature result");
    @(negedge clk);request_valid=0;request_mask=~mask;request_rr=5'(rr+9);
    @(posedge clk);#1;check(!result_valid,"E+1 no premature result");
    @(posedge clk);#1;check(result_valid&&winner_valid===expected_valid&&winner_indices===expected_indices,"E+2 exact all four RR winners");
    repeat(ordinal%3)begin @(posedge clk);#1;check(result_valid&&winner_valid===expected_valid&&winner_indices===expected_indices,"held output stable");end
    @(negedge clk);result_ready=1;@(negedge clk);result_ready=0;expected_ordinal++;
   end
  end
  check(expected_ordinal==18592,"vacuous or truncated count");
  $display("PASS snapshot top4 vectors=%0d checks=%0d",expected_ordinal,checks);$finish;
 end
 initial begin #100000000;$fatal(1,"top4 timeout");end
endmodule
