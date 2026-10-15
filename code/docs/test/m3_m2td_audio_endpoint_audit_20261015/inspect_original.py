"""Read only the signed ZIP; copy a bounded allowlist and cite raw bytes.

This is an offline observation extractor, not an STA acceptance checker.
Never imports project HDL/checkers or invokes vendor tools.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
ZIP = REPO / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_整机PnR_STA_20261015.zip"
EXPECTED = "17e71ebd5b54743fd0214af5fbfdfd1a4cca4eddbcedab56f7b3df7b3ca521ff"
MEMBERS = (
    "MANIFEST.json", "PREPARATION_RECEIPT.json", "RUN_RECEIPT.json",
    "PHYSICAL_REVIEW.json", "project.gprj", "run.tcl",
    "constraints/audio_visual_hold055.sdc", "constraints/audio_visual.cst",
    "pnr/timing.html", "pnr/usage.txt", "pnr/cmd.do", "pnr/device.cfg",
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cells(raw: str) -> list[str]:
    # Actual Gowin HTML has some missing </td> (e.g. Frequency column).
    return [html.unescape(re.sub(r"<[^>]*>", "", x)).strip()
            for x in re.findall(r"<t[dh]\b[^>]*>(.*?)(?=<t[dh]\b|</tr>|$)", raw, re.S)]


def tables(text: str) -> list[dict]:
    anchors = list(re.finditer(r'<a\s+name="([^"]+)"', text))
    result = []
    for match in re.finditer(r"<table\b[^>]*>.*?</table>", text, re.S):
        prior = [a for a in anchors if a.start() < match.start()]
        anchor = prior[-1].group(1) if prior else None
        command_match = re.findall(r"<h4>Report Command:(.*?)</h4>",
                                   text[prior[-1].end():match.start()] if prior else "", re.S)
        rows = []
        for row_index, row in enumerate(re.finditer(r"<tr\b[^>]*>.*?</tr>", match.group(), re.S)):
            start = match.start() + row.start()
            end = match.start() + row.end()
            rows.append({"row_index_zero_based": row_index, "cells": cells(row.group()),
                         "char_start": start, "char_end": end})
        result.append({"anchor": anchor, "command": html.unescape(command_match[-1]) if command_match else None,
                       "char_start": match.start(), "char_end": match.end(), "rows": rows})
    return result


def location(text: str, start: int, end: int) -> dict:
    raw = text[start:end].encode("utf-8")
    return {"member": "pnr/timing.html", "byte_start_inclusive": len(text[:start].encode("utf-8")),
            "byte_end_exclusive": len(text[:end].encode("utf-8")),
            "fragment_sha256": sha(raw), "locator_convention": "zero-based UTF-8 raw bytes; no newline normalization"}


def inspect(output: Path) -> dict:
    if output.parent.resolve() != ROOT or output.exists():
        raise ValueError("output must be a fresh immediate child of the exclusive directory")
    data = ZIP.read_bytes()
    if sha(data) != EXPECTED:
        raise ValueError("signed physical ZIP SHA mismatch")
    with zipfile.ZipFile(ZIP) as archive:
        names = archive.namelist()
        expected_names = set(MEMBERS) | {"stdout.log", "stderr.log", "pnr/pins.html"}
        if len(names) != len(set(names)) or set(names) != expected_names:
            raise ValueError("unexpected archive member set")
        manifest = json.loads(archive.read("MANIFEST.json"))
        blobs = {}
        for name in MEMBERS:
            blob = archive.read(name)
            if name != "MANIFEST.json":
                identity = manifest["files"][name]
                if identity != {"bytes": len(blob), "sha256": sha(blob)}:
                    raise ValueError(f"signed member differs: {name}")
            blobs[name] = blob
        raw_text = blobs["pnr/timing.html"].decode("utf-8")
        parsed = tables(raw_text)
    found = []
    selected_details = []
    for table in parsed:
        if not re.fullmatch(r"(?:Setup|Hold)_Slack_Table[0-9]+", table["anchor"] or ""):
            continue
        for row in table["rows"][1:]:
            row_cells = row["cells"]
            if len(row_cells) != 9:
                raise ValueError(f"unexpected timing row width in {table['anchor']}")
            if "g_polyphonic.u_audio_core/u_chain/" not in " ".join(row_cells[2:4]):
                continue
            found.append({"analysis": table["anchor"].split("_")[0], "anchor": table["anchor"],
                          "report_command": table["command"], "row_index_zero_based": row["row_index_zero_based"],
                          "path_number": int(row_cells[0]), "slack_ns": row_cells[1],
                          "from_node": row_cells[2], "to_node": row_cells[3],
                          "from_clock": row_cells[4], "to_clock": row_cells[5],
                          "relation_ns": row_cells[6], "clock_skew_ns": row_cells[7], "data_delay_ns": row_cells[8],
                          "raw_location": location(raw_text, row["char_start"], row["char_end"])})
    # Only four sample/pitch datapath rows and one event-to-audio ingress row.
    selections = [("Hold_Slack_Table8", n) for n in (2, 3, 4, 5)] + [("Setup_Slack_Table10", 1)]
    selected = []
    for anchor, number in selections:
        matches = [f for f in found if f["anchor"] == anchor and f["path_number"] == number]
        if len(matches) != 1:
            raise ValueError(f"missing/duplicate selected row {anchor}:{number}")
        record = matches[0]
        # Locate actual detailed timing block, not a summary/table-only inference.
        kind = anchor.split("_")[0]
        candidates = [t for t in parsed if t["anchor"] and t["anchor"].startswith(kind)
                      and any(record["from_node"] in c for r in t["rows"] for c in r["cells"])
                      and any(record["to_node"] in c for r in t["rows"] for c in r["cells"])
                      and t["anchor"] != anchor]
        record["detail_candidates"] = [{"anchor": t["anchor"], **location(raw_text, t["char_start"], t["char_end"])} for t in candidates]
        record["routed_node_locations"] = [
            {"node": r["cells"][-1], "physical_location": r["cells"][-2],
             "raw_location": location(raw_text, r["char_start"], r["char_end"])}
            for t in candidates for r in t["rows"] if len(r["cells"]) == 7
            and r["cells"][-1] in (record["from_node"], record["to_node"])]
        selected.append(record)
        selected_details.extend(candidates)
    metadata = {t["anchor"]: [{"cells": r["cells"], "raw_location": location(raw_text, r["char_start"], r["char_end"])} for r in t["rows"]]
                for t in parsed if t["anchor"] in ("Message", "Clock_Report", "STA_Tool_Run_Summary", "Max_Frequency_Report")}
    report = {
        "schema": "M3_M2TD_ENDPOINT_OBSERVATIONS_V1", "scope": "OFFLINE_ORIGINAL_REPORT_OBSERVATION_ONLY",
        "board_release_allowed": False, "new_sta_executed": False,
        "source_archive": {"path": str(ZIP.relative_to(REPO)).replace("\\", "/"), "bytes": len(data), "sha256": sha(data)},
        "member_identities": {n: {"bytes": len(b), "sha256": sha(b)} for n, b in blobs.items()},
        "archive_members": names, "metadata": metadata,
        "audio_summary_rows": found, "selected_paths": selected,
        "base_name_search": {x: raw_text.count(x) for x in ("base_s1", "base_s2")},
        "netlist_in_archive": any(n.endswith(".vg") for n in names),
        "all_table_anchors": [t["anchor"] for t in parsed],
        "limits": ["Absent from limited worst-path report is not proof of optimization or absence from netlist.",
                   "A source register, synthesis .vg cell and a routed PnR timing node are different evidence classes.",
                   "Hold-only/Setup-only for exact pair cannot accept setup+hold coverage."]}
    output.mkdir()
    for name, blob in blobs.items():
        dest = output / "originals" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
    (output / "observations.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fragments = output / "fragments"
    fragments.mkdir()
    for table in parsed:
        if table["anchor"] in {p["anchor"] for p in selected} or table in selected_details or table["anchor"] in metadata:
            (fragments / (table["anchor"] + "_byte" + str(len(raw_text[:table["char_start"]].encode("utf-8"))) + ".html")).write_bytes(raw_text[table["char_start"]:table["char_end"]].encode("utf-8"))
    if sha(ZIP.read_bytes()) != EXPECTED:
        raise ValueError("input changed during observation")
    print(json.dumps({"status": "OBSERVED_NOT_STA_ACCEPTED", "selected_paths": len(selected),
                      "all_audio_summary_rows": len(found), "source_before_after_sha256": EXPECTED,
                      "output": str(output), "board_release_allowed": False}))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        inspect(args.output.resolve())
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print(f"OBSERVATION_REJECTED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
