"""New exact combo simulation with independently frozen MIDI/display reference."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import prepare_138k_night_cache_combo as prepared
import run_138k_score_bram_integration_sim as parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--negative", choices=("audio_isolation", "video_isolation", "response_command"))
    args = parser.parse_args()
    project = args.project.resolve()
    prepared.validate(project)
    old = prepared.base.parent.inputs(project)[0]
    reference_parser = old["sources/midi_event_parser.sv"]
    reference_midi = old["sources/midi_input.sv"]
    assert reference_parser.count(b"module midi_event_parser #(") == 1
    assert reference_midi.count(b"module midi_input #(") == 1
    assert reference_midi.count(b"midi_event_parser #(") == 1
    reference_parser = reference_parser.replace(b"module midi_event_parser #(", b"module reference_midi_event_parser #(", 1)
    reference_midi = reference_midi.replace(b"module midi_input #(", b"module reference_midi_input #(", 1)
    reference_midi = reference_midi.replace(b"midi_event_parser #(", b"reference_midi_event_parser #(", 1)
    original_syntax = parent.syntax_copy
    reference_display = (project / "inputs/sources/audio_visual_display_probe.sv").read_bytes()

    def isolate_reference(name, raw):
        if name != "reference_audio_visual_top.sv":
            return original_syntax(name, raw)
        if raw.count(b"midi_input #(") != 1:
            raise ValueError("REFERENCE_MIDI_INSTANCE_ANCHOR")
        raw = raw.replace(b"midi_input #(", b"reference_midi_input #(", 1)
        raw = original_syntax(name, raw)
        raw += b"\n" + original_syntax("reference_midi.sv", reference_midi)
        raw += b"\n" + original_syntax("reference_parser.sv", reference_parser)
        if args.negative == "video_isolation":
            token = b"audio_visual_display_probe #"
            if raw.count(token) != 1:
                raise ValueError("REFERENCE_DISPLAY_INSTANCE_ANCHOR")
            raw = raw.replace(token, b"reference_audio_visual_display_probe #", 1)
            display = reference_display.replace(b"module audio_visual_display_probe", b"module reference_audio_visual_display_probe", 1)
            raw += b"\n" + original_syntax("reference_display.sv", display)
        return raw

    execution_sources = {str(Path(__file__).resolve()): parent.sha(Path(__file__)),
                         str(Path(prepared.__file__).resolve()): parent.sha(Path(prepared.__file__)),
                         str(Path(parent.__file__).resolve()): parent.sha(Path(parent.__file__))}
    old_prepare = parent.prepare
    old_args = sys.argv[:]
    parent.prepare = prepared
    parent.syntax_copy = isolate_reference
    sys.argv = [parent.__file__, "--project", str(project), "--output", str(args.output)]
    if args.negative:
        sys.argv += ["--negative", args.negative]
    try:
        code = parent.main()
    finally:
        parent.prepare = old_prepare
        parent.syntax_copy = original_syntax
        sys.argv = old_args
    receipt = args.output.resolve() / "receipt.json"
    result = json.loads(receipt.read_bytes())
    result["scope"] = "exact newcache + MIDIrepair + directedHold combo; frozen reference MIDI independently defined"
    result["source_SHA256"].update(execution_sources)
    result["isolated_reference"] = {"MIDI_wrapper_and_parser_distinct": True,
        "reference_parser_original_sha256": hashlib.sha256(old["sources/midi_event_parser.sv"]).hexdigest(),
        "reference_midi_original_sha256": hashlib.sha256(old["sources/midi_input.sv"]).hexdigest(),
        "video_reference_distinct_when_mutated": args.negative == "video_isolation"}
    if any(parent.sha(Path(path)) != value for path, value in execution_sources.items()):
        result.update(passed=False, error="COMBO_EXECUTION_SOURCE_CHANGED")
        code = 1
    receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
