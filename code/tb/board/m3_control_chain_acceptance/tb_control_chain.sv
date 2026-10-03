// Test-only voice metadata/base fixture, NOT the production voice router.
`timescale 1ns/1ps
module tb_control_chain;
 import audio_defs_pkg::*;
 logic clk=0; always #10 clk=~clk;
 logic rst_n=0, byte_valid=0, select_source=0;
 logic [7:0] byte_data=0;
 wire [1:0] parser_valid,parser_ready;
 wire [127:0] parser_data;
 wire [63:0] pd0,pd1;
 wire [31:0] errors0,errors1,overflow0,overflow1;
 midi_event_parser #(.SOURCE_ID(0),.LOCAL_FIFO_DEPTH(128)) p0(
  .clk(clk),.rst_n(rst_n),.midi_byte(byte_data),.midi_byte_valid(byte_valid&&!select_source),
  .midi_byte_error(1'b0),.event_ready(parser_ready[0]),.event_valid(parser_valid[0]),.event_data(pd0),
  .parser_error_count(errors0),.event_fifo_overflow_count(overflow0),
  .event_fifo_level(),.event_fifo_high_watermark());
 midi_event_parser #(.SOURCE_ID(9),.LOCAL_FIFO_DEPTH(128)) p1(
  .clk(clk),.rst_n(rst_n),.midi_byte(byte_data),.midi_byte_valid(byte_valid&&select_source),
  .midi_byte_error(1'b0),.event_ready(parser_ready[1]),.event_valid(parser_valid[1]),.event_data(pd1),
  .parser_error_count(errors1),.event_fifo_overflow_count(overflow1),
  .event_fifo_level(),.event_fifo_high_watermark());
 logic uart_rx_pin=1,uart_mode=0;
 wire uart_valid,uart_ready;
 wire [63:0] uart_data;
 wire [31:0] uart_errors,uart_parse_errors,uart_overflow;
 midi_input #(.SOURCE_ID(3)) uart_input(
  .clk(clk),.rst_n(rst_n),.midi_rx_async(uart_rx_pin),.event_ready(uart_ready),
  .event_valid(uart_valid),.event_data(uart_data),.uart_frame_error_count(uart_errors),
  .parser_error_count(uart_parse_errors),.event_fifo_overflow_count(uart_overflow),
  .event_fifo_level(),.event_fifo_high_watermark(),.midi_rx_busy());
 // Two byte streams multiplexed only at event handshakes; stable grant on stall.
 logic grant=0;
 wire selected=parser_valid[grant]?grant:!grant;
 wire midi_valid=uart_mode?uart_valid:parser_valid[selected];
 wire [63:0] midi_data=uart_mode?uart_data:(selected?pd1:pd0);
 wire midi_ready;
 assign parser_ready[0]=!uart_mode && !selected && midi_ready;
 assign parser_ready[1]=!uart_mode && selected && midi_ready;
 assign uart_ready=uart_mode && midi_ready;
 always @(posedge clk)if(!rst_n)grant<=0;else if(midi_valid&&midi_ready)grant<=!selected;
 // Independent competing-source fixture: no production input algorithm replaced.
 logic button_valid=0; logic [63:0] button_data=0;
 wire button_ready,event_valid;
 wire [63:0] event_data;
 wire [15:0] fifo_level,fifo_high;
 logic event_gate=1;
 wire control_ready;
 wire event_ready=event_gate&&control_ready;
 performance_event_fifo #(.DEPTH(32)) fifo(
  .clk(clk),.rst_n(rst_n),.button_valid(button_valid),.button_ready(button_ready),.button_data(button_data),
  .midi_valid(midi_valid),.midi_ready(midi_ready),.midi_data(midi_data),.event_valid(event_valid),
  .event_ready(event_ready),.event_data(event_data),.event_fifo_level(fifo_level),.event_fifo_high_watermark(fifo_high));
 logic request_valid=0; wire request_ready;
 logic [31:0] request_id=0;
 logic [3:0] slot_occupied=15,note_on_mask=0;
 logic [15:0] slot_source_ids=0,slot_channels=0;
 logic [127:0] slot_generations=0,live_base=0,frozen_base=0;
 wire snapshot_valid,snapshot_ready;
 wire [31:0] snapshot_id;
 wire [3:0] snapshot_occupied;
 wire [15:0] snapshot_sources,snapshot_channels;
 wire [127:0] snapshot_generations;
 wire [47:0] snapshot_pitch_bend,snapshot_modulation;
 wire [19:0] snapshot_pitch_range;
 performance_control_snapshot control(
  .clk(clk),.rst_n(rst_n),.event_valid(event_valid&&event_gate),.event_ready(control_ready),.event_data(event_data),
  .request_valid(request_valid),.request_ready(request_ready),.request_id(request_id),.slot_occupied(slot_occupied),
  .slot_source_ids(slot_source_ids),.slot_channels(slot_channels),.slot_generations(slot_generations),
  .snapshot_valid(snapshot_valid),.snapshot_ready(snapshot_ready),.snapshot_id(snapshot_id),
  .snapshot_occupied(snapshot_occupied),.snapshot_sources(snapshot_sources),.snapshot_channels(snapshot_channels),
  .snapshot_generations(snapshot_generations),.snapshot_pitch_bend(snapshot_pitch_bend),
  .snapshot_modulation(snapshot_modulation),.snapshot_pitch_range(snapshot_pitch_range),.control_applied(),.invalid_range());
 always @(posedge clk)if(!rst_n)frozen_base<=0;else if(request_valid&&request_ready)frozen_base<=live_base;
 logic cancel=0,result_ready=1,consumer_gate=1;
 wire consumer_ready,result_valid;
 assign snapshot_ready=consumer_ready&&consumer_gate;
 wire [31:0] result_id;
 wire [3:0] result_occupied;
 wire [15:0] result_sources,result_channels;
 wire [127:0] result_generations,result_fcw;
 pitch_mod_snapshot_pipeline #(.OCT_FILE("oct.mem"),.SUB_FILE("sub.mem"),.LFO_FILE("lfo.mem")) dut(
  .clk(clk),.rst_n(rst_n),.cancel(cancel),.request_valid(snapshot_valid&&consumer_gate),.request_ready(consumer_ready),
  .request_id(snapshot_id),.request_occupied(snapshot_occupied),.note_on_mask(note_on_mask),
  .request_sources(snapshot_sources),.request_channels(snapshot_channels),.request_generations(snapshot_generations),
  .request_base_fcw(frozen_base),.request_pitch_bend(snapshot_pitch_bend),.request_modulation(snapshot_modulation),
  .request_pitch_range(snapshot_pitch_range),.result_valid(result_valid),.result_ready(result_ready),
  .result_id(result_id),.result_occupied(result_occupied),.result_sources(result_sources),.result_channels(result_channels),
  .result_generations(result_generations),.result_fcw(result_fcw));
 wire [127:0] phases;
 for(genvar i=0;i<4;i++)assign phases[32*i+:32]=dut.g_lane[i].u_control.lfo_phase;
 integer fd,cycle=0,consumed=0,full_pop_push=0,stalls=0,read_stalls=0,write_through=0;
 logic [31:0] random_state=32'd20261003;
 integer req_due=-1,fcw_due=-1;
 logic [31:0] expected_phase[0:3];
 logic prev_fifo_stall=0,prev_snap_stall=0,prev_result_stall=0;
 logic [63:0] held_fifo;
 logic [311:0] held_snap;
 logic [323:0] held_result;
 task automatic check(input logic good,input string msg);
  if(good!==1'b1)$fatal(1,"%s cycle=%0d",msg,cycle);
 endtask
 always @(posedge clk)begin
  cycle++;
  if(cycle%10000==0)$fflush(fd);
  if(!rst_n)begin
   $fdisplay(fd,"R %0d",cycle);req_due=-1;fcw_due=-1;
   prev_fifo_stall=0;prev_snap_stall=0;prev_result_stall=0;
   for(integer i=0;i<4;i++)expected_phase[i]=0;
  end else begin
   if(prev_fifo_stall)check(event_valid&&event_data===held_fifo,"FIFO held payload");
   if(prev_snap_stall)check(snapshot_valid&&{snapshot_id,snapshot_occupied,snapshot_sources,snapshot_channels,snapshot_generations,snapshot_pitch_bend,snapshot_modulation,snapshot_pitch_range}===held_snap,"snapshot held payload");
   if(prev_result_stall&&!cancel)check(result_valid&&{result_id,result_occupied,result_sources,result_channels,result_generations,result_fcw}===held_result,"result held payload");
   prev_fifo_stall=event_valid&&!event_ready;held_fifo=event_data;
   prev_snap_stall=snapshot_valid&&!snapshot_ready;
   held_snap={snapshot_id,snapshot_occupied,snapshot_sources,snapshot_channels,snapshot_generations,snapshot_pitch_bend,snapshot_modulation,snapshot_pitch_range};
   prev_result_stall=result_valid&&!result_ready&&!cancel;
   held_result={result_id,result_occupied,result_sources,result_channels,result_generations,result_fcw};
   if(prev_result_stall)stalls++;
   if(event_valid&&!control_ready)read_stalls++;
   if(event_valid&&event_ready)$fdisplay(fd,"F %0d %016h",cycle,event_data);
   if(button_valid&&button_ready)$fdisplay(fd,"P %0d %016h 1",cycle,button_data);
   if(midi_valid&&midi_ready)$fdisplay(fd,"P %0d %016h 0",cycle,midi_data);
   if(fifo_level==32&&event_valid&&event_ready&&((button_valid&&button_ready)||(midi_valid&&midi_ready)))full_pop_push++;
   if(note_on_mask)$fdisplay(fd,"N %0d %h",cycle,note_on_mask);
   if(snapshot_valid&&snapshot_ready)begin
    $fdisplay(fd,"C %0d %0d %032h",cycle,snapshot_id,frozen_base);fcw_due=cycle+7;
   end
   if(cancel)begin $fdisplay(fd,"X %0d",cycle);fcw_due=-1;end
   if(request_valid&&request_ready)begin
    $fdisplay(fd,"Q %0d %0d %h %04h %04h %032h %032h",cycle,request_id,slot_occupied,slot_source_ids,slot_channels,slot_generations,live_base);req_due=cycle+4;
    if(event_valid&&event_ready)write_through++;
   end
   if(result_valid&&result_ready&&!cancel)begin
    $fdisplay(fd,"T %0d %0d %h %04h %04h %032h %032h",cycle,result_id,result_occupied,result_sources,result_channels,result_generations,result_fcw);consumed++;
   end
   for(integer i=0;i<4;i++)begin
    if(note_on_mask[i])expected_phase[i]=0;
    if(snapshot_valid&&snapshot_ready&&snapshot_occupied[i])expected_phase[i]=expected_phase[i]+32'd447392;
   end
  end
  #2;
  if(rst_n)begin
   for(integer i=0;i<4;i++)check(phases[32*i+:32]===expected_phase[i],"LFO advances exactly once per accepted occupied lane");
   if(req_due==cycle)begin
    check(snapshot_valid,"snapshot exact E+4");
    $fdisplay(fd,"S %0d %0d %h %04h %04h %032h %012h %012h %05h",cycle,snapshot_id,snapshot_occupied,snapshot_sources,snapshot_channels,snapshot_generations,snapshot_pitch_bend,snapshot_modulation,snapshot_pitch_range);req_due=-1;
   end
   if(fcw_due==cycle)begin
    check(result_valid,"FCW exact E+7");
    $fdisplay(fd,"O %0d %0d %h %04h %04h %032h %032h",cycle,result_id,result_occupied,result_sources,result_channels,result_generations,result_fcw);fcw_due=-1;
   end
  end else check(!result_valid&&result_fcw==0&&!snapshot_valid,"reset outputs immediately clear");
 end
 task automatic tick(input integer n);repeat(n)@(negedge clk);endtask
 task automatic reset_all;
  @(negedge clk);rst_n=0;request_valid=0;byte_valid=0;button_valid=0;cancel=0;note_on_mask=0;
  #2;check(!result_valid&&!snapshot_valid,"asynchronous reset clears tokens");tick(3);rst_n=1;tick(2);
 endtask
 task automatic put_byte(input integer src,input integer value);
  @(negedge clk);select_source=(src==9);byte_data=8'(value);byte_valid=1;
  @(negedge clk);byte_valid=0;
 endtask
 task automatic midi(input integer src,status,a,b);
  // Independent raw input trace, decoded by Python; includes running status/realtime.
  put_byte(src,status);put_byte(src,a);if((status>>4)!=12)put_byte(src,b);
 endtask
 always @(posedge clk)if(rst_n&&byte_valid)$fdisplay(fd,"B %0d %0d %02h",cycle,select_source?9:0,byte_data);
 task automatic uart_byte(input integer value);
  $fdisplay(fd,"B %0d 3 %02h",cycle,value);
  @(negedge clk);uart_rx_pin=0;tick(1600);
  for(integer bitno=0;bitno<8;bitno++)begin uart_rx_pin=(value>>bitno)&1;tick(1600);end
  uart_rx_pin=1;tick(1600);tick(20);
 endtask
 task automatic fixture_event(input integer identity,kind,ctrl,value);
  @(negedge clk);button_data=0;button_data[63:61]=3'(kind);button_data[60:53]=8'(identity);
  button_data[25:18]=8'(ctrl);button_data[17:6]=12'(value);button_valid=1;
  do @(posedge clk);while(!button_ready);
  @(negedge clk);button_valid=0;
 endtask
 task automatic launch(input integer identity,input integer mask);
  wait(request_ready);@(negedge clk);request_id++;slot_occupied=4'(mask);
  for(integer i=0;i<4;i++)begin
   // Repeated identities and differing channels, plus empty slots.
   slot_source_ids[4*i+:4]=4'((identity+i*(request_id%2))>>4);
   slot_channels[4*i+:4]=4'(identity+i*(request_id%2));
   slot_generations[32*i+:32]=request_id*4+i;
   random_state=random_state^(random_state<<13);
   random_state=random_state^(random_state>>17);
   random_state=random_state^(random_state<<5);
   live_base[32*i+:32]=(request_id%31==0)?32'd1122405052:32'd11746659+(random_state%50000000);
  end
  request_valid=1;@(negedge clk);request_valid=0;
  // Simulated slot steal after E, no changes to the frozen transaction.
  live_base=live_base+128'h11111111222222223333333344444444;
  slot_source_ids=~slot_source_ids;slot_channels=~slot_channels;slot_generations=~slot_generations;
 endtask
 task automatic consume;wait(result_valid);@(negedge clk);result_ready=1;tick(1);endtask
 integer mark,start_cycle,delta;
 initial begin
  fd=$fopen("capture.txt","w");if(!fd)$fatal(1,"capture open failed");
  reset_all();
  // Actual UART small mixed set, no force on parser internals.
  uart_mode=1;
  uart_byte('he5);uart_byte(0);uart_byte(96);
  uart_byte('hb5);uart_byte(1);uart_byte(127);
  uart_byte('hc5);uart_byte(127);
  uart_byte('h95);uart_byte(60);uart_byte(100);
  uart_byte('hb5);uart_byte(64);uart_byte(127);
  uart_byte('h85);uart_byte(60);uart_byte(0);tick(100);
  launch('h35,15);consume();uart_mode=0;
  // Mixed dual parser streams: running status, realtime and all Program values.
  event_gate=0;
  for(integer n=0;n<80;n++)begin
   midi(n%2?9:0,'h90+(n%16),48+n%24,80);
   if(n%4==0)midi(n%2?9:0,'hb0+(n%16),64,127);
   midi(n%2?9:0,'hc0+(n%16),n,0);
   midi(n%2?9:0,'he0+(n%2),n%128,96);
   midi(n%2?9:0,'hb0+(n%2),1,n%128);
  end
  check(fifo_level==32,"real public FIFO full");event_gate=1;
  fixture_event('hf1,EVENT_CONTROL_CHANGE,CTRL_PITCH_RANGE,24);
  tick(220000); // pending per-source controls drain at the real 50MHz/1kHz limit
  for(integer n=80;n<128;n++)midi(0,'hc0+(n%16),n,0);
  put_byte(0,'h90);put_byte(0,62);put_byte(0,'hf8);put_byte(0,81);
  put_byte(0,63);put_byte(0,82); // running status
  midi(9,'h80,55,0);
  tick(100);$fdisplay(fd,"D %0d",cycle);
  // Independent producer populates all 256 accepted identities, range0/24/invalid.
  for(integer id=0;id<256;id++)begin
   fixture_event(id,EVENT_PITCH_BEND,CTRL_PITCH_BEND,(id*37)&4095);
   fixture_event(id,EVENT_CONTROL_CHANGE,CTRL_MODULATION,4095-id);
   fixture_event(id,EVENT_CONTROL_CHANGE,CTRL_PITCH_RANGE,(id%5==0)?0:((id%5==1)?24:2));
   fixture_event(id,EVENT_CONTROL_CHANGE,CTRL_PITCH_RANGE,25);
   launch(id,15);consume();
  end
  tick(200);check(fifo_level==0,"initial event streams drained");
  // Same-edge FIFO accepted control + Q. A queued not-yet-accepted value excluded.
  event_gate=0;fixture_event(0,EVENT_PITCH_BEND,CTRL_PITCH_BEND,2047);
  @(negedge clk);event_gate=1; // launch drives on next negedge, so use explicit Q here
  request_id++;slot_source_ids=0;slot_channels=0;slot_occupied=15;request_valid=1;
  @(negedge clk);request_valid=0;consume();
  event_gate=0;fixture_event(0,EVENT_PITCH_BEND,CTRL_PITCH_BEND,2048);
  launch(0,15);consume();event_gate=1;tick(10);
  // Held output + next held snapshot, both with metadata/base changing after E.
  result_ready=0;launch(0,15);wait(result_valid);launch(1,15);wait(snapshot_valid);
  tick(40);consume();consume();
  // Coincident note-on and accepted FCW, and separate-cycle note-on.
  consumer_gate=0;launch(2,15);wait(snapshot_valid);
  @(negedge clk);note_on_mask=15;consumer_gate=1;tick(1);note_on_mask=0;consume();
  @(negedge clk);note_on_mask=5;tick(1);note_on_mask=0;
  // Cadenced sampled fixture: exact alternating1041/1042 cycles, default LFO.
  mark=cycle;
  for(integer n=0;n<576;n++)begin
   start_cycle=cycle;launch(n%256,n%17==0?0:15);consume();
   delta=(n%2)?1042:1041;tick(delta-(cycle-start_cycle));
  end
  $fdisplay(fd,"K %0d %0d",mark,cycle);
  // Cancel each in-flight math age and one held result; drain before reuse.
  for(integer k=0;k<8;k++)begin
   result_ready=0;launch(k,15);wait(snapshot_valid&&snapshot_ready);@(posedge clk);@(negedge clk);
   tick(k);cancel=1;tick(1);cancel=0;tick(12);check(!result_valid,"cancel removes old tag");
   result_ready=1;launch(k+16,15);consume();
  end
  // Reset across each four-read stage, each FCW stage and held result.
  for(integer k=0;k<4;k++)begin launch(k,15);tick(k);reset_all();launch(k+32,15);consume();end
  for(integer k=0;k<8;k++)begin
   result_ready=0;launch(k,15);wait(snapshot_valid&&snapshot_ready);@(posedge clk);@(negedge clk);
   tick(k);reset_all();result_ready=1;launch(k+64,15);consume();
  end
  tick(30);
  check(errors0==0&&errors1==0&&overflow0==0&&overflow1==0&&uart_errors==0&&uart_parse_errors==0&&uart_overflow==0,"input no error/overflow");
  check(consumed>=512&&stalls>=32&&full_pop_push>0&&read_stalls>0&&write_through>0,"required nonempty boundary coverage");
  $fdisplay(fd,"END %0d %0d %0d %0d %0d",consumed,stalls,full_pop_push,read_stalls,write_through);
  $fclose(fd);$display("PASS control chain RTL consumed=%0d stalls=%0d full_pop_push=%0d read_stalls=%0d write_through=%0d",consumed,stalls,full_pop_push,read_stalls,write_through);$finish;
 end
 initial begin #40000000;$fatal(1,"control chain timeout");end
endmodule
