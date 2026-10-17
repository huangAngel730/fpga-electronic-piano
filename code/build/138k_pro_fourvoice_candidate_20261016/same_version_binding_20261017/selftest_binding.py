"""One bounded software-only group for the new portable identity checker."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path


REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/same_version_binding_20261017"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def refresh_manifest(root: Path) -> str:
    path = root / "MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for row in manifest["files"]:
        data = (root / row["path"]).read_bytes()
        row["bytes"], row["sha256"] = len(data), sha(data)
    dump(path, manifest)
    return sha(path.read_bytes())


def main() -> int:
    start = time.monotonic()
    tests = OUT / "selftest"
    if tests.exists():
        raise FileExistsError("keep previous selftest; do not overwrite")
    tests.mkdir(parents=True)
    original = OUT / "artifact"
    receipt = json.loads((OUT / "CREATION_RECEIPT.json").read_text(encoding="utf-8"))
    cases = [
        ("correct", 0, "PASS_STATIC_SOURCE_IDENTITY_ONLY"),
        ("source_one_byte", 2, "FILE_SHA_MISMATCH"),
        ("missing_rom", 2, "MISSING_FILE"),
        ("scope_escalation", 2, "SCOPE_ESCALATION"),
        ("unsupported_part_claim", 2, "UNSUPPORTED_PHYSICAL_IDENTITY"),
        ("path_escape", 2, "UNSAFE_PATH"),
    ]
    results = []
    for name, expected_code, expected_text in cases:
        case = tests / name
        case.mkdir()
        root = case / "artifact"
        shutil.copytree(original, root)
        expected_sha = receipt["manifest_sha256"]
        if name == "source_one_byte":
            path = root / "source_closure/inputs/sources/m2_fourvoice_timbre_delay_frame_core.sv"
            data = bytearray(path.read_bytes())
            data[0] ^= 1
            path.write_bytes(data)
        elif name == "missing_rom":
            path = (root / "source_closure/inputs/rom/piano_band_4x256_8191.mem").resolve()
            assert path.is_relative_to(tests.resolve())
            path.unlink()
        elif name in ("scope_escalation", "unsupported_part_claim"):
            path = root / "SOURCE_BINDING.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            if name == "scope_escalation":
                data["scope"] = "PRO_FULL_CHAIN_RTL_AND_BOARD_PASS"
            else:
                data["target"]["complete_device_symbol"] = "GW5AST-LV138FPG676AC1/I0"
            dump(path, data)
            expected_sha = refresh_manifest(root)
        elif name == "path_escape":
            path = root / "MANIFEST.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["files"].append({"path": "../escape.bin", "bytes": 0, "sha256": sha(b"")})
            dump(path, manifest)
            expected_sha = sha(path.read_bytes())
        command = [sys.executable, "-B", "-X", "utf8", str(HERE / "check_binding.py"), "--artifact-root", str(root), "--expected-manifest-sha256", expected_sha]
        remaining = 60 - (time.monotonic() - start)
        if remaining <= 0:
            raise TimeoutError("new software selftest group exceeded 60 seconds")
        run = subprocess.run(command, cwd=REPO, capture_output=True, timeout=min(8, remaining), check=False)
        (case / "stdout.raw").write_bytes(run.stdout)
        (case / "stderr.raw").write_bytes(run.stderr)
        text = run.stdout.decode("utf-8", errors="replace")
        ok = run.returncode == expected_code and expected_text in text
        result = {"case": name, "argv": command, "cwd": str(REPO), "expected_exit": expected_code, "actual_exit": run.returncode, "expected_text": expected_text, "behavior_ok": ok, "stdout_sha256": sha(run.stdout), "stderr_sha256": sha(run.stderr)}
        dump(case / "CASE_RECEIPT.json", result)
        results.append(result)
    final = {"schema": "M2_NEW_STATIC_BINDING_CHECKER_SELFTEST_V1", "result": "PASS" if all(r["behavior_ok"] for r in results) else "FAIL", "level": "L0_SOFTWARE_CHECKER_ONLY", "elapsed_seconds": round(time.monotonic() - start, 6), "timebox_seconds": 60, "cases": results, "correct_cases": 1, "rejection_cases": 5, "old_test_groups_rerun": False, "compiler_or_eda_invoked": False, "pro_dut_pass": False, "board_release_allowed": False}
    dump(tests / "SELFTEST_RECEIPT.json", final)
    print(json.dumps(final, ensure_ascii=False, sort_keys=True))
    return 0 if final["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
