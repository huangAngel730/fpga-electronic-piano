"""Read-only exact RAM physical gate; inherits every original board/timing gate."""
from pathlib import Path
import argparse
import inspect
import json
import re
import xml.etree.ElementTree as ET

import prepare_138k_score_bram_integration as prepared
import check_138k_score_receive_integration as parent


def xml_resource(path):
    facts, total, errors = parent.xml_resource(path)
    if errors:
        return facts, total, errors
    try:
        root = ET.parse(path).getroot()
        score = [n for n in root.iter() if n.attrib.get("name") == "u_score_receiver"]
        if len(score) != 1:
            raise ValueError("EXACT_SCORE_HIERARCHY")
        if facts["score_actual_BSRAM"] != 8 or facts["score_actual_SSRAM"] != 0:
            raise ValueError("EXACT8_BODY_BSRAM_NO_SSRAM")
        if (facts["score_actual_registers"] > 8192 or facts["score_actual_LUT"] > 8192):
            raise ValueError("SCORE_PRELIMINARY_RESOURCE_BUDGET")
        lanes = {}
        for i in range(8):
            suffix = f"byte_lanes[{i}].storage"
            nodes = [n for n in score[0].iter()
                     if n.attrib.get("name", "").split("/")[-1] == suffix]
            if len(nodes) != 1:
                raise ValueError("MISSING_OR_DUPLICATE_BODY_LANE:" + suffix)
            count = nodes[0].attrib.get("T_Bsram", nodes[0].attrib.get("Bsram", "0"))
            if not re.fullmatch(r"1(?:\(1\))?", count):
                raise ValueError("BODY_LANE_NOT_ONE_BSRAM:" + suffix)
            lanes[suffix] = dict(nodes[0].attrib)
        facts.update(body_BSRAM_lanes=lanes, preliminary_budget_not_device_capacity=True)
    except (OSError, ValueError, ET.ParseError) as error:
        errors.append("RAM body mapping: " + str(error))
    return facts, total, errors


def review(run):
    # Preserve the old review's complete checks and only bind the new prepared
    # scope/version and the stricter native body-RAM hierarchy requirement.
    source = inspect.getsource(parent.review)
    old_version = "'score_receive_integration_1'"
    if source.count(old_version) != 2:
        raise ValueError("INHERITED_REVIEW_VERSION_TEMPLATE_DRIFT")
    source = source.replace(old_version, repr(prepared.VERSION))
    namespace = dict(parent.review.__globals__)
    namespace.update(prepared=prepared, xml_resource=xml_resource)
    exec(compile(source, "<RAM_exact_scope_original_complete_physical_review>", "exec"), namespace)
    try:
        result = namespace["review"](run)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as error:
        result = {"passed": False, "errors": ["INVALID_OR_INCOMPLETE_BUILD:" + str(error)]}
    result.update(date="2026-10-10", version=prepared.VERSION,
                  inherited_gate_sha256=parent.sha(Path(parent.__file__)),
                  checker_sha256=parent.sha(Path(__file__)),
                  scope="new exact RAM fulltop; complete inherited timing/CDC/reset/pin gates retained",
                  board_release_allowed=False, programmed=False)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    result = review(parser.parse_args().run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
