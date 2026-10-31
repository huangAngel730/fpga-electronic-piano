`timescale 1ns/1ps
// Compare frozen original against the identity-address change, including
// internal history/pointers and every output, rather than only valid samples.
module delay_identity_pair #(parameter DEPTH=16)(
 input logic clk,rst_n,flush,en,
 input logic signed [23:0] pcm,
 input logic [15:0] delay_samples,
 input logic [14:0] dry,wet,feedback,
 output integer comparisons=0,valid_results=0,wraps=0
);
 wire signed [23:0] a,b;
 wire av,bv,ac,bc,af,bf;
 m1td_delay_effect #(.DEPTH(DEPTH)) dut(clk,rst_n,flush,en,pcm,delay_samples,dry,wet,feedback,a,ac,af,av);
 m1td_delay_reference #(.DEPTH(DEPTH)) ref_dut(clk,rst_n,flush,en,pcm,delay_samples,dry,wet,feedback,b,bc,bf,bv);
 always @(posedge clk or negedge rst_n) begin
  #1;
  comparisons=comparisons+1;
  if({a,ac,af,av,dut.wr_ptr,dut.rd_ptr} !== {b,bc,bf,bv,ref_dut.wr_ptr,ref_dut.rd_ptr})
   $fatal(1,"delay first difference depth=%0d comparison=%0d",DEPTH,comparisons);
  if(av) valid_results=valid_results+1;
  if(rst_n&&!flush&&av&&dut.wr_ptr==0)wraps=wraps+1;
  for(integer i=0;i<DEPTH;i=i+1)
   if(dut.buffer[i] !== ref_dut.buffer[i])
    $fatal(1,"history first difference depth=%0d index=%0d comparison=%0d",DEPTH,i,comparisons);
 end
endmodule

module tb_delay_identity_miter;
 logic clk=0,rst_n=1,flush=0,en=0;
 logic signed [23:0] pcm=0;
 logic [15:0] delay_samples=0;
 logic [14:0] dry=0,wet=0,feedback=0;
 integer c16,v16,w16,c1024,v1024,w1024;
 integer resets=0,flushes=0;
 logic [31:0] rng=32'h3754a821;
 always #12.5 clk=~clk;
 delay_identity_pair #(.DEPTH(16)) small_pair(clk,rst_n,flush,en,pcm,delay_samples,dry,wet,feedback,c16,v16,w16);
 delay_identity_pair #(.DEPTH(1024)) actual_pair(clk,rst_n,flush,en,pcm,delay_samples,dry,wet,feedback,c1024,v1024,w1024);
 initial begin
  #3 rst_n=0;resets=resets+1;
  #18 rst_n=1;
  for(integer n=0;n<18000;n=n+1) begin
   @(negedge clk);
   rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
   en=(n<6000)||(n%5==0)||(n%31<17);
   case(n%11)
    0:pcm=24'sh7fffff;
    1:pcm=24'sh800000;
    2:pcm=0;
    default:pcm=rng[23:0];
   endcase
   delay_samples=(n%7==0)?0:((n%7==1)?16'hffff:rng[15:0]);
   dry=(n%9==0)?0:((n%9==1)?32767:rng[14:0]);
   wet=(n%9==2)?0:((n%9==3)?32767:rng[29:15]);
   feedback=(n%9==4)?0:((n%9==5)?32767:(rng[14:0]^15'h42b1));
   // Idle drain before legal synchronous flush. Mid-operation async reset
   // additionally checks the original asynchronous behavior.
   if(n==7000||n==14000)begin
    en=0;repeat(4)@(negedge clk);
    flush=1;flushes=flushes+1;
    @(negedge clk);flush=0;
   end
   if(n==9000||n==16000)begin
    #3 rst_n=0;resets=resets+1;
    #5 rst_n=1;
   end
  end
  en=0;repeat(5)@(negedge clk);
  if(v16<8000||v1024<8000||w16<100||w1024<5)$fatal(1,"insufficient wrap/valid coverage");
  $display("DELAY_IDENTITY_MITER_COMPLETE comparisons16=%0d valid16=%0d wraps16=%0d comparisons1024=%0d valid1024=%0d wraps1024=%0d async_resets=%0d flushes=%0d",c16,v16,w16,c1024,v1024,w1024,resets,flushes);
  $finish;
 end
 initial begin #1000000;$fatal(1,"miter timeout");end
endmodule
