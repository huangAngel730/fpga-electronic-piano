`timescale 1ns/1ps
module tb_control_snapshot_selector;
logic clk=0;always #10 clk=~clk;
logic rst_n=0,cancel=0,request_valid=0,result_ready=0;
logic[31:0]request_mask=0,request_id=0,request_epoch=0;logic[4:0]request_rr=0;
wire request_ready,result_valid,first_valid,second_valid;wire[4:0]first_index,second_index;wire[31:0]result_id,result_epoch;
control_snapshot_selector dut(.*);
integer checks=0,completed=0,cancelled=0,cycle=0,last_accepted=-100;
integer file,scan,expected_id,expected_rr,expected_fv,expected_sv,expected_i,expected_j;
reg[31:0]expected_mask,expected_epoch;
string path;
logic[75:0]hold_data;
task automatic ck(input logic ok,input string message);checks++;if(ok!==1'b1)$fatal(1,"deep selector %s case=%0d cycle=%0d",message,completed,cycle);endtask
always @(posedge clk)begin
 cycle++;
 if(!rst_n)last_accepted=-100;
 else if(request_valid&&request_ready)begin ck(cycle-last_accepted>=4,"initiation spacing");last_accepted=cycle;end
end
initial begin
if(!$value$plusargs("VECTORS=%s",path))$fatal(1,"missingvectors");
file=$fopen(path,"r");if(!file)$fatal(1,"vectoropen");
repeat(4)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
while(!$feof(file))begin
 scan=$fscanf(file,"%d %h %d %h %d %d %d %d\n",expected_id,expected_mask,expected_rr,expected_epoch,expected_fv,expected_i,expected_sv,expected_j);
 if(scan==-1 && $feof(file))break;
 if(scan!=8)$fatal(1,"malformedvect");
 @(negedge clk);ck(request_ready,"requestadmission");request_mask=expected_mask;request_rr=5'(expected_rr);request_id=expected_id;request_epoch=expected_epoch;request_valid=1;
 @(posedge clk);#1;ck(!result_valid&&!request_ready,"capture stage no premature output");
 @(negedge clk);request_valid=0;request_mask=~expected_mask;request_rr=5'(expected_rr+17);request_id=32'hffffffff;request_epoch=~expected_epoch;
 @(posedge clk);#1;ck(!result_valid,"group stage no premature output");
 @(negedge clk);@(posedge clk);#1;
 ck(result_valid,"Eplus2result");
 ck({first_valid,first_index,second_valid,second_index}==={1'(expected_fv),5'(expected_i),1'(expected_sv),5'(expected_j)},"snapshot roundrobin oracle");
 ck(result_id==expected_id && result_epoch==expected_epoch,"id and epoch aligned frozen");
 hold_data={first_valid,first_index,second_valid,second_index,result_id,result_epoch};
 if(completed%31==0)repeat(4)begin @(negedge clk);@(posedge clk);#1;ck(result_valid&&!request_ready&&{first_valid,first_index,second_valid,second_index,result_id,result_epoch}===hold_data,"backpressure token stable");end
 @(negedge clk);result_ready=1;@(posedge clk);#1;ck(!result_valid&&request_ready,"exactlyonce consume");@(negedge clk);result_ready=0;completed++;
end
$fclose(file);
if(completed!=18592)$fatal(1,"vacuous or truncatedcount=%0d",completed);
for(integer st=1;st<=3;st++)begin
 @(negedge clk);request_mask=32'hffffffff;request_id=32'h12345;request_epoch=77;request_valid=1;
 @(negedge clk);request_valid=0;
 repeat(st-1)@(negedge clk);
 cancel=1;#1;ck(!request_ready&&!result_valid,"cancel gates both transactions");@(negedge clk);cancel=0;
 repeat(3)begin @(negedge clk);ck(!result_valid&&request_ready,"cancel drains no old token");end
 cancelled++;
end
@(negedge clk);request_valid=1;request_mask=32'hffffffff;@(negedge clk);request_valid=0;rst_n=0;
#1;ck(!result_valid&&!request_ready,"reset flushes inflight");repeat(3)@(negedge clk);rst_n=1;repeat(4)@(negedge clk);ck(request_ready&&!result_valid,"reset recovery");
$display("PASS deep snapshot selector cases=%0d checks=%0d cancels=%0d E_to_Eplus2 II4",completed,checks,cancelled);$finish;
end
initial begin #10000000;$fatal(1,"TBtimeout");end
endmodule
