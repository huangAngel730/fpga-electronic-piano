`timescale 1ns/1ps
module tb_midi_deep_present;
 import audio_defs_pkg::*;
 parameter integer BURST=8,DEPTH=8,CLOCK_HZ=100000;
 localparam integer INTERVAL=(CLOCK_HZ+999)/1000;
 logic fixture_mode=0,fixture_valid=0;performance_event_t fixture_event;
 logic clk=0,rst_n=0;always #10 clk=~clk;
 logic[7:0]midi_byte=0;logic midi_byte_valid=0,midi_byte_error=0,event_ready=0;
 wire event_valid;performance_event_t event_data;
 wire[15:0]level,high_water;wire[31:0]overflow,errors;
 midi_event_parser #(.LOCAL_FIFO_DEPTH(DEPTH),.SOURCE_ID(4'd7),.CLK_HZ(CLOCK_HZ),.MAX_DISCRETE_BURST(BURST))dut(
  .clk(clk),.rst_n(rst_n),.midi_byte(midi_byte),.midi_byte_valid(midi_byte_valid),.midi_byte_error(midi_byte_error),
  .event_ready(event_ready),.event_valid(event_valid),.event_data(event_data),.event_fifo_level(level),
  .event_fifo_high_watermark(high_water),.event_fifo_overflow_count(overflow),.parser_error_count(errors));
 // Decoder comparison uses an unchanged production parser renamed by runner.
 wire decoder_valid;performance_event_t decoder_data;wire[15:0]dl,dh;wire[31:0]dover,derror;
 midi_event_parser_reference #(.LOCAL_FIFO_DEPTH(DEPTH),.SOURCE_ID(4'd7),.CLK_HZ(CLOCK_HZ),.MAX_DISCRETE_BURST(BURST))reference_decoder(
  .clk(clk),.rst_n(rst_n),.midi_byte(midi_byte),.midi_byte_valid(midi_byte_valid),.midi_byte_error(midi_byte_error),
  .event_ready(1'b0),.event_valid(decoder_valid),.event_data(decoder_data),.event_fifo_level(dl),
  .event_fifo_high_watermark(dh),.event_fifo_overflow_count(dover),.parser_error_count(derror));
 performance_event_t queue[0:DEPTH-1],held_event,model_locked_event;
 integer qcount=0,peak=0,cycle=0,checks=0,control_count=0,discrete_count=0,grant_count=0;
 integer fifo_full_pop_push=0,overflow_expected=0,due_burst=0,last_control=-100000000;
 integer cancellations=0,updates_inflight=0,latest_locks=0,selection_cycles=0;
 bit was_stalled=0,model_locked=0;
 logic[31:0]pending=0,mask_now;logic[11:0]values[0:31],mod_values[0:15];logic[15:0]mod_valid=0;
 logic[4:0]rr=0,locked_slot=0,pick,slot;
 logic keep_now;integer winner,idx;logic[11:0]expected_value;
 task automatic check(input bit ok,input string why);
  begin checks++;if(!ok)$fatal(1,"deep parser oracle cycle=%0d: %s",cycle,why);end
 endtask
 always @(posedge clk)begin
  cycle++;
  if(!rst_n)begin
   qcount=0;peak=0;overflow_expected=0;due_burst=0;last_control=-100000000;
   pending=0;rr=0;was_stalled=0;model_locked=0;locked_slot=0;model_locked_event='0;mod_valid=0;
   for(integer k=0;k<32;k++)values[k]=0;
   for(integer k=0;k<16;k++)mod_values[k]=0;
  end else begin
   if(!fixture_mode)check(dut.parsed_event_valid===reference_decoder.parsed_event_valid &&
         dut.parsed_event_data===reference_decoder.parsed_event_data,"unchanged real byte decode");
   if(was_stalled)check(event_valid && event_data===held_event,"held presentation changed under backpressure");
   mask_now=pending;keep_now=0;
   if(dut.parsed_control)begin
    slot={dut.parsed_event_data.channel,dut.parsed_event_data.control_id==CTRL_MODULATION};
    keep_now=!(slot[0] && ((model_locked&&locked_slot==slot)?
      model_locked_event.control_value==dut.parsed_event_data.control_value:
      (mod_valid[slot[4:1]]&&mod_values[slot[4:1]]==dut.parsed_event_data.control_value)));
    mask_now[slot]=keep_now;
    if(!keep_now&&pending[slot])cancellations++;
    if(dut.selection_busy)updates_inflight++;
   end
   winner=-1;
   for(integer k=0;k<32;k++)begin idx=(rr+k)%32;if(winner<0&&mask_now[idx])winner=idx;end
   if(dut.start_selection)begin check(dut.eligible_mask===mask_now,"captured bitmap equals effective live mask");selection_cycles=0;end
   else if(dut.selection_busy)begin selection_cycles++;check(selection_cycles<=3,"bounded selection cannot globally retry/starve");end
   if(mask_now==0 || cycle-last_control<INTERVAL)due_burst=0;
   if(event_valid&&event_ready)begin
    if(model_locked)begin
     check(event_data===model_locked_event,"immutable control payload handshake");
     check(cycle-last_control>=INTERVAL,"aggregate 1kHz cooldown");
     last_control=cycle;control_count++;due_burst=0;
     if(locked_slot[0])begin mod_valid[locked_slot[4:1]]=1;mod_values[locked_slot[4:1]]=model_locked_event.control_value;end
     model_locked=0;
    end else begin
     check(qcount>0,"no extra hidden FIFO capacity");check(event_data===queue[0],"discrete FIFO order and identity");
     if(mask_now!=0&&cycle-last_control>=INTERVAL)begin due_burst++;check(due_burst<=BURST,"no ninth discrete handshake while control due");end
     if(qcount==DEPTH&&dut.parsed_discrete)fifo_full_pop_push++;
     for(integer k=0;k<DEPTH-1;k++)queue[k]=queue[k+1];qcount--;discrete_count++;
    end
   end
   pending=mask_now;
   if(dut.parsed_control)values[slot]=dut.parsed_event_data.control_value;
   if(dut.selector_valid && dut.selection_busy && mask_now!=0)
    check(dut.grant_control,"live pending requires first-computation grant, no hidden retry");
   if(dut.grant_control)begin
    check(winner>=0,"no stale/cancelled snapshot winner");pick=5'(winner);
    expected_value=values[pick];
    check(dut.selected_index===pick && dut.selected_value===expected_value,"exact LIVE RR and newest payload at lock");
    if(dut.parsed_control&&slot==pick)latest_locks++;
    pending[pick]=0;rr=pick+5'd1;locked_slot=pick;model_locked=1;
    model_locked_event='0;model_locked_event.event_type=pick[0]?EVENT_CONTROL_CHANGE:EVENT_PITCH_BEND;
    model_locked_event.source_id=7;model_locked_event.channel=pick[4:1];
    model_locked_event.control_id=pick[0]?CTRL_MODULATION:CTRL_PITCH_BEND;
    model_locked_event.control_value=expected_value;grant_count++;
   end
   if(dut.parsed_discrete)begin
    if(qcount<DEPTH)begin queue[qcount]=dut.parsed_event_data;qcount++;end
    else overflow_expected++;
   end
   if(qcount>peak)peak=qcount;
   was_stalled=event_valid&&!event_ready;held_event=event_data;
   #1;
   check(level==qcount && high_water==peak && overflow==overflow_expected,"FIFO count peak overflow, including full pop/push");
   check(dut.control_pending===pending && dut.round_robin_index===rr,"pending ownership and RR state");
   check(errors===derror,"parser error behavior unchanged");
  end
 end
 task automatic idle(input integer n);begin repeat(n)@(negedge clk);end endtask
 task automatic byte_send(input logic[7:0]b);begin @(negedge clk);midi_byte=b;midi_byte_valid=1;@(negedge clk);midi_byte_valid=0;end endtask
 task automatic msg(input logic[7:0]s,a,b);begin byte_send(s);byte_send(a);byte_send(b);end endtask
 task automatic pitch(input integer ch,v);begin msg(8'('hE0+ch),8'(v&127),8'((v>>7)&127));end endtask
 task automatic modulate(input integer ch,v);begin msg(8'('hB0+ch),8'd1,8'(v));end endtask
 task automatic reset_now;begin @(negedge clk);rst_n=0;idle(3);rst_n=1;idle(3);end endtask
 integer seed=32'h55ab89;integer rv;
 initial begin
  reset_now();
  if(CLOCK_HZ==50000000)begin
   // Actual 50MHz counter interval, focused 3 grants. Broad semantic cases run
   // at shorter test interval separately; no dozens of redundant ms waits.
   event_ready=0;msg('h90,60,100);idle(4);pitch(0,10000);idle(10);event_ready=1;
   wait(control_count==1);pitch(0,11000);modulate(1,77);
   wait(control_count==3);idle(20);
   check(grant_count==3&&control_count==3&&discrete_count==1,"real 50MHz nonvacuous 3 grants");
   check(checks>400000,"real 50000 cycle cooldown observed twice");
   $display("PASS deep parser REAL RATE clk=%0d interval=%0d cycles=%0d checks=%0d controls=%0d",CLOCK_HZ,INTERVAL,cycle,checks,control_count);
   $finish;
  end
  // Held discrete head may not be revoked by a new eligible control.
  event_ready=0;msg('h90,60,100);idle(4);pitch(0,8191);idle(25);
  check(event_valid&&event_data.event_type==EVENT_NOTE_ON,"held first note retained");
  event_ready=1;idle(INTERVAL+40);
  // Full FIFO, new input and draining handshake; capacity accounting oracle.
  event_ready=0;for(integer k=0;k<DEPTH+4;k++)msg('h90,8'(40+k),90);
  pitch(1,12000);event_ready=1;for(integer k=0;k<30;k++)msg('h90,8'(50+k%30),100);idle(INTERVAL+40);
  // All 32 identities, running status, realtime and normal CC64/program events.
  event_ready=0;
  for(integer ch=0;ch<16;ch++)begin pitch(ch,1000+ch*333);modulate(ch,30+ch);end
  event_ready=1;idle(34*INTERVAL+300);
  byte_send('hC0);byte_send(1);byte_send(0);byte_send('hF8);msg('hB0,64,127);msg('hB0,64,0);
  // Returning CC1 to its accepted value cancels unsent excursions.
  event_ready=0;msg('h90,60,100);modulate(0,99);modulate(0,30);idle(8);event_ready=1;idle(2*INTERVAL+40);
  // Sustained traffic and rapid same-slot updates during bounded selection.
  for(integer k=0;k<500;k++)begin
   rv=$random(seed);event_ready=(rv&7)!=0;
   case(k%5)
    0:pitch((k/5)%16,(k*61)%16384);
    1:modulate((k/5)%16,(k*17)%128);
    2:msg('h90,8'(30+k%58),8'(20+k%100));
    3:msg('h80,8'(30+k%58),0);
    4:begin byte_send('hB0);byte_send(64);byte_send(k[0]?127:0);end
   endcase
  end
  event_ready=1;idle(34*INTERVAL+500);
  // Directed full FIFO pop+push uses actual Note byte completion, not fixture.
  reset_now();event_ready=0;
  for(integer k=0;k<DEPTH;k++)msg('h90,8'(50+k),100);
  byte_send('h90);byte_send(77);
  @(negedge clk);midi_byte=101;midi_byte_valid=1;event_ready=1;
  @(negedge clk);midi_byte_valid=0;event_ready=0;idle(3);event_ready=1;idle(DEPTH+10);
  check(fifo_full_pop_push>0,"required full FIFO simultaneous consume/insert covered");
  // Explicit isolated scheduler fixtures permit 3 decoded controls on adjacent
  // clocks (faster than MIDI bytes). They are not reported as physical MIDI.
  reset_now();event_ready=1;
  for(integer ch=0;ch<5;ch++)begin modulate(ch,30+ch);idle(INTERVAL+10);end
  event_ready=0;msg('h90,60,100);idle(4);
  for(integer ch=0;ch<5;ch++)modulate(ch,90+ch);
  idle(INTERVAL+10);event_ready=1;wait(dut.start_selection);@(posedge clk);#2;
  fixture_mode=1;force dut.parsed_event_valid=fixture_valid;force dut.parsed_event_data=fixture_event;
  for(integer ch=0;ch<3;ch++)begin
   @(negedge clk);fixture_valid=1;fixture_event='0;fixture_event.event_type=EVENT_CONTROL_CHANGE;
   fixture_event.source_id=7;fixture_event.channel=4'(ch);fixture_event.control_id=CTRL_MODULATION;fixture_event.control_value=12'(((30+ch)<<5)|((30+ch)>>2));
  end
  @(negedge clk);fixture_valid=0;release dut.parsed_event_valid;release dut.parsed_event_data;
  midi_byte=8'hF8;midi_byte_valid=1;#2;fixture_mode=0;@(negedge clk);midi_byte_valid=0;
  idle(5);idle(4*INTERVAL+20);
  // Current-byte insertion ahead of the old snapshot must win immediately.
  reset_now();event_ready=0;msg('h90,60,100);idle(4);modulate(10,91);modulate(11,92);
  event_ready=1;wait(dut.start_selection);@(posedge clk);#2;idle(3);
  fixture_mode=1;force dut.parsed_event_valid=fixture_valid;force dut.parsed_event_data=fixture_event;
  fixture_valid=1;fixture_event='0;fixture_event.event_type=EVENT_CONTROL_CHANGE;
  fixture_event.source_id=7;fixture_event.channel=0;fixture_event.control_id=CTRL_MODULATION;fixture_event.control_value=101;
  @(negedge clk);fixture_valid=0;release dut.parsed_event_valid;release dut.parsed_event_data;
  midi_byte=8'hF8;midi_byte_valid=1;#2;fixture_mode=0;@(negedge clk);midi_byte_valid=0;
  idle(4*INTERVAL+20);
  // Same-slot update at the final lock edge must use newest payload, not ROM/cache.
  reset_now();event_ready=0;msg('h90,60,100);idle(4);pitch(0,10000);
  event_ready=1;wait(dut.start_selection);@(posedge clk);#2;idle(3);
  fixture_mode=1;force dut.parsed_event_valid=fixture_valid;force dut.parsed_event_data=fixture_event;
  fixture_valid=1;fixture_event='0;fixture_event.event_type=EVENT_PITCH_BEND;
  fixture_event.source_id=7;fixture_event.channel=0;fixture_event.control_id=CTRL_PITCH_BEND;fixture_event.control_value=12'hdef;
  @(negedge clk);fixture_valid=0;release dut.parsed_event_valid;release dut.parsed_event_data;
  midi_byte=8'hF8;midi_byte_valid=1;#2;fixture_mode=0;@(negedge clk);midi_byte_valid=0;
  idle(INTERVAL+20);$display("fixture counters latest=%0d cancel=%0d inflight=%0d",latest_locks,cancellations,updates_inflight);check(latest_locks>0 && cancellations>=4 && updates_inflight>=3,"mandatory latest-lock and cancellation repair fixtures covered");
  // Real malformed byte/reset recovery, reset held discrete/control/in-flight.
  event_ready=0;msg('h90,60,100);pitch(2,12345);idle(8);reset_now();
  event_ready=1;pitch(0,10000);wait(dut.selection_busy);reset_now();
  msg('hB0,1,88);wait(dut.control_locked);event_ready=0;idle(5);reset_now();
  @(negedge clk);midi_byte_valid=1;midi_byte_error=1;midi_byte='h91;@(negedge clk);midi_byte_valid=0;midi_byte_error=0;
  msg('h91,70,60);msg('h81,70,0);event_ready=1;idle(INTERVAL+50);
  check(grant_count>=40 && control_count>=35 && discrete_count>=100,"nonvacuous control/discrete coverage");
  check(checks>10000,"nonvacuous cycle checks");
  $display("PASS deep parser burst=%0d depth=%0d clk=%0d cycles=%0d checks=%0d grants=%0d controls=%0d discrete=%0d cancel=%0d inflight_updates=%0d latest_lock=%0d full_pop_push=%0d",BURST,DEPTH,CLOCK_HZ,cycle,checks,grant_count,control_count,discrete_count,cancellations,updates_inflight,latest_locks,fifo_full_pop_push);
  $finish;
 end
 initial begin #1000000000;$fatal(1,"deep parser timeout");end
endmodule
