"""Create the requested local ABCD delivery; never stage or publish files."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    docs = ROOT / "code/docs/test"
    entries = {
        "A_REAL_R05_CAPTURE.zip": (
            docs / "m3_r05_functional_integration_20261015/night_20261016/RESUME_R02/SEAL_SUCCESS/M3_NIGHT_A_RESUME_R02_REAL_CAPTURE.zip",
            "e0e1d77840c353256bbbea18178a198367f234a19bc86f3cbe3fde2688938645"),
        "B_REUSED_DIRECTED_STA.zip": (
            docs / "m3_m2td_audio_endpoint_audit_20261015/successor_R03/delivery_night_r03/B_DIRECTED_STA_CANDIDATE_20261016.zip",
            "59f40000f25bccc492199e4a0f6e843e4a7ccf68ddaeab5823c756b888d44ce3"),
        "C_REAL_DIGITAL_VALIDATION.zip": (
            docs / "m3_40mhz_pcm_i2s_latency_20261015/night_20261016/RESUME_R02/SEAL_R01/C_R02_REAL_R05_DIGITAL_EVIDENCE.zip",
            "e894e81afa9fae37b71b52c245a11cfbe1fc4c617720728d23bc6acbf7952dd9"),
        "D_AUDIO_VISUAL_POSITIVE_AND_NEGATIVES.zip": (
            docs / "m3_dual_slider_138k_candidate_20261015/night_20261016/RESUME_R01/D_FOUR_RTL_NEGATIVES_COMPLETE_RESUME_R01_20261016.zip",
            "d95def3980b6f09daac320934244986419a756bddd6b505e5a2b715992e4f885"),
        "HISTORY/R01_ALL_FAILURES_AND_SOFTWARE.zip": (
            HERE.parent / "RESUME_R01/M3_NIGHT_RESUME_R01_HANDOFF_LOCAL_PARTIAL.zip",
            "9f7bd17a6a3044ccea7dadd4b439dabbcc2c16d9c75a2201b869c3132afd8616"),
    }
    contents = {}
    syntax_checked = 0
    for name, (path, expected) in entries.items():
        raw = path.read_bytes()
        assert sha(raw) == expected, path
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            if name.startswith(("A_", "C_", "D_")):
                for member in archive.namelist():
                    if "RESUME_R0" in member and member.endswith(".py"):
                        ast.parse(archive.read(member).decode("utf-8-sig"), filename=member)
                        syntax_checked += 1
        contents[name] = raw
    previous = json.loads((HERE.parent / "PUBLICATION_PLAN.json").read_text(encoding="utf-8"))
    for name, item in previous["file_identities"].items():
        raw = (ROOT / name).read_bytes()
        assert {"bytes": len(raw), "sha256": sha(raw)} == item, name
    previous_gate = json.loads((HERE.parent / "gate_R01/GATE_RECEIPT.json").read_text(encoding="utf-8"))
    cached = subprocess.check_output(["git", "diff", "--cached", "--binary"], cwd=ROOT)
    assert sha(cached) == previous_gate["before"]["staged_diff_sha256"]
    assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT)
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in (".md", ".txt", ".json", ".py"):
            assert not path.name.startswith("FINAL_BUNDLE_")
            contents["COORDINATOR/" + path.name] = path.read_bytes()
    state = {
        "status": "ABCD_LOCAL_LIMITED_SCOPE_EVIDENCE_COMPLETE_M2_REVIEW_PENDING",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "publication": "NOT_COMMITTED_NOT_PUSHED_USER_WILL_HANDLE_LATER",
        "A": {"group_consumed": 1, "group_limit": 3, "real_modelsim": "PASS", "ticks": 253456, "commits": 303},
        "B": {"scope": "FIVE_PAIRS_SETUP_HOLD_REUSED", "new_eda_calls": 0},
        "C": {"real_consumer": "PASS", "requests_before_next_frame": 303,
              "complete_stereo_frames": 302, "serial_observed_requests": 301,
              "reset_interrupted_serial_ids": [302, 303], "max_request_to_serial_last_bit_cycles": 1673,
              "damaged_trace_negatives_rejected": 10, "real_lr_swap_coverage": "NOT_PROVEN_L_EQUALS_R"},
        "D": {"scope": "DIAGNOSTIC_AUDIO_VISUAL_COEXISTENCE", "positive": "REUSED_PASS",
              "rtl_behavioral_negatives": 4, "resume_group_consumed": 1},
        "source_archive_python_ast_checks": syntax_checked,
        "previous_77_staged_tree_unchanged": True,
        "repository_gate": "PREVIOUS_77_TREE_9_OF_9_ONLY_NEW_PUBLICATION_GATE_DEFERRED",
        "startup_signoff": "UNKNOWN_NOT_SIGNED", "analog_latency": "NOT_MEASURED",
        "hardware_invocations": 0, "n32_new_work": 0, "board_release_allowed": False,
        "delivery": "FOUR_AI_WINDOWS_DELIVERED_TO_COORDINATOR_M2_WAITING_USER_FORWARD",
    }
    contents["LOCAL_DELIVERY_STATE.json"] = (json.dumps(state, indent=2) + "\n").encode()
    manifest = {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in contents.items()}
    with (HERE / "FINAL_BUNDLE_MANIFEST.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2)
        stream.write("\n")
    contents["FINAL_BUNDLE_MANIFEST.json"] = (HERE / "FINAL_BUNDLE_MANIFEST.json").read_bytes()
    output = HERE / "M3_ABCD_LOCAL_DELIVERY_20261016.zip"
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, raw in contents.items():
            archive.writestr(name, raw)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for name, raw in contents.items():
            assert archive.read(name) == raw, name
    receipt = {"path": str(output), "bytes": output.stat().st_size,
               "sha256": sha(output.read_bytes()), "status": state["status"],
               "members_verified": len(contents), "previous_77_staged_tree_unchanged": True,
               "publication": state["publication"]}
    with (HERE / "FINAL_BUNDLE_SHA.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
