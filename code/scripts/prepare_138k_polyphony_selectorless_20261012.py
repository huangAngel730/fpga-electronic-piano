"""Prepare-only minimal selector-removal successor; NEVER executes EDA.

The user's one allowed attempt failed before synthesis. A future attempt needs
new authorization. Keep V0282 project, original failed attempt and their receipts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

import prepare_138k_polyphony_resource as original

SOURCE = original.ROOT / "code/build/138k_polyphony_resource/prepared/N32_R1_20261011_01"
DEST = original.ROOT / "code/build/138k_polyphony_resource/selectorless_20261012_01"
FROZEN_SHA = "883297182d9705788d5d04855b597ad8620ab2b1b8ca38727a8b06492a0454e9"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def expected():
    record=original.verify(SOURCE)
    if sha((SOURCE/"frozen_receipt.json").read_bytes())!=FROZEN_SHA:
        raise ValueError("ORIGINAL_FROZEN_DRIFT")
    data=(SOURCE/"run_synthesis_only.tcl").read_text("ascii")
    selector="set_option -synthesis_tool GowinSynthesis\n"
    if data.count(selector)!=1:
        raise ValueError("EXACT_SINGLE_REJECTED_SELECTOR_REQUIRED")
    adapted=data.replace(selector,"")
    oldcd="cd {"+SOURCE.as_posix()+"}"
    oldopen="open_project {"+(SOURCE/original.PROJECT).as_posix()+"}"
    newcd="cd {"+DEST.as_posix()+"}"
    newopen="open_project {"+(DEST/original.PROJECT).as_posix()+"}"
    if adapted.count(oldcd)!=1 or adapted.count(oldopen)!=1:
        raise ValueError("EXACT_PATH_ANCHORS")
    adapted=adapted.replace(oldcd,newcd).replace(oldopen,newopen)
    reverse=adapted.replace(newcd,oldcd).replace(newopen,oldopen)
    if reverse!=data.replace(selector,""):
        raise ValueError("NONREVERSIBLE_LOCATION_CHANGE")
    commands=[s.strip() for s in adapted.splitlines() if s.strip()]
    if commands[-1]!="run syn" or any("run all" in x or "run pnr" in x for x in commands):
        raise ValueError("SYNTHESIS_ONLY_COMMANDS")
    project=(SOURCE/original.PROJECT).read_bytes()
    listing=ET.fromstring(project).find("FileList")
    for f in listing:
        path=Path(f.attrib["path"]).resolve()
        if not path.is_relative_to(SOURCE.resolve()) or not path.is_file():
            raise ValueError("GPRJ_SOURCE_REDIRECT")
    payload={original.PROJECT:project,"run_synthesis_only.tcl":adapted.encode("ascii")}
    report=dict(schema=1,status="PREPARED_NOT_AUTHORIZED_NOT_SYNTHESIZED",
        original_project=str(SOURCE),successor_project=str(DEST),configuration=record["configuration"],
        original_frozen_sha256=FROZEN_SHA,tool=record["tool"],
        source_ROM_include_SDC_files_unchanged=True,old_GPRJ_bytes_unchanged=True,
        source_paths_refer_to_original_readonly_inputs=True,
        semantic_changes=["Remove only rejected set_option -synthesis_tool GowinSynthesis"],
        reversible_location_changes=["cd","open_project copied GPRJ"],
        source_algorithm_changes=0,real_new_tool_runs=0,
        synthesis_authorized=False,physical_resources="UNKNOWN",physical_STA="NOT_RUN",
        automatic_retry=False,requires_new_user_authorization=True,
        original_failed_attempt_preserved=True,device_operation=False,
        preparation_script_sha256=sha(Path(__file__).read_bytes()),
        artifacts={n:dict(bytes=len(b),sha256=sha(b)) for n,b in payload.items()})
    return payload,report


def verify():
    payload,report=expected()
    actual={p.name for p in DEST.iterdir() if p.is_file()}
    if actual!=set(payload)|{"repair_receipt.json"} or any(p.is_dir() for p in DEST.iterdir()):
        raise ValueError("EXACT_SUCCESSOR_FILE_SET")
    for n,b in payload.items():
        if (DEST/n).read_bytes()!=b:
            raise ValueError("SUCCESSOR_INPUT_SHA:"+n)
    if (DEST/"repair_receipt.json").read_bytes()!=original.canonical(report):
        raise ValueError("SUCCESSOR_CANONICAL_RECEIPT")
    return report


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check",action="store_true")
    a=cli.parse_args()
    try:
        if not a.check:
            if DEST.exists(): raise ValueError("REFUSE_EXISTING_SUCCESSOR")
            payload,report=expected()
            DEST.mkdir(parents=True,exist_ok=False)
            for n,b in payload.items():
                with (DEST/n).open("xb") as f:f.write(b)
            with (DEST/"repair_receipt.json").open("xb") as f:f.write(original.canonical(report))
        r=verify()
        print(json.dumps(dict(status=r["status"],semantic_changes=r["semantic_changes"],
                             real_new_tool_runs=0,authorized=False),ensure_ascii=False))
        return 0
    except (OSError,ValueError,subprocess.SubprocessError) as e:
        print(json.dumps(dict(status="REJECT",diagnostic=str(e)),ensure_ascii=False))
        return 1


if __name__=="__main__":raise SystemExit(main())
