"""Run a fresh commercial implementation, snapshotting all inputs and exits."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import time
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GOWIN = Path("D:/program/Gowin_work/Gowin/Gowin_V1.9.12.04_x64/IDE/bin/gw_sh.exe")

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def preflight():
    """Read-only path/flow closure. No compiler, EDA or device subprocess."""
    project = ROOT / "project"
    assert not list(project.rglob("*.pr")), "Old physical seed forbidden"
    assert not (ROOT / "pnr_reference").exists(), "Old reference forbidden"
    options = (ROOT / "options.tcl").read_text(encoding="utf-8")
    rebuild = (ROOT / "rebuild.tcl").read_text(encoding="utf-8")
    assert "run all" in rebuild and "run pnr" not in rebuild
    assert "open_project" not in rebuild
    assert "create_project -name pro_audio" in rebuild
    assert "GW5AST-LV138FPG676AC1/I0 -device_version C" in rebuild
    assert "set_option -inc_place 0" in options and "set_option -inc_pnr 0" in options
    assert not re.search(r"set_option\s+-\S*(?:copy|seed|reference)\S*", options, re.I)
    cfg = json.loads((project / "impl/pro_audio_process_config.json").read_text())
    assert cfg["INCREMENTAL_PLACE_AND_ROUTING"] == "0"
    assert cfg["INCREMENTAL_PLACE_ONLY"] == "0" and cfg["Incremental_Compile"] == ""
    registrations = []
    for element in ET.parse(project / "pro_audio.gprj").findall(".//File"):
        rel = element.attrib["path"]
        f = project / rel
        assert not Path(rel).is_absolute() and ":" not in rel
        assert f.resolve().is_relative_to(project.resolve()) and f.is_file(), rel
        registrations.append(rel)
    tcl_sources = []
    for raw in re.findall(r"add_file -type \w+ \[file join \$package_root ([^\]]+)\]", rebuild):
        rel = raw.strip("{} ").replace(" ", "/")
        assert (ROOT / rel).is_file(), rel
        tcl_sources.append(rel.removeprefix("project/"))
    assert set(tcl_sources) == set(registrations), "Tcl and GUI source registration differ"
    include_dirs = [project / p for p in cfg["IncludePath"]]
    assert all(x.is_dir() and x.resolve().is_relative_to(project.resolve()) for x in include_dirs)
    includes = []
    roms = set()
    for rel in registrations:
        p = project / rel
        if p.suffix not in (".sv", ".v", ".vh", ".svh"):
            continue
        text = p.read_text(encoding="utf-8")
        for name in re.findall(r'`include\s+"([^"]+)"', text):
            hits = [q / name for q in [p.parent] + include_dirs if (q / name).is_file()]
            assert hits, name
            includes.append({"consumer": rel, "include": name, "resolved": hits[0].relative_to(ROOT).as_posix()})
        for name in re.findall(r'"([^"\n]+\.(?:mem|hex))"', text):
            assert (project / name).is_file(), name
            roms.add(name)
    return {"status": "PASS_STATIC_ONLY", "registered_files": len(registrations),
            "tcl_GUI_registration_set_equal": True, "include_resolutions": includes,
            "ROM_literals_resolved": sorted(roms), "old_seed_count": 0,
            "incremental_or_copy_flow": False, "EDA_invocations": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--snapshot-only", action="store_true", help="Static preflight and immutable input snapshot only; never launch EDA")
    args = parser.parse_args()
    if not args.name.replace("_", "").isalnum():
        parser.error("fresh simple evidence name required")
    checks = preflight()
    out = ROOT / "evidence" / args.name
    out.mkdir(exist_ok=False)
    paths = [p for folder in ("src", "ip", "include", "rom") for p in (ROOT / "project" / folder).rglob("*") if p.is_file()]
    paths += list(ROOT.glob("*.tcl")) + list((ROOT / "project").glob("*.*")) + [Path(__file__)]
    paths += list((ROOT / "project/impl").rglob("*.json"))
    identities = {p: sha(p) for p in paths}
    record = {"status": "RUNNING", "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "tool": str(GOWIN), "tool_sha256": sha(GOWIN), "device": "GW5AST-LV138FPG676AC1/I0", "stepping": "C", "source_sha256": {p.relative_to(ROOT).as_posix(): h for p,h in identities.items()}, "device_operations": False}
    def save():
        (out / "receipt.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    save()
    for p in paths:
        dest = out / "inputs" / p.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        if sha(dest) != identities[p]:
            raise RuntimeError("source changed while snapshotting")
    env = dict(os.environ)
    env["PRO_EXTENSION_BUILD_DIR"] = str(out / "gowin")
    env.pop("PRO_EXTENSION_SYNTHESIS_INPUT", None)
    record["static_preflight"] = checks
    record["flow"] = "FRESH_FULL_COMMERCIAL_RUN_ALL_NO_REUSE"
    if args.snapshot_only:
        record["status"] = "STATIC_SNAPSHOT_ONLY_NO_EDA"
        record["executed_inputs_unchanged"] = all(sha(p)==h for p,h in identities.items())
        save()
        print(record["status"], "inputs", len(identities), flush=True)
        return 0
    entry = ROOT / "rebuild.tcl"
    cmd = [str(GOWIN), str(entry)]
    record["argv"] = cmd
    begin = time.monotonic()
    try:
        with (out / "stdout.log").open("wb") as stdout, (out / "stderr.log").open("wb") as stderr:
            process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
            code = process.wait()
        record["exit_code"] = code
        record["elapsed_seconds"] = time.monotonic()-begin
        record["status"] = "TOOL_COMPLETED_UNREVIEWED" if code == 0 else "FAIL"
        record["executed_inputs_unchanged"] = all(sha(p)==h for p,h in identities.items())
        if not record["executed_inputs_unchanged"]:
            record["status"] = "FAIL"
        record["ended_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save()
        print(record["status"], "exit", code, flush=True)
        return int(record["status"] != "TOOL_COMPLETED_UNREVIEWED")
    except Exception as error:
        record["status"] = "FAIL"
        record["error"] = str(error)
        save()
        raise

if __name__ == "__main__":
    raise SystemExit(main())
