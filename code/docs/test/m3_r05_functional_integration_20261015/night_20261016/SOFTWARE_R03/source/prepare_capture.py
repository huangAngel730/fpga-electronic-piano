"""Generate an isolated observation-only board/TB; freeze all other R05 inputs."""
import difflib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common import ROOT, DOCS, TB_DIR, identity, sha, write_new
from input_binding import inspect_archive

OUT = DOCS / "night_20261016"
TB = TB_DIR / "night_20261016"
BOARD = ROOT / "code/rtl/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016"


def main():
    data, binding = inspect_archive()
    TB.mkdir(parents=True, exist_ok=True)
    BOARD.mkdir(parents=True, exist_ok=True)
    observer = (TB_DIR / "m3_r05_public_observer.sv").read_bytes()
    # Guard is sampled pre-NBA and blocks X/Z from entering signed JSON fields.
    guard = b'''        if ((^{rst_n,frame_tick,request_accept,request_id,commit_pulse,
            committed_id,committed_left,committed_right,committed_clip,pending_valid,
            play_left,play_right,clip_count,audio_underrun,i2s_bclk,i2s_ws,i2s_din}) === 1'bx)
            $fatal(1,"R05_OBSERVER_UNKNOWN_PUBLIC_PORT");
'''
    needle = b"        // No fabricated accept/first-valid/cancel-handshake."
    assert observer.count(needle) == 1
    observer = observer.replace(needle, guard + needle)
    # X->0 during elaboration is initialization, not a reset-lifetime event.
    observer = observer.replace(b"    always @(negedge rst_n) begin", b"    always @(negedge rst_n) if ($time > 0) begin")
    (TB / "m3_r05_public_observer.sv").write_bytes(observer)
    original = data["inputs/sources/m2_fourvoice_timbre_delay_board_top.sv"]
    candidate = original.replace(b".committed_right(produced_right), .committed_clip()",
                                  b".committed_right(produced_right), .committed_clip(night_committed_clip)")
    assert candidate != original
    insert = b'''
    // NIGHT OBSERVATION ONLY: all taps are direct public module port wires.
    wire night_committed_clip;
    m3_r05_public_observer #(.TRACE_FILE("REAL_CAPTURE.jsonl")) night_observer(
      .clk(core_clk),.rst_n(rst_sync_n),.frame_tick(i2s_frame_tick),
      .request_accept(frame_sample_req),.request_id(sample_req_id),
      .commit_pulse(pcm_valid_q),.committed_id(produced_req_id),
      .committed_left(produced_left),.committed_right(produced_right),
      .committed_clip(night_committed_clip),.pending_valid(pending_valid),
      .play_left(buffered_left),.play_right(buffered_right),
      .clip_count(status_clip_count),.audio_underrun(audio_underrun),
      .i2s_bclk(i2s_bclk),.i2s_ws(i2s_lrck),.i2s_din(i2s_din));
    integer night_input_fd, night_input_cycle=0;
    initial begin
      night_input_fd=$fopen("REAL_INPUTS.jsonl","w");
      if(night_input_fd==0)$fatal(1,"R05_INPUT_FILE_OPEN");
      $fdisplay(night_input_fd,"{\\"kind\\":\\"HEADER\\",\\"schema\\":\\"M3_R05_INPUT_PRE_NBA_V1\\",\\"clock_hz\\":40000000}");
      #0;
      $fdisplay(night_input_fd,"{\\"kind\\":\\"INITIAL_INPUTS\\",\\"time_ns\\":%0d,\\"midi_rx\\":%0d,\\"sys_rst_n\\":%0d}",$time,midi_rx,sys_rst_n);
    end
    always @(posedge core_clk) begin
      night_input_cycle=night_input_cycle+1;
      if ((^{rst_sync_n,midi_rx,shared_event_valid,shared_event_ready,
          shared_event_data,status_active_voice_count,night_config_valid,night_config_ready}) === 1'bx)
        $fatal(1,"R05_INPUT_UNKNOWN_PUBLIC_PORT");
      $fdisplay(night_input_fd,"{\\"kind\\":\\"TICK\\",\\"cycle\\":%0d,\\"time_ns\\":%0d,\\"rst_n\\":%0d,\\"midi_rx\\":%0d,\\"event_valid\\":%0d,\\"event_ready\\":%0d,\\"event_data_hex\\":\\"%016h\\",\\"config_valid\\":%0d,\\"config_ready\\":%0d,\\"active_voice_count\\":%0d}",
          night_input_cycle,$time,rst_sync_n,midi_rx,shared_event_valid,
          shared_event_ready,shared_event_data,night_config_valid,
          night_config_ready,status_active_voice_count);
    end
    // These aliases only export the configuration input/output port wires.
    wire night_config_valid,night_config_ready;
    assign night_config_valid=g_polyphonic.m1_config_pending;
    assign night_config_ready=g_polyphonic.m1_config_ready;
    always @(midi_rx) if ($time > 0) $fdisplay(night_input_fd,"{\\"kind\\":\\"MIDI_EDGE\\",\\"time_ns\\":%0d,\\"value\\":%0d}",$time,midi_rx);
    always @(sys_rst_n) if ($time > 0) $fdisplay(night_input_fd,"{\\"kind\\":\\"RAW_RESET_EDGE\\",\\"time_ns\\":%0d,\\"value\\":%0d}",$time,sys_rst_n);
    final begin
      $fdisplay(night_input_fd,"{\\"kind\\":\\"END\\",\\"cycle\\":%0d}",night_input_cycle);
      $fclose(night_input_fd);
    end
'''
    # Alias config wires within their generate scope; no hierarchical taps.
    insert = insert.replace(b"    assign night_config_valid=g_polyphonic.m1_config_pending;\n", b"")
    insert = insert.replace(b"    assign night_config_ready=g_polyphonic.m1_config_ready;\n", b"")
    candidate = candidate.replace(b"        m2_fourvoice_timbre_delay_frame_core u_audio_core (",
        b"        assign night_config_valid=m1_config_pending;\n        assign night_config_ready=m1_config_ready;\n        m2_fourvoice_timbre_delay_frame_core u_audio_core (")
    assert candidate.count(b"endmodule") == 1
    candidate = candidate.replace(b"endmodule", insert + b"\nendmodule")
    board_path = BOARD / "m2_fourvoice_timbre_delay_board_observed.sv"
    board_path.write_bytes(candidate)
    original_tb = (TB_DIR / "tb_r05_watchdog_7ms.sv").read_bytes()
    tb = original_tb.replace(b"        sys_rst_n=0;#1000;", b'''        // Finish at a complete frame fence. Two core clocks allow that fence
        // to be recorded pre-NBA, then reset cancels the new pending request.
        @(posedge dut.i2s_frame_tick); #50;
        sys_rst_n=0;#1000;''')
    assert original_tb != tb
    tb_path = TB / "tb_r05_observed_7ms.sv"
    tb_path.write_bytes(tb)
    changes = []
    for name, old, new, path in (("BOARD", original, candidate, board_path),
        ("TB", original_tb, tb, tb_path), ("OBSERVER", (TB_DIR / "m3_r05_public_observer.sv").read_bytes(), observer, TB / "m3_r05_public_observer.sv")):
        diff = "".join(difflib.unified_diff(old.decode().splitlines(True), new.decode().splitlines(True), fromfile=name+"_original", tofile=name+"_candidate"))
        (OUT / (name + ".diff")).write_text(diff, encoding="utf-8", newline="\n")
        changes.append({"kind": name, "original_sha256": sha(old), "candidate": identity(path), "diff": identity(OUT / (name + ".diff"))})
    if not (OUT / "INPUT_BINDING.json").exists():
        write_new(OUT / "INPUT_BINDING.json", binding)
    write_new(OUT / "CANDIDATE_CHANGES_R03.json", {"changes": changes, "algorithm_rom_changed": False, "formal_board_changed": False})
    print("PREPARED_CAPTURE_CANDIDATE")


if __name__ == "__main__":
    main()
