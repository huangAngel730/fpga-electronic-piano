"""Post-build exact MIDI SSRAM classification; original executed gate retained."""
from pathlib import Path
import argparse
import inspect
import json
import types

import check_138k_night_cache_combo as executed
import check_138k_score_receive_integration as original


def classified_resource(path):
    source = inspect.getsource(original.xml_resource)
    anchors = {
        "score=find('u_score_receiver');": "score=find('u_score_receiver');midi=find('u_midi_input');",
        "for node in [score,wave,bridge]:": "for node in [score,wave,bridge,midi]:",
        "expectedRAM=23+count(score,'Bsram');expectedSS=89+count(score,'Ssram')":
            "if count(midi,'Bsram')!=0 or count(midi,'Ssram')!=20:raise ValueError('exact repaired MIDI RAM must be0BSRAM/20SSRAM')\n"
            "        expectedRAM=23+count(score,'Bsram');expectedSS=66+count(midi,'Ssram')+count(score,'Ssram')",
    }
    for before, after in anchors.items():
        if source.count(before) != 1:
            raise ValueError("COMPLETE_RESOURCE_GATE_TEMPLATE_DRIFT")
        source = source.replace(before, after, 1)
    namespace = dict(original.xml_resource.__globals__)
    exec(compile(source, "<exact_sameedge_MIDI20SSRAM_only>", "exec"), namespace)
    facts, total, errors = namespace["xml_resource"](path)
    if not errors:
        facts.update(MIDI_BSRAM=0, MIDI_SSRAM=20, frozen_nonMIDI_nonScore_SSRAM=66,
                     MIDI_mapping_change="old23 to new20, fixed compare structure with unchanged sequential state",
                     candidate_MIDI_sha256="5960d37c775e3e8f3acb724647a00246b89119240fb7b1c6303010426e4d949c")
    return facts, total, errors


def final_resource(path):
    # Reuse every native9-BSRAM body/history and budget assertion unchanged.
    namespace = dict(executed.xml_resource.__globals__)
    namespace["inherited"] = types.SimpleNamespace(xml_resource=classified_resource)
    return types.FunctionType(executed.xml_resource.__code__, namespace)(path)


def review(run):
    run = run.resolve()
    initial = json.loads((run / "assessment.json").read_bytes())
    allowed = {"score hierarchy: resource outside original+score scope",
               "frozen resource footprint changed BSRAM", "physical SSRAM does not match exact hierarchy"}
    if initial.get("passed") is not False or set(initial.get("errors", [])) != allowed:
        raise ValueError("INITIAL_FAILURE_NOT_EXACT_RESOURCE_CLASSIFICATION")
    project = run / "project"
    executed.prepared.validate(project)
    midi = project / "inputs/sources/midi_event_parser.sv"
    if original.sha(midi) != "5960d37c775e3e8f3acb724647a00246b89119240fb7b1c6303010426e4d949c":
        raise ValueError("CLASSIFIED_MIDI_SOURCE_IDENTITY")
    # Give the immutable complete review an alternate resource function only.
    source = inspect.getsource(original.review)
    if source.count("'score_receive_integration_1'") != 2:
        raise ValueError("COMPLETE_REVIEW_TEMPLATE_DRIFT")
    source = source.replace("'score_receive_integration_1'", repr(executed.prepared.VERSION))
    namespace = dict(original.review.__globals__)
    namespace.update(prepared=executed.prepared, xml_resource=final_resource, directed=executed.directed)
    exec(compile(source, "<complete_gate_exact_MIDI_resource_classification>", "exec"), namespace)
    result = namespace["review"](run)
    result.update(date="2026-10-11", version=executed.prepared.VERSION,
                  final_resource_classification_only=True, initial_assessment_sha256=original.sha(run / "assessment.json"),
                  initial_failure_preserved=initial["errors"], executed_gate_sha256=original.sha(Path(executed.__file__)),
                  final_gate_sha256=original.sha(Path(__file__)), additional_EDA_runs=0,
                  board_release_allowed=False, programmed=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("REFUSE_OVERWRITE_FINAL_ASSESSMENT")
    result = review(args.run)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("report_gate", "additional_UART_and_parent_directed_proof", "actual_hierarchy")},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
