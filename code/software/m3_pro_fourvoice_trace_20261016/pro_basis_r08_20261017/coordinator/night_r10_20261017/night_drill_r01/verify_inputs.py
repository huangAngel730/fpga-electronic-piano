"""Read-only receipt/Git/ZIP byte verification, never execute an input."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import zipfile
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[7]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/night_drill_r01"
SOURCE = ROOT / "code/docs/test/m2_night_drill_r01_20261017"
OUT = ROOT / "code/output/m3_m2_night_drill_20261017/originals/input_verification"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    start = time.monotonic()
    resume = sys.argv[1:] == ["--resume-tree"]
    if not resume:
        OUT.mkdir(parents=True, exist_ok=False)
    target = OUT / "tree_repair" if resume else OUT
    if resume:
        target.mkdir(exist_ok=False)
    commands = []

    def git(*args: str) -> bytes:
        index = len(commands)
        if resume and index < 20:
            data = (OUT / f"git_{index:02d}.stdout.bin").read_bytes()
            error = (OUT / f"git_{index:02d}.stderr.bin").read_bytes()
            commands.append({"argv": ["git", *args], "exit_code": None,
                             "original_exit_receipt": "NOT_SEPARATELY_PERSISTED; use independent READ_COMMAND_TOOL_RECEIPTS.json for ancestry",
                             "reused_original_read": True, "stdout_sha256": sha(data),
                             "stderr_sha256": sha(error)})
            return data
        proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                              timeout=min(10, max(0.1, 55 - (time.monotonic() - start))), check=False)
        (target / f"git_{index:02d}.stdout.bin").write_bytes(proc.stdout)
        (target / f"git_{index:02d}.stderr.bin").write_bytes(proc.stderr)
        commands.append({"argv": ["git", *args], "cwd": str(ROOT), "exit_code": proc.returncode,
                         "stdout_sha256": sha(proc.stdout), "stderr_sha256": sha(proc.stderr)})
        if proc.returncode:
            raise RuntimeError(f"GIT_READ_FAILED:{index}")
        return proc.stdout

    assignment = json.loads((SOURCE / "ASSIGNMENT_RECEIPT.json").read_text(encoding="utf-8"))
    sample = json.loads((SOURCE / "HANDOFF.json").read_text(encoding="utf-8"))
    checks = []
    for name, receipt in [("assignment", assignment), ("sample", sample)]:
        commit = receipt["result_commit"]
        if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            raise ValueError("FULL_COMMIT_REQUIRED")
        git("merge-base", "--is-ancestor", commit, "origin/develop")
        for item in receipt["manifest"]:
            relative = item["path"]
            original = git("show", f"{commit}:{relative}")
            current = (ROOT / relative).read_bytes()
            valid = len(original) == item["bytes"] and sha(original) == item["sha256"]
            checks.append({"receipt": name, "commit": commit, "path": relative,
                           "bytes": len(original), "sha256": sha(original), "manifest_match": valid,
                           "current_sha256": sha(current), "current_equals_sample": current == original})
            if not valid:
                raise ValueError("MANIFEST_MISMATCH:" + relative)
    pub = json.loads((SOURCE / "SOURCE_PUBLICATION_RECEIPT.json").read_text(encoding="utf-8"))
    gate = json.loads((SOURCE / "SOURCE_GATE_RECEIPT.json").read_text(encoding="utf-8"))
    tree = git("rev-parse", sample["result_commit"] + "^{tree}").decode().strip()
    expected_tree = "7352880e5091a7396d7a9727d98e6f7d0446aa0c"
    if tree != expected_tree or gate["tree"] != tree or pub["tree"] != tree:
        raise ValueError("SOURCE_TREE_MISMATCH")
    archive = SOURCE / "SOURCE_RAW_EVIDENCE.zip"
    members = []
    with zipfile.ZipFile(archive) as zf:
        if zf.testzip() is not None:
            raise ValueError("SOURCE_ZIP_CRC_FAILURE")
        for info in zf.infolist():
            data = zf.read(info)
            members.append({"name": info.filename, "bytes": len(data), "sha256": sha(data), "crc32": info.CRC})
        stdout_candidates = [x for x in members if x["sha256"] == gate["stdout_sha256"]]
        stderr_candidates = [x for x in members if x["sha256"] == gate["stderr_sha256"]]
        if len(stdout_candidates) != 1 or len(stderr_candidates) != 1:
            raise ValueError("GATE_RAW_STREAMS_MISSING")
        stdout = zf.read(stdout_candidates[0]["name"]).decode("utf-8", errors="strict")
        pass_lines = [s for s in stdout.splitlines() if "[PASS]" in s]
        if len(pass_lines) != 9 or gate["exit_code"] != 0 or gate["pass_count"] != 9:
            raise ValueError("SOURCE_GATE_FAILED")
    result = {"schema": "M3_DRILL_INPUT_VERIFICATION_R01", "utc": datetime.now(timezone.utc).isoformat(),
              "status": "PASS", "read_order": ["ASSIGNMENT_RECEIPT.json", "HANDOFF.json"],
              "remote_tip": git("rev-parse", "origin/develop").decode().strip(),
              "assignment_commit": assignment["result_commit"], "sample_commit": sample["result_commit"],
              "sample_gate_tree": tree, "checks": checks, "archive_members": members,
              "source_gate_raw_pass_lines": pass_lines, "commands": commands,
              "actual_sample_receive_status": "INPUTS_VERIFIED_NOT_YET_DURABLY_RECEIVED",
              "M2_machine": None, "M2_session": None,
              "M2_identity_boundary": "Originals provide sender paths/PID/time; no explicit host/session identity",
              "real_failure_recovery_evidence": "MISSING", "board_release_allowed": False}
    result["targeted_tree_repair"] = {"used": resume, "elapsed_seconds": time.monotonic() - start,
                                      "limit_seconds": 60, "manifest_git_reads_reused": 20 if resume else 0}
    (DOC / "INPUT_VERIFICATION.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "manifest_items": len(checks),
                      "zip_members": len(members), "source_gate_passes": len(pass_lines)}))


if __name__ == "__main__":
    main()
