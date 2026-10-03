// Exhaustive legal q/pulse/pop cases against frozen6055bb8; actual sequential RTL.
`timescale 1ns/1ps
module tb_tail_select_exhaustive #(
 parameter integer BUTTONS=2, LOCAL=4
);
 logic clk=0;always #10 clk=~clk;
 logic rst_n=0,event_ready=0;
 logic [BUTTONS-1:0]press=0,release_keys=0;
 wire valid0,valid1;wire[63:0]data0,data1;wire[31:0]count0,count1;
 button_reference #(.BUTTON_COUNT(BUTTONS),.LOCAL_FIFO_DEPTH(LOCAL))baseline(
 .clk(clk),.rst_n(rst_n),.button_press_pulse(press),.button_release_pulse(release_keys),
 .event_ready(event_ready),.event_valid(valid0),.event_data(data0),.overflow_count(count0));
 button_event_converter #(.BUTTON_COUNT(BUTTONS),.LOCAL_FIFO_DEPTH(LOCAL))candidate(
 .clk(clk),.rst_n(rst_n),.button_press_pulse(press),.button_release_pulse(release_keys),
 .event_ready(event_ready),.event_valid(valid1),.event_data(data1),.overflow_count(count1));
 integer checks=0,cases=0,n,pop,drop;
 logic[31:0]seeds[0:7];logic[31:0]branch0,branch1;
 logic[32:0]expected_sum;logic[31:0]expected_count;
 task automatic check(input logic ok,input string label);
 checks++;if(ok!==1'b1)$fatal(1,"tailselect %s B=%0d D=%0d case%0d count%h/%h",label,BUTTONS,LOCAL,cases,count0,count1);
 endtask
 initial begin
 seeds[0]=0;seeds[1]=32'hfe;seeds[2]=32'hfffe;seeds[3]=32'hfffffe;
 seeds[4]=32'h7ffffffe;seeds[5]=32'hfffffffc;seeds[6]=32'hfffffffe;seeds[7]=32'hffffffff;
 repeat(3)@(negedge clk);rst_n=1;
 for(integer q=0;q<=LOCAL;q++)begin
  for(integer pulses=0;pulses<(1<<(2*BUTTONS));pulses++)begin
   for(integer ready=0;ready<2;ready++)begin
    for(integer seed=0;seed<8;seed++)begin
     @(negedge clk);baseline.fifo_count=q;candidate.fifo_count=q;
     baseline.overflow_count=seeds[seed];candidate.overflow_count=seeds[seed];
     press=BUTTONS'(pulses);release_keys=BUTTONS'(pulses>>BUTTONS);event_ready=ready;
     n=0;for(integer k=0;k<2*BUTTONS;k++)n=n+((pulses>>k)&1);
     pop=(q>0)&&ready;drop=q-pop+n-LOCAL;if(drop<0)drop=0;
     expected_sum={1'b0,seeds[seed]}+drop;
     expected_count=expected_sum[32] ? 32'hffffffff : expected_sum[31:0];
     #1;branch0=candidate.count_no_pop;branch1=candidate.count_with_pop;
     check(candidate.drops_no_pop==(q+n>LOCAL ? q+n-LOCAL : 0),"no-pop branch drop formula");
     check(candidate.drops_with_pop==((q>0 ? q-1+n : q+n)>LOCAL ? (q>0 ? q-1+n : q+n)-LOCAL : 0),"pop branch guarded formula");
     event_ready=!ready;#1;
     check(candidate.count_no_pop===branch0&&candidate.count_with_pop===branch1,"both precomputed branches independent oflate-ready");
     event_ready=ready;#1;check(valid0===valid1&&data0===data1,"pre-edge exact event");
     @(posedge clk);#1;cases++;
     check(count0===expected_count&&count1===expected_count,"exact same-cycle saturation");
     check(candidate.fifo_count===baseline.fifo_count,"same-cycle local count");
     check(valid0===valid1&&data0===data1,"post-edge exact event");
     for(integer k=0;k<LOCAL;k++)check(candidate.fifo_mem[k]===baseline.fifo_mem[k],"unchanged ordered FIFO storage");
    end
   end
  end
 end
 @(negedge clk);rst_n=0;press='1;release_keys='1;event_ready=1;
 @(posedge clk);#1;check(count0===0&&count1===0&&!valid0&&!valid1,"reset beats pending new pulses");
 check(cases==(LOCAL+1)*(1<<(2*BUTTONS))*16,"exhaustive nonvacuous case count");
 $display("PASS tailselect exhaustive BUTTONS=%0d LOCAL=%0d cases=%0d checks=%0d",BUTTONS,LOCAL,cases,checks);$finish;
 end
 initial begin #30000000;$fatal(1,"exhaustive timeout");end
endmodule
