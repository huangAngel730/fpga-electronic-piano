#!/usr/bin/env python3
"""Build an isolated Gowin copy to inspect actual I2S output timing paths."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from capture_t034_formal_build import ROOT, PROJECT, digest, git, project_inputs

OUT = ROOT / "code/output/t034_audio_output_paths"
NAME = "t034_audio_output_probe"
PORTS = ("i2s_bclk", "i2s_lrck", "i2s_din")


def prepare():
    inputs = project_inputs()
    dirty = git("status", "--porcelain", "--untracked-files=no", "--",
                *[str(path.relative_to(ROOT)) for path in inputs])
    if dirty:
        raise ValueError("Formal project inputs modified: " + dirty)
    hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): digest(path)
              for path in inputs}
    OUT.mkdir(parents=True, exist_ok=True)
    sdc = (ROOT / "code/constraints/audio_timing.sdc").read_text(encoding="utf-8")
    extra = [f"report_timing -{kind} -to [get_ports {{{port}}}] -max_paths 1"
             for port in PORTS for kind in ("setup", "hold")]
    (OUT / f"{NAME}.sdc").write_text(sdc.rstrip() + "\n" + "\n".join(extra) + "\n",
                                     encoding="utf-8")
    original = ET.parse(PROJECT).getroot()
    for item in original.findall("./FileList/File"):
        source = (PROJECT.parent / item.attrib["path"]).resolve()
        item.set("path", (OUT / f"{NAME}.sdc" if item.attrib["type"] == "file.sdc"
                          else source).as_posix())
    probe_project = OUT / f"{NAME}.gprj"
    ET.ElementTree(original).write(probe_project, encoding="utf-8", xml_declaration=True)
    script = OUT / "build.tcl"
    script.write_text(f"open_project {{{probe_project.as_posix()}}}\n"
                      "set_option -top_module electronic_piano_top\n"
                      "set_option -verilog_std sysv2017\nrun all\n", encoding="utf-8")
    return inputs, hashes, extra, script


def main():
    try:
        inputs, before, extra, script = prepare()
        home = Path(os.environ.get("GOWIN_HOME", "D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64"))
        executable = home / "IDE/bin/gw_sh.exe"
        if not executable.is_file():
            raise ValueError(f"Gowin executable missing: {executable}")
        started = datetime.now(timezone.utc)
        log = OUT / "build.log"
        with log.open("w", encoding="utf-8") as stream:
            result = subprocess.run([str(executable), str(script)], cwd=OUT,
                                    stdout=stream, stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise ValueError(f"Gowin run all failed ({result.returncode}); see {log}")
        if "Bitstream generation completed" not in log.read_text(encoding="utf-8", errors="replace"):
            raise ValueError("Gowin log lacks bitstream completion")
        report = OUT / "impl/pnr" / f"{NAME}_tr_content.html"
        pins = OUT / "impl/pnr" / f"{NAME}.rpt.txt"
        for target in (report, pins):
            if not target.is_file() or target.stat().st_size == 0 or target.stat().st_mtime < started.timestamp() - 2:
                raise ValueError(f"Missing or stale report: {target}")
        after = {str(path.relative_to(ROOT)).replace("\\", "/"): digest(path)
                 for path in inputs}
        if after != before:
            raise ValueError("Formal project inputs changed while building")
        from check_t034_output_paths import verify_paths
        measured = verify_paths(report.read_text(encoding="utf-8"),
                                pins.read_text(encoding="utf-8"), extra,
                                (OUT / f"{NAME}.sdc").read_text(encoding="utf-8"),
                                (ROOT / "code/constraints/electronic_piano.cst").read_text(encoding="utf-8"))
        evidence = {"scope": "isolated formal RTL output paths; not a formal bitstream",
                    "source_commit": git("rev-parse", "HEAD"),
                    "build_started_utc": started.isoformat(),
                    "formal_input_sha256": before,
                    "reports_sha256": {path.name: digest(path) for path in (report, pins, log,
                        OUT / f"{NAME}.sdc", OUT / f"{NAME}.gprj")},
                    "extra_sdc_commands": extra, "paths": measured}
        (OUT / "summary.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print("PASS T034 isolated I2S output-path proof:", OUT / "summary.json")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("FAIL T034 output-path probe:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
