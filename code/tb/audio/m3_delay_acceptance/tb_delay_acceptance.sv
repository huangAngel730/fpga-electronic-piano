// Independent cycle-vector acceptance, real delay_effect RTL only.
`timescale 1ns/1ps
module tb_delay_acceptance;
 parameter integer DEPTH=16;
 logic sys_clk=0;always #10 sys_clk=~sys_clk;
 logic sys_rst_n=0,sample_enable=0;
 logic signed [23:0] pcm_in=0;
 logic [15:0] delay_samples=0;
 logic [14:0] dry_gain=0,wet_gain=0,feedback=0;
 wire signed [23:0] pcm_out;
 wire pcm_valid;
 delay_effect #(.DEPTH(DEPTH))dut(.*);
 string vector_path="vectors.txt";
 integer fd,out_fd,total,count=0,valid_count=0,rc;
 integer r,en,pcm,delay_value,dry,wet,fb,valid_expected,pcm_expected;
 integer extra;
 initial begin
  if($value$plusargs("VECTORS=%s",vector_path))begin end
  fd=$fopen(vector_path,"r");if(!fd)$fatal(1,"missing vector file");
  rc=$fscanf(fd,"%d",total);
  if(rc!=1||total<=0)$fatal(1,"empty/malformed vector count");
  out_fd=$fopen("capture.txt","w");if(!out_fd)$fatal(1,"capture file open");
  for(count=0;count<total;count++)begin
   rc=$fscanf(fd,"%d %d %d %d %d %d %d %d %d",r,en,pcm,delay_value,dry,wet,fb,valid_expected,pcm_expected);
   if(rc!=9)$fatal(1,"malformed record/count mismatch at %0d",count);
   if((r!=0&&r!=1)||(en!=0&&en!=1)||(valid_expected!=0&&valid_expected!=1)||
      pcm < -8388608 || pcm > 8388607 || pcm_expected < -8388608 || pcm_expected > 8388607 ||
      delay_value<0||delay_value>=DEPTH||dry<0||dry>32767||wet<0||wet>32767||fb<0||fb>32767)
    $fatal(1,"invalid vector range");
   @(negedge sys_clk);
   sys_rst_n=r;sample_enable=en;pcm_in=24'(pcm);delay_samples=16'(delay_value);
   dry_gain=15'(dry);wet_gain=15'(wet);feedback=15'(fb);
   #2;if(!r&&(pcm_valid!==0||pcm_out!==24'd0))$fatal(1,"async reset did not immediately clear output");
   @(posedge sys_clk);#2;
   if((^pcm_out===1'bx)||(pcm_valid!==0&&pcm_valid!==1))$fatal(1,"unknown X output");
   $fdisplay(out_fd,"%0d %0d %06h",count,pcm_valid,pcm_out);
   if(pcm_valid!==1'(valid_expected))$fatal(1,"valid timing/count mismatch row=%0d got=%b expected=%0d",count,pcm_valid,valid_expected);
   if(pcm_out!==24'(pcm_expected))$fatal(1,"PCM/feedback history mismatch row=%0d got=%0d expected=%0d",count,$signed(pcm_out),pcm_expected);
   if(pcm_valid)valid_count++;
  end
  while(!$feof(fd))begin
   extra=$fgetc(fd);
   if(extra!=-1&&extra!=9&&extra!=10&&extra!=13&&extra!=32)$fatal(1,"trailing malformed/count mismatch");
  end
  if(count==0||valid_count==0)$fatal(1,"empty/no valid test");
  $fclose(fd);$fclose(out_fd);
  $display("PASS delay independent cycle TB depth=%0d cycles=%0d valid=%0d",DEPTH,count,valid_count);$finish;
 end
 initial begin #20000000;$fatal(1,"delay timeout");end
endmodule
