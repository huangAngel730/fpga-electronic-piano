`timescale 1ns/1ps
module tb_prepared_corner;
logic clk=0,rst_n=0;always #10 clk=~clk;
logic[31:0]p=0;logic[4:0]rr=0,ix=0;logic parsed=0;logic[11:0]val=0;
wire v;wire[4:0]idx;wire[11:0]value;
prepared_selector_probe dut(clk,rst_n,p,rr,parsed,ix,val,v,idx,value);
integer checks=0;
initial begin
repeat(2)@(negedge clk);rst_n=1;
for(integer n=0;n<32;n++) begin
 @(negedge clk);rr=5'(n);p=(32'd1<<5'(n+1))|(32'd1<<5'(n+3))|(32'd1<<5'(n+5));
 // External state forcing must first initialize the lookahead cache. Actual
 // parser state cannot jump independently of its same-edge update equations.
 parsed=0;@(posedge clk);#1;@(negedge clk);
 // This corner uses CC1 cancellation (odd absolute slot). For even RR, all three are CC1.
 if(n%2==0)begin
 parsed=1;ix=5'(n+1);val=0;
 @(posedge clk);#1;p=p&~(32'd1<<ix);ix=5'(n+3);#1;
 if(!v || idx!==5'(n+5))$fatal(1,"two consecutive cancellations mismatch rr=%0d got=%0d",n,idx);
 checks++;
 end else begin
 parsed=0;@(posedge clk);#1;
 parsed=1;ix=5'(n);val=12'd371;
 #1;if(!v || idx!==5'(n) || value!=371)$fatal(1,"current insertion priority mismatch rr=%0d",n);
 checks++;
 end
end
@(negedge clk);rst_n=0;parsed=0;p=0;@(posedge clk);#1;if(v)$fatal(1,"reset stale candidate");checks++;
if(checks!=33)$fatal(1,"empty corner check");
$display("PASS prepared corner checks=%0d",checks);$finish;
end
initial begin #100000;$fatal(1,"timeout");end
endmodule
