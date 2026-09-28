#!/usr/bin/env python3
"""Capture and verify the current formal Gowin project build (T034 baseline)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "code/build/electronic_piano.gprj"
PNR = ROOT / "code/build/impl/pnr"
SYNTH = ROOT / "code/build/impl/gwsynthesis/electronic_piano_syn.rpt.html"
OUTPUT = ROOT / "code/output/t034_formal_build"
from check_t009_fusion_report import verify  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_inputs():
    tree = ET.parse(PROJECT)
    sources = [((PROJECT.parent / node.attrib["path"]).resolve())
               for node in tree.findall("./FileList/File")
               if node.attrib.get("enable") == "1"]
    if not sources or len(sources) != len(set(sources)):
        raise ValueError("Project has missing or duplicate enabled inputs")
    for path in sources:
        if not path.is_file() or not path.is_relative_to(ROOT):
            raise ValueError(f"Missing or out-of-repo input: {path}")
    return [PROJECT, *sources]


def cst_pins(text):
    locations = {}
    settings = {}
    for line in text.splitlines():
        line = line.split("//", 1)[0].strip()
        loc = re.fullmatch(r'IO_LOC\s+"([^"]+)"\s+(\S+);', line)
        port = re.fullmatch(r'IO_PORT\s+"([^"]+)"\s+(.+);', line)
        if loc:
            if loc[1] in locations:
                raise ValueError(f"Duplicate IO_LOC: {loc[1]}")
            locations[loc[1]] = loc[2]
        if port:
            if port[1] in settings:
                raise ValueError(f"Duplicate IO_PORT: {port[1]}")
            settings[port[1]] = dict(re.findall(r'(IO_TYPE|PULL_MODE|BANK_VCCIO)=(\S+)', port[2]))
    if not locations or locations.keys() != settings.keys():
        raise ValueError("IO_LOC/IO_PORT sets differ or are empty")
    for name, fields in settings.items():
        if set(fields) != {"IO_TYPE", "PULL_MODE", "BANK_VCCIO"}:
            raise ValueError(f"Incomplete IO_PORT: {name}")
    return {name: {"ball": ball, **settings[name]}
            for name, ball in locations.items()}


def placed_pins(usage):
    section = re.search(r'^7\. Pinout by Port Name\s*$(.*?)^8\. All Package Pins',
                        usage, re.M | re.S)
    if section is None:
        raise ValueError("Missing port pinout table")
    found = {}
    for line in section[1].splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 18 or cells[0] in ("Port Name", ""):
            continue
        name = cells[0]
        if name in found:
            raise ValueError(f"Duplicate placed pin: {name}")
        found[name] = {"ball": cells[2].split("/")[0],
                       "constrained": cells[3], "direction": cells[4],
                       "IO_TYPE": cells[7], "PULL_MODE": cells[9],
                       "BANK_VCCIO": cells[17]}
    if not found:
        raise ValueError("No placed ports")
    return found


def synthesis_bsram(report):
    # Gowin synthesis prints a device denominator even for a zero-block design.
    # This is synthesis evidence, not an assertion about a missing PnR row.
    matches = re.findall(
        r'<td class="label">\s*BSRAM\s*</td>\s*<td>\s*(\d+)\s*/\s*(\d+)\s*</td>',
        report, re.I)
    if len(matches) != 1:
        raise ValueError(f"Expected one synthesis BSRAM utilization row, got {len(matches)}")
    used, available = map(int, matches[0])
    if available != 118 or used > available:
        raise ValueError(f"Unexpected synthesis BSRAM utilization {used}/{available}")
    return {"used": used, "available": available, "stage": "synthesis"}


def validate_synthesis_against_pnr(synth, pnr):
    bsram = synthesis_bsram(synth)
    pnr_used = pnr["timing_and_resources"]["resources"].get("BSRAM")
    if pnr_used is not None and bsram["used"] != pnr_used:
        raise ValueError(f"Synthesis/PnR BSRAM mismatch: {bsram['used']} vs {pnr_used}")
    return bsram


def verify_build(timing, usage, cst):
    errors, timing_info = verify(timing, usage)
    # Gowin omits the DSP/BSRAM categories entirely in a design using neither.
    # Record them as unreported, not as proven zero; still require Logic and FF.
    optional = {"Missing resource: DSP", "Missing resource: BSRAM"}
    missing_optional = [e for e in errors if e in optional]
    errors = [e for e in errors if e not in optional]
    timing_info["resource_categories_not_reported"] = [e.split(": ")[1]
                                                       for e in missing_optional]
    timing_info["capacity"] = {}
    for kind in ("Logic", "Register", "DSP", "BSRAM"):
        rows = re.findall(r"^\s*" + kind + r"\s*\|\s*(\d+)/(\d+)", usage, re.M)
        if len(rows) > 1:
            raise ValueError(f"Ambiguous resource row: {kind}")
        if rows:
            timing_info["capacity"][kind] = int(rows[0][1])
    if errors:
        raise ValueError("Timing/resource gate: " + "; ".join(errors))
    expected = cst_pins(cst)
    actual = placed_pins(usage)
    if expected.keys() != actual.keys():
        raise ValueError(f"CST versus placed ports: missing={sorted(expected.keys()-actual.keys())}, "
                         f"extra={sorted(actual.keys()-expected.keys())}")
    for name, fields in expected.items():
        for key, value in fields.items():
            if actual[name][key] != value:
                raise ValueError(f"{name}: {key} CST={value} PnR={actual[name][key]}")
        if actual[name]["constrained"] != "Y":
            raise ValueError(f"{name}: placement is unconstrained")
    metadata = {}
    for key in ("Tool Version", "Part Number"):
        match = re.findall(r'^\s*<' + key + r'>:\s*(.+)$', usage, re.M)
        if len(match) != 1:
            raise ValueError(f"Expected one {key}")
        metadata[key] = match[0]
    if metadata["Part Number"] != "GW5AT-LV60PG484AC1/I0":
        raise ValueError("Wrong target part")
    return {"tool_and_part": metadata, "timing_and_resources": timing_info,
            "pins": actual}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True,
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()


def run_capture():
    inputs = project_inputs()
    dirty = git("status", "--porcelain", "--untracked-files=no", "--",
                *[str(path.relative_to(ROOT)) for path in inputs])
    if dirty:
        raise ValueError("Project input has uncommitted edits; cannot attribute to HEAD: " + dirty)
    before = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in inputs}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    targets = [PNR / ("electronic_piano" + suffix)
               for suffix in (".rpt.txt", "_tr_content.html", ".fs")] + [SYNTH]
    start = datetime.now(timezone.utc)
    command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
               str(ROOT / "code/scripts/build_electronic_piano.ps1"), "-Flow", "bitstream"]
    with (OUTPUT / "build.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log,
                                stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise ValueError(f"Gowin build exited {result.returncode}; see {OUTPUT / 'build.log'}")
    for p in targets:
        if not p.is_file() or not p.stat().st_size or p.stat().st_mtime < start.timestamp() - 2:
            raise ValueError(f"Missing/stale build output: {p}")
    after = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in inputs}
    if before != after:
        raise ValueError("Project inputs changed during build")
    log_text = (OUTPUT / "build.log").read_text(encoding="utf-8", errors="replace")
    if "gw_sh exit code: 0" not in log_text:
        raise ValueError("Build log missing successful gw_sh completion")
    info = verify_build(targets[1].read_text(encoding="utf-8"),
                        targets[0].read_text(encoding="utf-8"),
                        (ROOT / "code/constraints/electronic_piano.cst").read_text(encoding="utf-8"))
    info["synthesis_bsram"] = validate_synthesis_against_pnr(
        SYNTH.read_text(encoding="utf-8"), info)
    top = (ROOT / "code/rtl/board/electronic_piano_top.sv").read_text(encoding="utf-8")
    if not re.search(r'parameter\s+int\s+unsigned\s+SOURCE_MODE\s*=\s*0', top):
        raise ValueError("Baseline SOURCE_MODE changed; reclassify the evidence")
    if not re.search(r'CLIP_COUNT_VALID\(1\x27b0\)', top):
        raise ValueError("DIAG/STAT classification changed; reclassify the evidence")
    summary = {"capture_utc": start.isoformat(), "source_commit": git("rev-parse", "HEAD"),
               "scope": "formal Gowin project, SOURCE_MODE=0 simple_voice; DIAG, not final polyphony/STAT",
               "t034_status": "baseline only; final integrated acceptance pending",
               "input_sha256": before,
               "output_sha256": {p.name: digest(p) for p in [*targets, OUTPUT / "build.log"]},
               **info}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
    return summary


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--verify-existing", action="store_true",
                     help="Read existing reports without claiming a fresh build")
    args = cli.parse_args()
    try:
        if args.verify_existing:
            pnr = PNR
            info = verify_build((pnr / "electronic_piano_tr_content.html").read_text(encoding="utf-8"),
                                (pnr / "electronic_piano.rpt.txt").read_text(encoding="utf-8"),
                                (ROOT / "code/constraints/electronic_piano.cst").read_text(encoding="utf-8"))
            info["synthesis_bsram"] = validate_synthesis_against_pnr(
                SYNTH.read_text(encoding="utf-8"), info)
            print("PASS existing report inspection only:", json.dumps(info, indent=2))
        else:
            info = run_capture()
            print("PASS T034 current baseline capture:", OUTPUT / "summary.json")
            print("Fmax:", info["timing_and_resources"]["fmax_mhz"])
            print("T034 final acceptance remains pending integrated RTL and re-run")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, ET.ParseError) as exc:
        print("FAIL T034 capture:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
