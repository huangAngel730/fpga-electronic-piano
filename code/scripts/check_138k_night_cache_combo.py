"""Full inherited board/timing gate plus exact new-cache resources/Hold proof."""
from pathlib import Path
import argparse
import inspect
import json
import math
import re
import xml.etree.ElementTree as ET

import prepare_138k_night_cache_combo as prepared
import check_138k_score_receive_integration as inherited


def xml_resource(path):
    facts, total, errors = inherited.xml_resource(path)
    if errors:
        return facts, total, errors
    try:
        root = ET.parse(path).getroot()
        scores = [n for n in root.iter() if n.get("name") == "u_score_receiver"]
        if len(scores) != 1 or facts["score_actual_BSRAM"] != 9 or facts["score_actual_SSRAM"] != 0:
            raise ValueError("EXACT_SCORE9_BSRAM_NO_SSRAM")
        score = scores[0]
        mapping = {}
        for name in [f"byte_lanes[{i}].storage" for i in range(8)] + ["request_history"]:
            nodes = [n for n in score.iter() if n.get("name", "").split("/")[-1] == name]
            if len(nodes) != 1:
                raise ValueError("BODY_OR_HISTORY_HIERARCHY_MISSING:" + name)
            count = nodes[0].get("T_Bsram", nodes[0].get("Bsram", "0"))
            if not re.fullmatch(r"1(?:\(1\))?", count):
                raise ValueError("BODY_OR_HISTORY_NOT_ONE_NATIVE_BSRAM:" + name)
            mapping[name] = dict(nodes[0].attrib)
        if facts["score_actual_registers"] > 8192 or facts["score_actual_LUT"] > 8192:
            raise ValueError("PRELIMINARY_SCORE_BUDGET")
        facts.update(new_cache_native_mapping=mapping, body_BSRAM=8, history_BSRAM=1)
    except (OSError, ValueError, ET.ParseError) as error:
        errors.append("new cache resource: " + str(error))
    return facts, total, errors


def directed(timing, usage, sdc, expected_ss):
    commands = json.loads((prepared.repair.SCOPE / "revision_manifest.json").read_bytes())["additional_hold_sdc_commands"]
    normal = lambda value: {re.sub(r"\s+", " ", line.strip()) for line in value.splitlines()
                           if line.strip() and not line.lstrip().startswith("#")}
    old = (inherited.original.prepared.SCOPE / "audio_visual_hold055.sdc").read_text(encoding="utf-8")
    errors = []
    if normal(sdc) != normal(old) | set(inherited.exact_extra_commands()) | set(commands):
        errors.append("exact complete old SDC plus three directed Hold commands mismatch")
    # Check all original UART/local tables unchanged, while separately requiring
    # the only three additional commands and their own reports to be active.
    old_sdc = "\n".join(line for line in sdc.splitlines() if line.strip() not in commands)
    old_errors, proof = inherited.directed(timing, usage, old_sdc, expected_ss)
    errors.extend(old_errors)
    rows = inherited.original.baseline_gate.parsed(timing)
    active = [row[2] for section, row in rows if section == "SDC_Report" and len(row) == 3 and row[1] == "Actived"]
    for command in commands:
        if active.count(command) != 1:
            errors.append("additional directed Hold command missing or duplicate: " + command)
    for command in commands[1:]:
        match = re.fullmatch(r"report_timing -(setup|hold) -from \[get_regs \{(.+)\}\] -to \[get_regs \{(.+)\}\] -max_paths 1", command)
        if match is None:
            errors.append("directed command syntax")
            continue
        kind, start, stop = match.groups()
        typed = [x for x in active if x.startswith("report_timing -" + kind + " ")]
        if command not in typed:
            continue
        name = kind.capitalize() + "_Slack_Table" + str(typed.index(command) + 1)
        paths = [row for section, row in rows if section == name and len(row) >= 9 and row[0].isdigit()]
        if (len(paths) != 1 or paths[0][2] != start + "/Q" or paths[0][3] != stop + "/D"
                or not math.isfinite(float(paths[0][1])) or float(paths[0][1]) < 0):
            errors.append("new exact PitchMod own-table path missing/negative: " + name)
        proof["new_combo_" + name] = paths
    return errors, proof


def review(run):
    source = inspect.getsource(inherited.review)
    if source.count("'score_receive_integration_1'") != 2:
        raise ValueError("INHERITED_COMPLETE_GATE_TEMPLATE_DRIFT")
    namespace = dict(inherited.review.__globals__)
    namespace.update(prepared=prepared, xml_resource=xml_resource, directed=directed)
    source = source.replace("'score_receive_integration_1'", repr(prepared.VERSION))
    exec(compile(source, "<complete_board_gate_newcache_MIDI_Hold>", "exec"), namespace)
    try:
        result = namespace["review"](run)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        result = {"passed": False, "errors": ["INVALID_OR_INCOMPLETE_COMBO_BUILD:" + str(error)]}
    result.update(date="2026-10-10", version=prepared.VERSION,
                  inherited_gate_sha256=inherited.sha(Path(inherited.__file__)),
                  checker_sha256=inherited.sha(Path(__file__)),
                  scope="exact new-cache plus same-edge MIDI plus directed Hold; original complete gates retained",
                  board_release_allowed=False, programmed=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    result = review(parser.parse_args().run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
