"""Strict final v3 profile with dedicated-table proofs; no design/build mutation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import check_138k_waveform_integration_v3_reset_profile as parent


def dedicated_paths(rows):
    manifest = json.loads((parent.executed.prepared.SCOPE / "revision_manifest.json").read_bytes())
    active = [r[2] for section, r in rows if section == "SDC_Report" and len(r) == 3 and r[1] == "Actived"]
    errors = []
    facts = {}
    for command in manifest["additional_reports"]:
        match = re.fullmatch(r"report_timing -(setup|hold) -from \[get_regs \{(.+)\}\] -to \[get_regs \{(.+)\}\] -max_paths 1", command)
        if match is None:
            errors.append("invalid expected dedicated command")
            continue
        kind, start, stop = match.groups()
        commands = [x for x in active if x.startswith("report_timing -" + kind + " ")]
        if commands.count(command) != 1:
            errors.append("missing/duplicate dedicated Active command " + command)
            continue
        table = kind.capitalize() + "_Slack_Table" + str(commands.index(command) + 1)
        paths = [r for section, r in rows if section == table and len(r) >= 4 and r[0].isdigit()]
        if (len(paths) != 1 or paths[0][2] != start + "/Q" or paths[0][3] != stop + "/D"
                or not math.isfinite(float(paths[0][1])) or float(paths[0][1]) < 0):
            errors.append("dedicated own-table path invalid: " + table)
        facts[table] = paths
    return errors, facts


def review(run):
    result = parent.review(run)
    path = run.resolve() / "project/impl/pnr/audio_visual_coexistence_top_tr_content.html"
    errors, facts = dedicated_paths(parent.executed.baseline_gate.parsed(path.read_text(encoding="utf-8")))
    result["errors"].extend(errors)
    result["dedicated_local_report_tables"] = facts
    result["passed"] = not result["errors"]
    result["post_build_profile"] = "v3_reset_classification_2_dedicated_tables"
    result["post_build_checker_SHA256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["first_reset_profile_checker_SHA256"] = hashlib.sha256(Path(parent.__file__).read_bytes()).hexdigest()
    result["board_release_allowed"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    result = review(args.run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
