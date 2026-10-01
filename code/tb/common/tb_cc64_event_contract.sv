module tb_cc64_public;
 import audio_defs_pkg::*;
 import sustain_control_contract_pkg::*;
 performance_event_t ev;
 integer v,src,ch,checks=0;
 initial begin
  if($bits(performance_event_t)!=64 || CTRL_SUSTAIN!=6)$fatal(1,"ID/width");
  for(v=0;v<128;v++)begin
   if(midi_cc_to_12bit(v[6:0])!==sustain_value_from_midi(v[6:0]))$fatal(1,"contract mapping");
   if((midi_cc_to_12bit(v[6:0])>=2048)!=(v>=64))$fatal(1,"threshold");
   for(src=0;src<16;src++)for(ch=0;ch<16;ch++)begin
    ev=make_sustain_event(src[3:0],ch[3:0],v[6:0]);
    if(ev.event_type!=EVENT_CONTROL_CHANGE || ev.control_id!=6 || ev.source_id!=src || ev.channel!=ch || ev.control_value!=((v<<5)|(v>>2)) || ev.note_number || ev.velocity || ev.expression || ev.reserved)$fatal(1,"event mismatch");
    checks++;
   end
  end
  ev=make_note_event(1,2,3,60,0);
  if(ev.event_type!=EVENT_NOTE_OFF || midi_velocity_to_10bit(127)!=1023 || midi_bend_to_12bit(8192)!=0 || midi_bend_to_12bit(0)!=-2048 || midi_bend_to_12bit(16383)!=2047)$fatal(1,"existing behavior changed");
  $display("PASS CC64 public events=%0d mappings=128 source_channels=256 old_note_pitch_rules=PASS",checks);$finish;
 end
endmodule
