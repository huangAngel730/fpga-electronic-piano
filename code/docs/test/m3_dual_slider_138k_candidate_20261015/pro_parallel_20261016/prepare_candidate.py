"""Copy the signed visual wrapper; edit only this new candidate."""
from pathlib import Path
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
OLD = ROOT / "code/rtl/input/m3_dual_slider_138k_candidate_20261015/dual_slider_candidate.sv"
NEW = OLD.parent / "pro_parallel_20261016/dual_slider_pro_parallel.sv"


def main():
    source = OLD.read_text(encoding="utf-8")
    changes = [
        ("module dual_slider_candidate #(", "module dual_slider_pro_parallel #("),
        ("parameter integer BASE_NOTE=36, NOTE_COUNT=49", "parameter integer BASE_NOTE=36, NOTE_COUNT=49, EVENT_FIFO_DEPTH=32"),
        ("input logic accepted_valid,", "input logic accepted_valid,\n    input logic display_event_enable, // diagnostic consumer pause; production tie high"),
        ("output wire sys_reset_done, video_reset_done", """output wire sys_reset_done, video_reset_done,
    output wire [15:0] queue_level, queue_high,
    output wire display_event_fire, score_event_fire, score_sink_ready,
    output audio_defs_pkg::performance_event_t display_event_data,
    output wire [97:0] score_seen_payload"""),
        ("wire [15:0] queue_level,queue_high;", "// Queue watermarks are public diagnostic outputs in this candidate."),
        ("visual_event_bridge #(.DEPTH(8))", "visual_event_bridge #(.DEPTH(EVENT_FIFO_DEPTH))"),
        ("assign video_event_ready=video_reset_done;", """assign video_event_ready=video_reset_done && display_event_enable;
    assign display_event_fire=video_event_valid && video_event_ready;
    assign display_event_data=video_event;
    assign score_event_fire=video_score_valid && video_score_ready;
    assign score_sink_ready=video_score_ready;
    assign score_seen_payload={video_score_id,video_score_note,video_hit_frame,
        video_duration_valid,video_duration,video_velocity};"""),
    ]
    candidate = source
    for before, after in changes:
        if candidate.count(before) != 1:
            raise RuntimeError("AMBIGUOUS_EDIT:" + before)
        candidate = candidate.replace(before, after)
    NEW.parent.mkdir(exist_ok=False)
    with NEW.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(candidate)
    with (HERE / "CANDIDATE.diff").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(difflib.unified_diff(source.splitlines(True), candidate.splitlines(True),
            fromfile=OLD.relative_to(ROOT).as_posix(), tofile=NEW.relative_to(ROOT).as_posix())))
    with (HERE / "COPY_MAP.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump({"original": str(OLD), "original_sha256": hashlib.sha256(OLD.read_bytes()).hexdigest(),
                   "candidate": str(NEW), "candidate_sha256": hashlib.sha256(NEW.read_bytes()).hexdigest(),
                   "formal_geometry_successor": "BLOCKED_INPUT_NOT_FOUND"}, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
