"""Self-check the provenance CLI using synthetic, explicitly labeled fixtures.

These fixtures are NOT M2-approved production files or RTL simulations.
All generated files stay in a new directory under code/output; no cleanup.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parents[4]
RUNNER = ROOT / "code/scripts/run_m3_integration_provenance_audit.py"
FIXTURES = {
    "code/rtl/midi_event_parser.sv": b"module midi_event_parser; endmodule\n",
    "code/rtl/button_event_converter.sv": b"module button_event_converter; endmodule\n",
    "code/rtl/performance_event_fifo.sv": b"module performance_event_fifo; endmodule\n",
    "code/rtl/performance_control_snapshot.sv": b"module performance_control_snapshot; endmodule\n",
    "code/rtl/adsr.sv": (
        b'`include "shared.svh"\nmodule adsr;\n'
        b'parameter ROM_FILE = "model/generated/gain.mem";\n'
        b'reg [7:0] table_data [0:1]; initial $readmemh(ROM_FILE, table_data);\n'
        b'// synthesis translate_off\n'
        b'initial $readmemh("missing_simulation_only.mem", table_data);\n'
        b'// synthesis translate_on\nendmodule\n'
    ),
    "code/rtl/strict_flash.sv": b"module strict_flash; endmodule\n",
    "code/rtl/shared.svh": b"localparam integer TEST_FIXTURE_WIDTH = 8;\n",
    "code/model/generated/gain.mem": b"00\n7f\n",
    "code/constraints/test.cst": b'IO_LOC "clk" 1;\n',
    "code/constraints/test.sdc": b"create_clock -period 20 [get_ports clk]\n",
}
ROLES = {
    "parser": "code/rtl/midi_event_parser.sv",
    "button_counter": "code/rtl/button_event_converter.sv",
    "public_fifo": "code/rtl/performance_event_fifo.sv",
    "control_snapshot": "code/rtl/performance_control_snapshot.sv",
    "adsr": "code/rtl/adsr.sv",
    "strict_flash": "code/rtl/strict_flash.sv",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def json_write(path, data):
    write(path, (json.dumps(data, indent=2) + "\n").encode("utf-8"))


def kind(path):
    return {".sv": "source", ".svh": "include", ".mem": "rom",
            ".cst": "cst", ".sdc": "sdc"}[Path(path).suffix]


def fixture(root):
    for path, data in FIXTURES.items():
        write(root / path, data)
    manifest = {
        "version": 1, "scope": "production", "test_fixture": True,
        "approval": {"by": "TEST_FIXTURE", "reference": "self-test only, not M2 approval"},
        "baseline_commit": "b9366a6", "features": {"audio": "synthetic", "visual": "synthetic"},
        "synthesis_cwd": "code", "project": {"path": "code/build/test.gprj"},
        "roles": copy.deepcopy(ROLES), "required_roles": list(ROLES),
        "include_dirs": ["code/rtl"],
        "files": [{"path": p, "sha256": sha(data), "kind": kind(p), "origin": "repository"}
                  for p, data in FIXTURES.items()],
    }
    entries = [{"path": "../" + p.removeprefix("code/"),
                "type": "file.systemverilog" if kind(p) == "source" else "file." + kind(p),
                "enable": "1"}
               for p in FIXTURES if kind(p) in ("source", "cst", "sdc")]
    # Reuse the existing prepare-style SHA table, with an independently pinned
    # metadata file. Only synthetic bytes are hashed here, never real sources.
    parser = next(f for f in manifest["files"] if f["path"] == ROLES["parser"])
    metadata = {"input_sha256": {parser["path"]: parser.pop("sha256")}}
    json_write(root / "approved_inputs.json", metadata)
    manifest["hash_manifests"] = [{"path": "approved_inputs.json",
                                   "sha256": sha((root / "approved_inputs.json").read_bytes())}]
    parser["hash_ref"] = {"manifest": "approved_inputs.json", "field": "input_sha256", "key": parser["path"]}
    return manifest, entries


def file_spec(manifest, path):
    return next(f for f in manifest["files"] if f["path"] == path)


def replace_source(root, manifest, entries, role, new_path, origin):
    old_path = manifest["roles"][role]
    old = file_spec(manifest, old_path)
    data = (root / old_path).read_bytes()
    write(root / new_path, data)
    manifest["files"].remove(old)
    manifest["files"].append({"path": new_path, "kind": "source", "origin": origin, "sha256": sha(data)})
    manifest["roles"][role] = new_path
    next(e for e in entries if e["path"] == "../" + old_path.removeprefix("code/"))["path"] = "../" + new_path.removeprefix("code/")


def add_source(root, manifest, entries, path, data):
    write(root / path, data)
    manifest["files"].append({"path": path, "kind": "source", "origin": "repository", "sha256": sha(data)})
    entries.append({"path": "../" + path.removeprefix("code/"), "type": "file.verilog", "enable": "1"})


def prepare_case(name, root, manifest, entries):
    """Return expected error code, or None for a positive fixture."""
    if name in ("production", "disabled_missing_source"):
        if name == "disabled_missing_source":
            entries.append({"path": "../missing.sv", "type": "file.verilog", "enable": "0"})
        return None
    if name in ("relocated_D", "relocated_E"):
        recorded = name[-1] + ":/fixture/team/repo"
        manifest["recorded_repo_root"] = recorded
        for e in entries:
            e["path"] = recorded + "/code/" + e["path"].removeprefix("../")
        for spec in manifest["files"]:
            spec["path"] = recorded + "/" + spec["path"]
        manifest["roles"] = {k: recorded + "/" + v for k, v in manifest["roles"].items()}
        # Test relocation of an absolute synthesis ROM path too.
        adsr = root / ROLES["adsr"]
        data = adsr.read_bytes().replace(b"model/generated/gain.mem", (recorded + "/code/model/generated/gain.mem").encode())
        write(adsr, data)
        file_spec(manifest, recorded + "/" + ROLES["adsr"])["sha256"] = sha(data)
        return None
    if name in ("isolated_candidate", "approved_production_stage", "output_only_button", "unapproved_output"):
        origin = "isolated_candidate" if name != "unapproved_output" else "repository"
        if name == "isolated_candidate":
            manifest["scope"] = "isolated"
        if name == "approved_production_stage":
            origin = "approved_production_stage"
        path = "code/output/candidate/button_event_converter.sv"
        replace_source(root, manifest, entries, "button_counter", path, origin)
        if name == "approved_production_stage":
            file_spec(manifest, path)["approval_reference"] = "TEST_FIXTURE explicit final staged approval"
            return None
        return {"output_only_button": "candidate_in_production", "unapproved_output": "unapproved_output"}.get(name)
    if name in ("duplicate_basename_allowed", "duplicate_basename", "duplicate_module_alias"):
        path = "code/rtl/other/midi_event_parser.sv" if name != "duplicate_module_alias" else "code/rtl/parser_alias.sv"
        data = b"module second_fixture_parser; endmodule\n" if name != "duplicate_module_alias" else FIXTURES[ROLES["parser"]]
        add_source(root, manifest, entries, path, data)
        if name == "duplicate_basename_allowed":
            manifest["allowed_duplicate_basenames"] = [{"name": "midi_event_parser.sv", "paths": [ROLES["parser"], path]}]
            return None
        return "duplicate_basename" if name == "duplicate_basename" else "duplicate_module"
    if name in ("old_parser", "raw_CRLF", "constraint_cst", "constraint_sdc"):
        path = {"constraint_cst": "code/constraints/test.cst", "constraint_sdc": "code/constraints/test.sdc"}.get(name, ROLES["parser"])
        data = (root / path).read_bytes()
        write(root / path, data.replace(b"\n", b"\r\n") if name == "raw_CRLF" else data + b"// stale copy\n")
        return "sha_mismatch"
    if name == "duplicate_parser":
        entries.append(dict(entries[0], path="../rtl/./midi_event_parser.sv"))
        return "duplicate_enabled_source"
    if name in ("missing_rom", "missing_source"):
        (root / ("code/model/generated/gain.mem" if name == "missing_rom" else ROLES["parser"])).unlink()
        return "missing_file"
    if name in ("simulation_rom_only", "unlisted_rom", "dynamic_rom", "nonliteral_include", "encrypted_source"):
        path = ROLES["adsr"]
        data = (root / path).read_bytes()
        replacements = {
            "simulation_rom_only": (b"model/generated/gain.mem", b"absent_synthesis_rom.mem"),
            "unlisted_rom": (b"model/generated/gain.mem", b"model/generated/other.mem"),
            "dynamic_rom": (b"$readmemh(ROM_FILE,", b"$readmemh(dynamic_rom(),"),
            "nonliteral_include": (b'`include "shared.svh"', b"`include UNRESOLVED_HEADER"),
            "encrypted_source": (b"module adsr;", b"`pragma protect begin_protected\nmodule adsr;"),
        }
        data = data.replace(*replacements[name])
        write(root / path, data)
        file_spec(manifest, path)["sha256"] = sha(data)
        if name == "unlisted_rom":
            write(root / "code/model/generated/other.mem", b"00\n")
        return {"dynamic_rom": "unresolved_synthesis_rom", "nonliteral_include": "unresolved_include", "encrypted_source": "encrypted_source"}.get(name, "unapproved_dependency")
    if name == "unlisted_source":
        write(root / "code/rtl/stale/midi_event_parser.sv", FIXTURES[ROLES["parser"]])
        entries[0]["path"] = "../rtl/stale/midi_event_parser.sv"
        return "unlisted_enabled_source"
    if name == "missing_role":
        del manifest["roles"]["parser"]
        return "missing_required_role"
    if name == "bad_enable":
        entries[0]["enable"] = "true"
        return "bad_enable"
    if name == "stale_import":
        write(root / "approved_inputs.json", b'{"input_sha256": {}}\n')
        return "sha_mismatch"
    if name == "unpinned_import":
        manifest["hash_manifests"] = []
        return "unapproved_hash_manifest"
    if name == "missing_constraints":
        entries[:] = [e for e in entries if e["type"] != "file.sdc"]
        manifest["files"] = [f for f in manifest["files"] if f["kind"] != "sdc"]
        return "missing_constraints"
    if name == "empty_manifest_files":
        manifest["files"] = []
        return "empty_file_list"
    if name == "unapproved_external":
        entries[0]["path"] = str(root.parent / "outside.sv")
        return "outside_approved_roots"
    if name == "missing_approval":
        manifest["approval"] = {}
        return "missing_approval"
    if name in ("missing_manifest", "duplicate_json_key", "malformed_xml", "xml_doctype", "report_overwrite"):
        return {"missing_manifest": "invalid_input", "duplicate_json_key": "duplicate_json_key",
                "malformed_xml": "invalid_input", "xml_doctype": "unsafe_xml", "report_overwrite": "report_write"}[name]
    raise ValueError(name)


def snapshot(root):
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in root.rglob("*") if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new directory under code/output")
    args = parser.parse_args()
    output_root = ROOT / "code/output"
    if args.output:
        output = args.output.resolve()
        if output_root.resolve() not in output.parents:
            parser.error("--output must be a new child of code/output")
        output.mkdir(parents=True, exist_ok=False)
    else:
        output = Path(tempfile.mkdtemp(prefix="m3_provenance_", dir=output_root))
    cases = ["production", "disabled_missing_source", "relocated_D", "relocated_E",
             "isolated_candidate", "approved_production_stage", "duplicate_basename_allowed",
             "old_parser", "output_only_button", "missing_rom", "duplicate_parser",
             "constraint_cst", "constraint_sdc", "unapproved_output", "raw_CRLF",
             "duplicate_basename", "duplicate_module_alias", "simulation_rom_only",
             "unlisted_rom", "dynamic_rom", "nonliteral_include", "encrypted_source",
             "unlisted_source", "missing_source", "missing_role", "bad_enable",
             "stale_import", "unpinned_import", "missing_constraints", "empty_manifest_files",
             "unapproved_external", "missing_approval", "missing_manifest", "duplicate_json_key",
             "malformed_xml", "xml_doctype", "report_overwrite"]
    results = []
    for name in cases:
        case_dir = output / name
        root = case_dir / "repo"
        manifest, entries = fixture(root)
        expected = prepare_case(name, root, manifest, entries)
        xml = '<?xml version="1" encoding="UTF-8"?><Project><FileList>' + "".join(
            "<File " + " ".join(k + "=" + quoteattr(v) for k, v in e.items()) + "/>" for e in entries
        ) + "</FileList></Project>\n"
        if name == "malformed_xml":
            xml = "<Project><FileList>"
        if name == "xml_doctype":
            xml = '<!DOCTYPE Project SYSTEM "missing.dtd">' + xml
        project = root / manifest["project"]["path"]
        write(project, xml.encode())
        manifest["project"]["sha256"] = sha(project.read_bytes())
        manifest_path = root / "approved_manifest.json"
        json_write(manifest_path, manifest)
        if name == "missing_manifest":
            manifest_path.unlink()
        if name == "duplicate_json_key":
            write(manifest_path, b'{"version":1,"version":1}\n')
        before = snapshot(root)
        report = case_dir / "audit_report.json"
        if name == "report_overwrite":
            write(report, b"KEEP PRIOR EVIDENCE\n")
        command = [sys.executable, "-X", "utf8", str(RUNNER), "--project", str(project),
                   "--manifest", str(manifest_path), "--repo-root", str(root), "--report", str(report)]
        run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=30)
        write(case_dir / "stdout.log", run.stdout.encode())
        write(case_dir / "stderr.log", run.stderr.encode())
        try:
            actual = json.loads(run.stdout)
        except ValueError:
            actual = {"result": "INVALID_JSON"}
        actual_error = actual.get("error", {}).get("code")
        preserved = before == snapshot(root)
        if name == "report_overwrite":
            preserved = preserved and report.read_bytes() == b"KEEP PRIOR EVIDENCE\n"
        passed = preserved and not run.stderr and (
            (expected is None and run.returncode == 0 and actual.get("result") == "PASS"
             and actual.get("label") == "TEST_FIXTURE_ONLY" and actual.get("scope") == manifest["scope"])
            or (expected is not None and run.returncode != 0 and actual.get("result") == "FAIL" and actual_error == expected))
        results.append({"case": name, "passed": passed, "expected_error": expected,
                        "actual_error": actual_error, "exit_code": run.returncode,
                        "inputs_unchanged": preserved, "command": command,
                        "stdout_sha256": sha(run.stdout.encode()), "stderr_sha256": sha(run.stderr.encode()),
                        "project_sha256": sha(project.read_bytes()),
                        "manifest_sha256": sha(manifest_path.read_bytes()) if manifest_path.exists() else None})
        print(f"{'PASS' if passed else 'FAIL'} {name}: exit={run.returncode}, error={actual_error}")
    evidence = {"label": "TEST_FIXTURE_ONLY", "python": sys.version,
                "runner_sha256": sha(RUNNER.read_bytes()), "selftest_sha256": sha(Path(__file__).read_bytes()),
                "fixture_cases": len(results), "positive_cases": sum(r["expected_error"] is None for r in results),
                "negative_cases": sum(r["expected_error"] is not None for r in results),
                "passed": all(r["passed"] for r in results), "results": results}
    json_write(output / "evidence.json", evidence)
    print(f"{'PASS' if evidence['passed'] else 'FAIL'} {len(results)} fixtures; evidence={output / 'evidence.json'}")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
