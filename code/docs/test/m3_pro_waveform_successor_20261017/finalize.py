"""Seal the successful bounded E2 run and every earlier failure unchanged."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
RTL = ROOT / "code/rtl/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017"
TB = ROOT / "code/tb/input/pcm_waveform_candidate/m3_pro_waveform_successor_20261017"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    rounds = sorted(HERE.glob("ROUND_*/RUN_RECEIPT.json"))
    assert len(rounds) == 3
    receipts = [json.loads(p.read_text(encoding="utf-8")) for p in rounds]
    assert [r["passed"] for r in receipts] == [False, False, True]
    assert all(r["identity_stable"] for r in receipts)
    success = receipts[-1]
    assert success["before"] == success["after"]
    for path, identity in success["after"]["inputs"].items():
        assert sha(Path(path)) == identity["sha256"], "SOURCE_DRIFT_AFTER_RUN"
    for path, identity in success["after"]["tools"].items():
        assert sha(Path(path)) == identity["sha256"], "TOOL_DRIFT_AFTER_RUN"
    source_map = []
    for path, identity in success["before"]["inputs"].items():
        frozen = HERE / "ROUND_03/execution_sources" / Path(path).name
        assert frozen.exists() and sha(frozen) == identity["sha256"]
        source_map.append({"original": path, "frozen": str(frozen.relative_to(ROOT)), **identity})
    write(HERE / "SOURCE_COPY_MAP.json", source_map)
    outcomes = []
    for r, path in zip(receipts, rounds):
        calls = []
        for call in r["calls"]:
            stdout = path.parent / (call["label"] + ".stdout")
            stderr = path.parent / (call["label"] + ".stderr")
            assert sha(stdout) == call["stdout_sha256"]
            assert sha(stderr) == call["stderr_sha256"]
            assert not call["timeout"]
            text = stdout.read_text(encoding="utf-8")
            first = re.findall(r"^FIRST_REJECT .+$", text, re.M)
            calls.append({**call, "first_reject_lines": first,
                          "stdout": str(stdout.relative_to(ROOT)),
                          "stderr": str(stderr.relative_to(ROOT))})
        outcomes.append({"round": r["round_number"], "passed": r["passed"],
                         "error": r["error"], "elapsed_seconds": r["elapsed_seconds"],
                         "receipt_sha256": sha(path), "calls": calls})
    result = {
        "task": "E2_FIXED_LEFT_WAVEFORM", "overall_status": "PARTIAL",
        "isolated_status": "PASS", "actual_level": success["level"],
        "head_at_run": success["head"], "origin_at_run": success["origin_develop_visible"],
        "rounds_consumed": 3, "round_limit": 6, "success_stop": True,
        "source_and_tool_identity_stable": True, "round_results": outcomes,
        "positive": success["results"][0], "rtl_negatives": success["results"][1:],
        "pixel_clocks_checked": 3998520,
        "input_identity": json.loads((HERE / "INPUT_IDENTITY.json").read_text(encoding="utf-8")),
        "main_source_sha256": {str(p.relative_to(ROOT)): sha(p)
                               for folder in (RTL, TB) for p in folder.glob("*.sv")},
        "remaining": ["new exact Pro source/ROM/top/trace", "M2 controlled integration and complete CDC/STA",
                      "approved same-version bitstream/restoration identity and electrical originals",
                      "same-version actual screen/audio coexistence capture"],
        "Gowin_ModelSim_hardware_invocations": 0, "board_release_allowed": False,
        "git_writes": 0, "submitted": False, "pushed": False,
        "publication_owner": "night_task_1", "M2_delivery": "待用户转发，尚未送达",
        "time_utc": datetime.now(timezone.utc).isoformat(),
    }
    write(HERE / "RESULT.json", result)
    files = sorted(p for folder in (RTL, TB, HERE) for p in folder.rglob("*")
                   if p.is_file() and not p.name.startswith("SEAL_EXECUTION."))
    entries = [{"path": str(p.relative_to(ROOT)).replace("\\", "/"),
                "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]
    manifest = {"task": result["task"], "overall_status": "PARTIAL",
                "isolated_status": "PASS", "board_release_allowed": False,
                "excludes": ["MANIFEST.json self", "zip self", "external package/communication receipts",
                             "SEAL_EXECUTION.* external execution receipts"],
                "entries": entries}
    write(HERE / "MANIFEST.json", manifest)
    package = HERE / "M3_FIXED_LEFT_WAVEFORM_ISOLATED_20261017.zip"
    with zipfile.ZipFile(package, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for entry, path in zip(entries, files):
            archive.write(path, entry["path"])
        archive.write(HERE / "MANIFEST.json", str((HERE / "MANIFEST.json").relative_to(ROOT)).replace("\\", "/"))
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
        for entry in entries:
            data = archive.read(entry["path"])
            assert len(data) == entry["bytes"] and digest(data) == entry["sha256"]
        assert len(archive.namelist()) == len(entries) + 1
        assert archive.read(str((HERE / "MANIFEST.json").relative_to(ROOT)).replace("\\", "/")) == (HERE / "MANIFEST.json").read_bytes()
    status = {"package": str(package), "bytes": package.stat().st_size,
              "sha256": sha(package), "members": len(entries) + 1,
              "manifest_sha256": sha(HERE / "MANIFEST.json"),
              "every_member_sha_bytes_crc_verified": True, "overall_status": "PARTIAL",
              "isolated_status": "PASS", "board_release_allowed": False,
              "submitted": False, "pushed": False,
              "git_head_at_seal": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    write(HERE / "PACKAGE_STATUS.json", status)
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
