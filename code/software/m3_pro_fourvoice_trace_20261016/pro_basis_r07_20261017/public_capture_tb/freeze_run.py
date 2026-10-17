"""Pin one new <=90s software group; preparation only, no selftest import."""
import json
from pathlib import Path
import shutil
import sys

from prepare import DOC, ROOT, SOFT, TB, identity, save


def main():
    # Refresh pre-execution source metadata after the documented static race fix.
    assembly_path = DOC / "SOURCE_ASSEMBLY.json"
    assembly = json.loads(assembly_path.read_text(encoding="utf-8"))
    assembly["new_TB_sources"] = [identity(TB / name) for name in
                                  ("r7a_public_observer.sv", "tb_r7a_public_capture.sv")]
    assembly["finish_request_phase"] = "DRIVER_STOP_THEN_CORE_NEGEDGE_STABLE_BEFORE_PRE_NBA"
    assembly_path.write_text(json.dumps(assembly, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8", newline="\n")
    references = json.loads((DOC / "INPUT_IDENTITIES.json").read_text(encoding="utf-8"))["files"]
    for ref in references:
        for key in ("original", "snapshot"):
            if identity(Path(ref[key]["path"])) != ref[key]:
                raise SystemExit("INPUT_IDENTITY_DRIFT_BEFORE_FREEZE")
    run = DOC / "RUN_01"
    run.mkdir(exist_ok=False)
    source = list(SOFT.glob("*.py")) + list(TB.glob("*.sv"))
    source += [DOC / n for n in ("PORT_MAP.json", "CAPTURE_SCHEMA.json", "SOURCE_ASSEMBLY.json",
                                "INPUT_IDENTITIES.json", "CASE_SPEC.json", "CAPTURE_FORMAT.md", "START.md", "SELF_AUDIT.md")]
    source += list((DOC / "FIXTURES").rglob("*"))
    source += [Path(ref[key]["path"]) for ref in references for key in ("original", "snapshot")]
    support = ROOT / "code/software/m3_r05_functional_integration_20261015"
    source += [support / n for n in ("supervised_process.py", "common.py", "windows_job.py")]
    pinned = sorted(set(p.resolve() for p in source if p.is_file()))
    originals = run / "SOURCE_INPUT_ORIGINALS"
    originals.mkdir()
    entries = []
    for index, path in enumerate(pinned, 1):
        item = identity(path)
        snapshot = originals / (f"{index:03d}_" + path.name)
        shutil.copyfile(path, snapshot)
        if identity(snapshot)["sha256"] != item["sha256"]:
            raise SystemExit("SNAPSHOT_MISMATCH")
        entries.append({"original": item, "snapshot": identity(snapshot)})
    prefix = Path(sys.base_prefix)
    runtime = [Path(sys.executable)]
    runtime += list(prefix.glob("*.dll")) + list(prefix.glob("*.zip"))
    runtime += list((prefix / "DLLs").glob("*.dll")) + list((prefix / "DLLs").glob("*.pyd"))
    runtime += [p for p in (prefix / "Lib").rglob("*.py")
                if "site-packages" not in p.parts and "__pycache__" not in p.parts]
    runtime += [Path("C:/Windows/System32/kernel32.dll")]
    save(DOC / "RUN_SPEC.json", {"schema": "M3_R7A_RUN_SPEC_V1", "run": str(run),
        "baseline": "4fd3366e42fd2356e56eb96eee70b6771afd4bb1", "group": "INITIAL_UNIQUE_NEW_SOFTWARE",
        "budget_s": 90, "execution_deadline_s": 85, "cleanup_reserve_s": 5,
        "command": [sys.executable, "-s", "-B", str(SOFT / "selftest.py"), "--output", str(run / "products")],
        "cwd": str(SOFT), "python_version": sys.version, "python_executable": sys.executable,
        "sources_inputs_dependencies": entries,
        "tool_runtime": [identity(p) for p in sorted(set(runtime)) if p.is_file()],
        "environment_changes": {"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": "REMOVED", "PYTHONHOME": "REMOVED"},
        "cases": identity(DOC / "CASE_SPEC.json"), "scope": "SYNTHETIC_REPRESENTATION_ONLY",
        "initial_group_allowed": 1, "new_defect_targeted_increment_max_s": 60,
        "HDL_rounds_allowed": 0, "old_R06_reexecution_allowed": False, "board_release_allowed": False})
    print(json.dumps({"frozen": identity(DOC / "RUN_SPEC.json"), "files": len(entries), "functional_groups_run": 0}))


if __name__ == "__main__":
    main()
