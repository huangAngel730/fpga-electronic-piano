"""Coordinator-approved startup sidecars, observation-only final candidate."""
import difflib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from common import ROOT, DOCS, TB_DIR, identity, write_new

OUT = DOCS / "night_20261016/RESUME_R01"
BO = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016/RESUME_R01/FIX_01/m2_fourvoice_timbre_delay_board_observed.sv"
BN = BO.parent.parent / "FIX_02" / BO.name
BN.parent.mkdir(exist_ok=False)
OBSERVER = TB_DIR / "night_20261016/RESUME_R01/FIX_02/m3_r05_public_observer.sv"
s = BO.read_text(encoding="utf-8")
controls = '''    reg night_capture_enabled=0;
    wire night_can_start = (rst_sync_n===1'b0) &&
      ((^{rst_sync_n,i2s_frame_tick,frame_sample_req,sample_req_id,pcm_valid_q,
          produced_req_id,produced_left,produced_right,night_committed_clip,pending_valid,
          buffered_left,buffered_right,status_clip_count,audio_underrun,
          i2s_bclk,i2s_lrck,i2s_din,midi_rx,shared_event_valid,shared_event_ready,
          shared_event_data,status_active_voice_count,night_config_valid,night_config_ready}) !== 1'bx);
    wire night_capture_active = night_capture_enabled || night_can_start;
    always @(posedge core_clk) if(night_can_start) night_capture_enabled<=1;
'''
anchor = '    m3_r05_public_observer #(.TRACE_FILE("REAL_CAPTURE.jsonl")) night_observer('
assert s.count(anchor) == 1
s = s.replace(anchor, controls + anchor)
s = s.replace('      .clk(core_clk),.rst_n(rst_sync_n),.frame_tick(i2s_frame_tick),', '      .clk(core_clk),.rst_n(rst_sync_n),.capture_enable(night_capture_active),.frame_tick(i2s_frame_tick),')
s = s.replace('    integer night_input_fd, night_input_cycle=0;', '    integer night_input_fd, night_input_cycle=0, night_start_input_fd, night_absolute_cycle=0, night_start_input_cycle=0;')
anchor = '      #0;'
initial = r'''      night_start_input_fd=$fopen("STARTUP_INPUTS.jsonl","w");
      if(night_start_input_fd==0)$fatal(1,"R05_STARTUP_INPUT_FILE_OPEN");
      $fdisplay(night_start_input_fd,"{\"kind\":\"HEADER\",\"schema\":\"M3_R05_STARTUP_INPUT_BINARY_V1\",\"clock_hz\":40000000}");
'''
assert s.count(anchor) == 1
s = s.replace(anchor, initial + anchor)
begin = '    always @(posedge core_clk) begin\n      night_input_cycle=night_input_cycle+1;'
prefix = r'''    always @(posedge core_clk) begin
      night_absolute_cycle=night_absolute_cycle+1;
      if(!night_capture_active) begin
        night_start_input_cycle=night_start_input_cycle+1;
        $fdisplay(night_start_input_fd,"{\"kind\":\"STARTUP_TICK\",\"absolute_cycle\":%0d,\"time_ps\":%0d,\"rst_n\":\"%b\",\"midi_rx\":\"%b\",\"event_valid\":\"%b\",\"event_ready\":\"%b\",\"event_data_binary\":\"%b\",\"config_valid\":\"%b\",\"config_ready\":\"%b\",\"active_voice_count\":\"%b\"}",
          night_absolute_cycle,longint'($realtime*1000.0),rst_sync_n,midi_rx,
          shared_event_valid,shared_event_ready,shared_event_data,night_config_valid,
          night_config_ready,status_active_voice_count);
        if(night_absolute_cycle>=64)$fatal(1,"R05_STARTUP_OVER_64_EDGES");
        if((rst_sync_n && shared_event_valid && shared_event_ready)===1'b1)
          $fatal(1,"R05_BUSINESS_ACCEPTED_BEFORE_CAPTURE");
      end else begin
      night_input_cycle=night_input_cycle+1;'''
assert s.count(begin) == 1
s = s.replace(begin, prefix)
anchor = '    end\n    // These aliases only export'
assert s.count(anchor) == 1
s = s.replace(anchor, '      end\n' + anchor)
anchor = '      $fclose(night_input_fd);'
tail = r'''      $fdisplay(night_start_input_fd,"{\"kind\":\"END\",\"absolute_edges\":%0d}",night_start_input_cycle);
      $fclose(night_start_input_fd);
'''
s = s.replace(anchor, tail + anchor)
BN.write_text(s, encoding="utf-8", newline="\n")
changes = json.loads((OUT / "CANDIDATE_CHANGES_FIX01.json").read_text(encoding="utf-8"))
for kind, old, new in (("BOARD", BO, BN), ("OBSERVER", TB_DIR / "night_20261016/RESUME_R01/m3_r05_public_observer.sv", OBSERVER)):
    diff = OUT / (kind + "_FIX02.diff")
    diff.write_text("".join(difflib.unified_diff(old.read_text(encoding="utf-8").splitlines(True), new.read_text(encoding="utf-8").splitlines(True),
        fromfile="prior_observation", tofile="startup_segment_observation")), encoding="utf-8", newline="\n")
    for row in changes["changes"]:
        if row["kind"] == kind:
            row["candidate"] = identity(new)
            row["diff"] = identity(diff)
write_new(OUT / "CANDIDATE_CHANGES_FIX02.json", changes)
runner = (HERE / "run_capture_fix01.py").read_text(encoding="utf-8")
runner = runner.replace('RESUME_R01/FIX_01/m2_fourvoice_timbre_delay_board_observed.sv', 'RESUME_R01/FIX_02/m2_fourvoice_timbre_delay_board_observed.sv')
runner = runner.replace('RESUME_R01/m3_r05_public_observer.sv', 'RESUME_R01/FIX_02/m3_r05_public_observer.sv')
runner = runner.replace('CANDIDATE_CHANGES_FIX01.json', 'CANDIDATE_CHANGES_FIX02.json')
runner = runner.replace('for name in ("REAL_CAPTURE.jsonl", "REAL_INPUTS.jsonl"):', 'for name in ("REAL_CAPTURE.jsonl", "REAL_INPUTS.jsonl", "STARTUP_CAPTURE.jsonl", "STARTUP_INPUTS.jsonl", "STARTUP_BOUNDARY_RAW.json"):')
runner = runner.replace(' + [BOARD]\n', ' + [BOARD, TB_DIR / "night_20261016/RESUME_R01/FIX_02/m3_r05_public_observer.sv"]\n')
(HERE / "run_capture_fix02.py").write_text(runner, encoding="utf-8", newline="\n")
write_new(OUT / "FIX02_RECEIPT.json", {"status": "STATIC_FINAL_CANDIDATE_NOT_EXECUTED", "contract": identity(OUT / "CAPTURE_INTERFACE.md"),
    "board": identity(BN), "observer": identity(OBSERVER), "runner": identity(HERE / "run_capture_fix02.py"),
    "algorithm_rom_clock_modified": False, "functional_groups_already_consumed": 2, "remaining": 1})
print("FIX02_SEGMENTED_RAW_STARTUP_PREPARED")
