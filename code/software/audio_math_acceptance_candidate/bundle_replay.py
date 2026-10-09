"""Read-only intake and boundary audio regression of the received V0208 bundle.

No extraction, old checker execution, capture rewriting or source modification.
Each of the56 negatives runs the same checker in a bounded child process.
All56 supplied mutations require their specified diagnostic, not generic exit1.
"""
import argparse
import base64
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from strict_capture import require

ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT / "code/rtl/138K_try/clock_trials_20261005/H_pll_core40_route2"
RECEIVED_ROM_PREFIX = "C:/Users/Angel17/.codex/worktrees/m2-138k-migration/fpga_gowin/code/output/platform_preparation_20261005/capture2/rom/"
FROZEN_PREFIX = "E:/FPGA/GAOYUNFPGA/138K_try/clock_trials_20261005/H_pll_core40_route2/"
PINNED = {"audio_observation.jsonl": "d17cf87952ac0c663e681e0b47051e9412af4a2979fb509aaa5d7114d5b32cc5",
          "midi_pcm.capture": "bd0035de464cb8c757c7e29a132073181e9e8179aa8303ab1ec110c6990042d6"}
# Expected diagnostic classes describe the supplied, frozen mutations. The
# misleading END_wrong_nonzero_count case changes END.total, not nonzero_left.
EXPECTED = {
    "adsr_level_plus3": "ENVELOPE_level_q16", "legal_wrong_envelope": "ENVELOPE_envelope",
    "wrong_envelope_field": "ENVELOPE_envelope",
    "duplicate_commit": "ORPHAN_OR_DUPLICATE_COMMIT", "duplicate_request": "DUPLICATE_REQUEST",
    "duplicate_state_adjusted_end": "DUPLICATE_STATE_LANE", "empty": "EMPTY_",
    "legal_wrong_fcw": "D_STATE_FCW_TRANSPORT", "legal_wrong_phase": "DDS_phase_acc",
    "legal_wrong_table": "DDS_table", "meta_only": "MISSING_JSON_END", "missing_end": "MISSING_JSON_END",
    "missing_end_counts": "END_COUNT_KEYS", "missing_first_reset_adjusted_end": "JSON_EPOCH_BINDING",
    "missing_lane_state_adjusted_end": "TICK_STATE_MISSING_LANE", "no_states_with_matching_end": "EMPTY_JSON_TRANSACTION_SET",
    "orphan_commit": "ORPHAN_OR_DUPLICATE_COMMIT", "pcm_out_of_range": "INTEGER_RANGE:pcm_left",
    "unknown_record": "UNKNOWN_JSON_TAG", "wrong_dds_fcw": "D_STATE_FCW_TRANSPORT",
    "wrong_end_commit": "END_COUNTS", "wrong_end_request": "END_COUNTS", "wrong_end_reset": "END_COUNTS",
    "wrong_end_state": "END_COUNTS", "wrong_pending_request_id": "TICK_WITHOUT_PENDING_REQUEST",
    "wrong_phase_acc": "DDS_phase_acc", "wrong_raw_state": "STATE_ENUM_MAPPING", "wrong_reset_epoch": "RESET_EPOCH_ORDER",
    "wrong_sample_hz": "META_PROFILE", "wrong_schema": "META_PROFILE", "wrong_sys_hz": "META_PROFILE",
    "wrong_table": "INTEGER_RANGE:table", "after_END": "F_RECORD_AFTER_END", "allowed_letter_garbage": "UNKNOWN_F_TAG:X",
    "duplicate_END": "F_RECORD_AFTER_END", "END_no_counts": "F_END_ARITY", "END_wrong_nonzero_count": "F_END_TOTAL",
    "extra_M_field": "F_ARITY:M", "missing_first_R": "F_BEFORE_RESET", "negative_R_cycle": "DECIMAL_TOKEN:cycle",
    "no_END": "MISSING_F_END", "no_M": "EMPTY_F_COMMIT_SET", "reordered_M_pair": "F_CYCLE_ORDER",
    "unknown_tag": "UNKNOWN_F_TAG:CORRUPT", "wrong_clip": "M_FIXTURE_KNOWN_ZERO",
    "coherent_zero_fcw_and_phase": "D_STATE_FCW_TRANSPORT", "END_negative_total": "DECIMAL_TOKEN:END",
    "END_nonzero_left_count_plus1": "F_END_NONZERO_LEFT", "first_R_cycle_zero": "F_CYCLE_ORDER",
    "fixture_select9": "INTEGER_RANGE:M", "R_epoch_zero": "F_RESET_EPOCH", "raw_boolean": "INTEGER_RANGE:raw_state",
    "raw15": "INTEGER_RANGE:raw_state", "terminal_lane_fcw_plus1": "D_STATE_FCW_TRANSPORT",
    "tick0_no_event": "STATE_WITHOUT_TRIGGER",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inventory(bundle):
    return [{"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}
            for path in sorted(bundle.rglob("*")) if path.is_file()]


def canonical_source(text, received):
    # Exact original path adaptations only, NOT a regex over arbitrary strings.
    if received:
        return text.replace(RECEIVED_ROM_PREFIX, "__FROZEN_ROM__/")
    text = text.replace(FROZEN_PREFIX + "rom/", "__FROZEN_ROM__/")
    for name in ("sine_table.svh", "sustain_controller_ports.svh"):
        text = text.replace('"' + FROZEN_PREFIX + "include/" + name + '"', '"' + name + '"')
    return text


def validate_bundle(bundle):
    for name, digest in PINNED.items():
        require(sha((bundle / "original_Golden" / name).read_bytes()) == digest, "ORIGINAL_RAW_SHA:" + name)
    evidence = bundle / "M2_evidence"
    manifest = json.loads((evidence / "raw_manifest.json").read_text(encoding="utf-8"))
    decoded = {}
    for name, entry in manifest.items():
        require(Path(name).name == name, "CARRIER_PATH")
        carrier = (evidence / name).read_bytes()
        require(sha(carrier) == entry["carrier_sha256"], "CARRIER_SHA:" + name)
        raw = gzip.decompress(base64.b64decode(carrier, validate=False))
        require(len(raw) == entry["raw_bytes"] and sha(raw) == entry["raw_sha256"], "CARRIER_RAW_SHA:" + name)
        decoded[name] = raw
    sources = sorted((bundle / "readonly_frozen_sources").glob("*"))
    require({path.name for path in sources} == {p.name for p in (FROZEN / "sources").glob("*") if p.is_file()},
            "FROZEN_SOURCE_FILE_SET")
    source_checks = []
    for path in sources:
        actual = path.read_text(encoding="utf-8")
        expected = (FROZEN / "sources" / path.name).read_text(encoding="utf-8")
        require(canonical_source(actual, True) == canonical_source(expected, False), "SOURCE_BODY_IDENTITY:" + path.name)
        source_checks.append({"name": path.name, "raw_sha256": sha(path.read_bytes()),
                              "body_sha256": sha(canonical_source(actual, True).encode("utf-8")),
                              "path_adapted": actual != expected})
    rom_identity = json.loads(decoded["temporal_DDS_source_review.json.gz.b64"])["ROM_identity"]
    for name, entry in rom_identity.items():
        raw = (bundle / "readonly_frozen_rom" / name).read_bytes()
        require(len(raw) == entry["bytes"] and sha(raw) == entry["sha256"], "RECEIVED_ROM_RAW_SHA:" + name)
        require(raw.replace(b"\r\n", b"\n") == (FROZEN / "rom" / name).read_bytes().replace(b"\r\n", b"\n"),
                "ROM_LF_IDENTITY:" + name)
    require(len(rom_identity) == 7, "ROM_COUNT")
    for received, repo in (("observer.sv.in", "code/tb/board/platform_audio_acceptance_20261005/observer.sv.in"),
                          ("tb_midi_pcm.sv", "code/tb/board/m3_midi_pcm_acceptance/tb_midi_pcm.sv")):
        require((bundle / "readonly_TB" / received).read_text(encoding="utf-8") ==
                (ROOT / repo).read_text(encoding="utf-8"), "OBSERVER_TB_TEMPLATE_IDENTITY:" + received)
    counts = {folder: len(list((bundle / folder).glob("*." + extension)))
              for folder, extension in (("previous32_JSONL", "jsonl"), ("previous14_F", "capture"))}
    counts["additional10"] = len([p for p in (bundle / "additional10").iterdir()
                                  if p.suffix in (".jsonl", ".capture")])
    require(counts == {"previous32_JSONL": 32, "previous14_F": 14, "additional10": 10}, "MISSING_56_NEGATIVES")
    return {"carrier_records_verified": len(manifest), "source_checks": source_checks,
            "rom_raw_and_lf_identity_verified": 7, "negative_counts": counts,
            "tb_scope": "Original templates only; exact generated capture2 TB/observer not provided"}


def command(bundle, jsonl, f_capture, timeout):
    cmd = [sys.executable, "-B", "-X", "utf8", str(Path(__file__).with_name("check_pair.py")),
           "--jsonl", str(jsonl), "--f-capture", str(f_capture),
           "--rom-root", str(bundle / "readonly_frozen_rom")]
    start = time.monotonic()
    process = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=timeout, check=False)
    try:
        result = json.loads(process.stdout.decode("utf-8"))
    except (ValueError, UnicodeError):
        result = {"status": "INFRASTRUCTURE_ERROR", "error": "CHILD_WITHOUT_JSON_RECEIPT"}
    return {"command": cmd, "cwd": str(ROOT), "exit_code": process.returncode,
            "elapsed_seconds": round(time.monotonic() - start, 6), "result": result,
            "stdout_base64": base64.b64encode(process.stdout).decode("ascii"),
            "stderr_base64": base64.b64encode(process.stderr).decode("ascii"),
            "stdout_sha256": sha(process.stdout), "stderr_sha256": sha(process.stderr)}


def mutation_summary(path, positive):
    """Report actual changed fields/lines; no original input is edited."""
    before = positive.read_text(encoding="utf-8").splitlines()
    after = path.read_text(encoding="utf-8").splitlines()
    fields, examples, changed = Counter(), [], 0
    for index in range(max(len(before), len(after))):
        old = before[index] if index < len(before) else None
        new = after[index] if index < len(after) else None
        if old == new:
            continue
        changed += 1
        if path.suffix == ".jsonl" and old is not None and new is not None:
            try:
                a, b = json.loads(old), json.loads(new)
                for key in set(a) | set(b):
                    if a.get(key) != b.get(key):
                        fields[key] += 1
            except ValueError:
                fields["invalid_json_text"] += 1
        elif old is not None and new is not None:
            for token in range(max(len(old.split()), len(new.split()))):
                a, b = old.split(), new.split()
                if (a[token] if token < len(a) else None) != (b[token] if token < len(b) else None):
                    fields[f"{a[0]}.token{token}"] += 1
        if len(examples) < 2:
            examples.append({"line": index + 1, "before": old, "after": new})
    return {"changed_lines": changed, "before_lines": len(before), "after_lines": len(after),
            "changed_fields_or_tokens": dict(fields), "first_examples": examples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    args = parser.parse_args()
    bundle = args.bundle_root.resolve()
    started = time.monotonic()
    report = {"status": "FAIL", "a1_complete": False, "a2_complete": False, "t060_complete": False}
    exit_code = 1
    try:
        report["bundle_inputs"] = inventory(bundle)
        report["intake"] = validate_bundle(bundle)
        original_json = bundle / "original_Golden/audio_observation.jsonl"
        original_f = bundle / "original_Golden/midi_pcm.capture"
        positive = command(bundle, original_json, original_f, 30)
        report["positive"] = positive
        require(positive["exit_code"] == 0 and positive["result"]["status"] == "PARTIAL_A2_AUDIO_MATH", "POSITIVE_AUDIO_REPLAY_FAILED")
        cases = []
        for folder in ("previous32_JSONL", "previous14_F", "additional10"):
            for path in sorted((bundle / folder).iterdir()):
                if path.suffix not in (".jsonl", ".capture"):
                    continue
                require(time.monotonic() - started < 850, "BUNDLE_REGRESSION_TIMEOUT")
                case = command(bundle, path if path.suffix == ".jsonl" else original_json,
                               path if path.suffix == ".capture" else original_f, 30)
                case["case"] = str(path.relative_to(bundle))
                case["input_sha256"] = sha(path.read_bytes())
                original = original_json if path.suffix == ".jsonl" else original_f
                case["differs_from_positive"] = path.read_bytes() != original.read_bytes()
                case["actual_mutation"] = mutation_summary(path, original)
                require(case["differs_from_positive"], "NEGATIVE_EQUALS_POSITIVE:" + case["case"])
                if case["exit_code"] == 1 and case["result"]["status"] == "REJECTED_CONTRACT_OR_MATH":
                    expected = EXPECTED.get(path.stem)
                    case["expected_diagnostic_prefix"] = expected
                    case["disposition"] = ("REJECTED_WITH_SPECIFIED_DIAGNOSTIC" if expected and
                                           case["result"]["diagnostic"].startswith(expected) else "WRONG_REJECTION_DIAGNOSTIC")
                elif case["exit_code"] == 0 and case["result"]["status"] == "PARTIAL_A2_AUDIO_MATH":
                    case["disposition"] = "UNEXPECTED_ACCEPTED_NEGATIVE"
                else:
                    case["disposition"] = "INFRASTRUCTURE_FAILURE_NOT_REJECTION"
                cases.append(case)
        report["negative_cases"] = cases
        report["negative_dispositions"] = dict(Counter(c["disposition"] for c in cases))
        require(len(cases) == 56, "NEGATIVE_RUN_COUNT")
        require(all(c["disposition"] == "REJECTED_WITH_SPECIFIED_DIAGNOSTIC" for c in cases),
                "NEGATIVE_DIAGNOSTIC_OR_UNEXPECTED_ACCEPTANCE_FAILURE")
        require(inventory(bundle) == report["bundle_inputs"], "BUNDLE_CHANGED_DURING_RUN")
        report["status"], exit_code = "PARTIAL_RECEIVED_A2_REGRESSION", 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    report.update(exit_code=exit_code, elapsed_seconds=round(time.monotonic() - started, 6))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
