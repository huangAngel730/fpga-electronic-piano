// Monitors actual bank scheduler against the private envelope's preparation contract.
module tb_bank_pipeline_event_monitor;
integer cycles=0,events=0,ticks=0;
for(genvar lane=0;lane<4;lane++)begin:g_lane
 always @(posedge tb_polyphonic_envelope_bank.clk)begin
  if(tb_polyphonic_envelope_bank.rst_n)begin
   if(lane==0)cycles=cycles+1;
   if(tb_polyphonic_envelope_bank.dut.slot_note_on[lane] || tb_polyphonic_envelope_bank.dut.slot_note_off[lane])begin
    events=events+1;
    if(tb_polyphonic_envelope_bank.dut.g_lane[lane].u_envelope.pending_tick &&
       (tb_polyphonic_envelope_bank.dut.g_lane[lane].u_envelope.state==1 ||
        tb_polyphonic_envelope_bank.dut.g_lane[lane].u_envelope.state==2 ||
        tb_polyphonic_envelope_bank.dut.g_lane[lane].u_envelope.state==7 ||
        tb_polyphonic_envelope_bank.dut.g_lane[lane].u_envelope.state==8 ||
        tb_polyphonic_envelope_bank.dut.g_lane[lane].u_envelope.state==9 ||
        tb_polyphonic_envelope_bank.dut.g_lane[lane].u_envelope.state==10))
      $fatal(1,"bank dispatched a new event over an accepted pending sample");
   end
   if(tb_polyphonic_envelope_bank.dut.lane_tick)begin
    if(lane==0)ticks=ticks+1;
    if(tb_polyphonic_envelope_bank.dut.slot_note_on[lane] || tb_polyphonic_envelope_bank.dut.slot_note_off[lane])
      $fatal(1,"bank overlapped lane_tick with lane event");
   end
  end
 end
end
final begin
 if(cycles<100000 || events<10 || ticks<9000)$fatal(1,"empty bank scheduler monitor");
 $display("PASS bank pipeline scheduler contract cycles=%0d events=%0d ticks=%0d",cycles,events,ticks);
end
endmodule
