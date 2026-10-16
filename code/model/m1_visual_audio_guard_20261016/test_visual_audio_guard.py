"""Bounded directed unittest cases, with one original CLI receipt per case."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

import visual_audio_guard as guard


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def save_new(path, value):
    with path.open("xb") as stream:
        stream.write(value)


def synthetic_frames(basis_sha, events_sha):
    """A test calendar and PCM symbols, never a claim of A/RTL PCM capture."""
    rows = []
    seq = 0
    epoch = 0
    frame = -1
    was_reset = True
    pcm_symbols = [100, -100, (1 << 23) - 1, -(1 << 23), 0, 55]
    for index in range(12):
        cycle = 1000 + (index * 2500) // 3
        in_reset = index in (0, 1, 8, 9)
        if in_reset and not was_reset:
            epoch += 1
            frame = -1
        frame += 1
        if in_reset:
            seq = 0
            pcm = 0
            clip_count = 0
        else:
            seq += 1
            pcm = pcm_symbols[(seq - 1) % len(pcm_symbols)]
            clip_count = min(max(seq - 2, 0), 2)
        rows.append({
            "epoch": epoch, "frame": frame, "cycle": cycle,
            "rst_n": int(not in_reset), "commit_seq": seq,
            "commit_id": seq if seq else None,
            "commit_cycle": cycle - 20 if seq else None,
            "pcm_left": pcm, "pcm_right": -pcm if abs(pcm) < (1 << 23) else 0,
            "underflow": 0, "clip_count": clip_count,
        })
        was_reset = in_reset
    return {
        "schema": guard.FRAME_SCHEMA,
        "source_kind": "SYNTHETIC_FRAME_CONTRACT_ONLY",
        "clock_hz": 40_000_000, "sample_rate_hz": 48_000,
        "input_events_sha256": events_sha, "basis_sha256": basis_sha,
        "window": {"first_cycle": rows[0]["cycle"], "last_cycle": rows[-1]["cycle"], "expected_frames": len(rows)},
        "frames": rows,
    }


def make_cases(base, contract):
    cases = []

    def add(name, mutate=None, marker=None, target="after", raw=None, existing_output=False):
        values = {"before": copy.deepcopy(base), "after": copy.deepcopy(base), "contract": copy.deepcopy(contract)}
        if mutate:
            mutate(values[target])
        payloads = {key: encoded(value) for key, value in values.items()}
        if raw is not None:
            payloads[target] = raw
        cases.append({"name": name, "inputs": payloads, "expected_exit": 0 if marker is None else 2, "marker": marker, "existing_output": existing_output})

    add("identical_complete_window")
    # A second positive case keeps a baseline underflow visible in both streams.
    known = copy.deepcopy(base)
    _known_underflow(known)
    cases.append({"name": "known_identical_underflow", "inputs": {"before": encoded(known), "after": encoded(known), "contract": encoded(contract)}, "expected_exit": 0, "marker": None, "existing_output": False})
    add("missing_middle", lambda d: d["frames"].pop(4), "incomplete frame count")
    add("missing_tail", lambda d: d["frames"].pop(), "incomplete frame count")
    add("missing_first", lambda d: d["frames"].pop(0), "incomplete frame count")
    add("duplicate_frame", lambda d: d["frames"].__setitem__(4, copy.deepcopy(d["frames"][3])), "cycle not strictly increasing")
    add("wrong_frame", lambda d: d["frames"][4].__setitem__("frame", 77), "missing/duplicate/reordered frame")
    add("wrong_epoch", lambda d: d["frames"][8].__setitem__("epoch", 0), "missing/duplicate/reordered frame")
    add("new_underflow", lambda d: d["frames"][4].__setitem__("underflow", 1), "mismatch at underflow")
    add("wrong_reset", lambda d: d["frames"][4].__setitem__("rst_n", 0), "reset row not cleared")
    add("wrong_commit_id", lambda d: d["frames"][4].__setitem__("commit_id", 99), "new commit_id not increasing")
    add("wrong_final_commit_id", lambda d: d["frames"][11].__setitem__("commit_id", 99), "mismatch at commit_id")
    add("wrong_commit_cycle", lambda d: d["frames"][4].__setitem__("commit_cycle", d["frames"][4]["commit_cycle"] + 1), "mismatch at commit_cycle")
    add("wrong_pcm_left", lambda d: d["frames"][4].__setitem__("pcm_left", d["frames"][4]["pcm_left"] - 1), "mismatch at pcm_left")
    add("wrong_pcm_right", lambda d: d["frames"][4].__setitem__("pcm_right", d["frames"][4]["pcm_right"] + 1), "mismatch at pcm_right")
    add("wrong_clip_count", lambda d: d["frames"][4].__setitem__("clip_count", 0), "mismatch at clip_count")
    add("regressed_clip_count", lambda d: d["frames"][5].__setitem__("clip_count", 0), "clip_count regressed")
    add("pcm_out_of_range", lambda d: d["frames"][4].__setitem__("pcm_left", 1 << 23), "integer outside")
    add("negative_counter", lambda d: d["frames"][4].__setitem__("clip_count", -1), "integer outside")
    add("bool_as_pcm", lambda d: d["frames"][4].__setitem__("pcm_left", True), "integer outside")
    add("bool_as_clock", lambda d: d.__setitem__("clock_hz", True), "integer outside")
    add("bool_as_sequence", lambda d: d["frames"][4].__setitem__("commit_seq", True), "integer outside")
    add("float_as_pcm", lambda d: d["frames"][4].__setitem__("pcm_left", 1.0), "integer outside")
    add("unknown_root_field", lambda d: d.__setitem__("extra", 0), "expected exact keys")
    add("missing_row_field", lambda d: d["frames"][4].pop("underflow"), "expected exact keys")
    add("unknown_window_field", lambda d: d["window"].__setitem__("extra", 0), "expected exact keys")
    add("bool_as_expected_frames", lambda d: d["window"].__setitem__("expected_frames", True), "integer outside", "contract")
    add("wrong_events_identity", lambda d: d.__setitem__("input_events_sha256", "0" * 64), "frozen contract mismatch at input_events_sha256")
    add("wrong_basis_identity", lambda d: d.__setitem__("basis_sha256", "0" * 64), "frozen contract mismatch at basis_sha256")
    add("basis_file_mismatch", lambda d: d.__setitem__("basis_sha256", "0" * 64), "actual A basis file SHA mismatch", "contract")
    add("wrong_sample_rate", lambda d: d.__setitem__("sample_rate_hz", 44_100), "expected 48000")
    add("missing_last_boundary", lambda d: d["window"].__setitem__("last_cycle", d["window"]["last_cycle"] + 1), "frozen contract mismatch at window")
    add("null_commit_identity", lambda d: d["frames"][4].__setitem__("commit_id", None), "nonzero sequence lacks commit identity")
    add("identity_without_commit", lambda d: d["frames"][0].__setitem__("commit_id", 1), "zero sequence has commit identity")
    add("future_commit", lambda d: d["frames"][4].__setitem__("commit_cycle", d["frames"][4]["cycle"] + 1), "commit later than observation")
    add("old_new_commit", lambda d: d["frames"][4].__setitem__("commit_cycle", d["frames"][3]["cycle"]), "new commit not in observed interval")
    add("skipped_commit_seq", lambda d: d["frames"][4].__setitem__("commit_seq", 5), "commit sequence skipped or regressed")
    add("pcm_without_new_commit", lambda d: d["frames"][4].__setitem__("commit_seq", 2), "changed commit_id without new commit")
    add("bad_frame_cadence", lambda d: d["frames"][5].__setitem__("cycle", d["frames"][5]["cycle"] + 10), "frame cadence outside")
    add("null_root", raw=b"null\n", marker="expected exact keys")
    add("duplicate_root_key", raw=encoded(base).replace(b'"schema":', b'"schema": "ignored", "schema":', 1), marker="duplicate JSON key")
    add("duplicate_nested_key", raw=encoded(base).replace(b'"underflow": 0', b'"underflow": 0, "underflow": 0', 1), marker="duplicate JSON key")
    add("nan_pcm", raw=encoded(base).replace(b'"pcm_left": 100', b'"pcm_left": NaN', 1), marker="non-finite JSON number")
    add("infinity_pcm", raw=encoded(base).replace(b'"pcm_left": 100', b'"pcm_left": Infinity', 1), marker="non-finite JSON number")
    add("negative_infinity_pcm", raw=encoded(base).replace(b'"pcm_left": 100', b'"pcm_left": -Infinity', 1), marker="non-finite JSON number")
    add("overflow_float_pcm", raw=encoded(base).replace(b'"pcm_left": 100', b'"pcm_left": 1e999', 1), marker="integer outside")
    add("real_synthetic_mixed", lambda d: d.__setitem__("source_kind", "REAL_CAPTURE_DERIVED"), "source_kind differs")
    add("output_exists", marker="File exists", existing_output=True)
    # Both streams self-report a shorter window, but cannot override the plan.
    shorter = copy.deepcopy(base)
    shorter["frames"].pop()
    shorter["window"]["expected_frames"] -= 1
    shorter["window"]["last_cycle"] = shorter["frames"][-1]["cycle"]
    cases.append({"name": "both_streams_truncated", "inputs": {"before": encoded(shorter), "after": encoded(shorter), "contract": encoded(contract)}, "expected_exit": 2, "marker": "frozen contract mismatch at window", "existing_output": False})
    reset_only = copy.deepcopy(base)
    for index, row in enumerate(reset_only["frames"]):
        row.update(epoch=0, frame=index, rst_n=0, commit_seq=0, commit_id=None, commit_cycle=None, pcm_left=0, pcm_right=0, underflow=0, clip_count=0)
    cases.append({"name": "all_reset_no_active_commit", "inputs": {"before": encoded(reset_only), "after": encoded(reset_only), "contract": encoded(contract)}, "expected_exit": 2, "marker": "no active committed frame", "existing_output": False})
    return cases


def _known_underflow(document):
    previous = document["frames"][5]
    for key in ("commit_seq", "commit_id", "commit_cycle", "pcm_left", "pcm_right"):
        document["frames"][6][key] = previous[key]
    document["frames"][6]["underflow"] = 1
    document["frames"][7]["commit_seq"] -= 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis", type=Path, required=True)
    parser.add_argument("--basis-sha256", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    basis = args.basis.resolve()
    if guard.sha256_file(basis) != args.basis_sha256:
        parser.error("frozen A basis SHA mismatch")
    root = args.evidence_dir.resolve()
    root.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    guard_path = Path(guard.__file__).resolve()
    test_path = Path(__file__).resolve()
    sources = {str(path): guard.sha256_file(path) for path in (basis, guard_path, test_path, Path(sys.executable).resolve())}
    event_bytes = encoded({
        "schema": "M1_VISUAL_AUDIO_SYNTHETIC_EVENT_CALENDAR_V1",
        "purpose": "Frame-contract symbols only; no physical or RTL event replay",
        "clock_hz": 40_000_000,
        "events": [{"cycle": 2000, "event": "TEST_ACTIVE_WINDOW"}, {"cycle": 7600, "event": "TEST_RESET_WINDOW"}, {"cycle": 9000, "event": "TEST_ACTIVE_WINDOW"}],
        "basis_scope": "A mathematical contract identity; this calendar differs from A settled-event examples",
    })
    save_new(root / "synthetic_events.json", event_bytes)
    base = synthetic_frames(args.basis_sha256, digest(event_bytes))
    contract = {key: copy.deepcopy(base[key]) for key in guard.CONTRACT_KEYS}
    contract["schema"] = guard.CONTRACT_SCHEMA
    cases = make_cases(base, contract)
    records = []

    class DirectedCLI(unittest.TestCase):
        def execute(self, case):
            remaining = 90 - (time.monotonic() - started)
            self.assertGreater(remaining, 0, "90 s suite budget consumed")
            directory = root / case["name"]
            directory.mkdir()
            for name, raw in case["inputs"].items():
                save_new(directory / (name + ".json"), raw)
            output = directory / "comparison.json"
            if case["existing_output"]:
                save_new(output, b"DO_NOT_OVERWRITE\n")
            command = [sys.executable, "-X", "utf8", "-B", str(guard_path), "--before", str(directory / "before.json"), "--after", str(directory / "after.json"), "--contract", str(directory / "contract.json"), "--basis", str(basis), "--output", str(output)]
            case_start = time.monotonic()
            timed_out = False
            try:
                completed = subprocess.run(command, cwd=str(guard_path.parent), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=min(10, remaining), check=False)
                stdout, stderr, exit_code = completed.stdout, completed.stderr, completed.returncode
            except subprocess.TimeoutExpired as exc:
                stdout, stderr, exit_code = exc.stdout or b"", exc.stderr or b"", None
                timed_out = True
            save_new(directory / "stdout.bin", stdout)
            save_new(directory / "stderr.bin", stderr)
            record = {
                "case": case["name"], "argv": command, "cwd": str(guard_path.parent),
                "expected_exit": case["expected_exit"], "exit_code": exit_code,
                "timed_out": timed_out, "elapsed_seconds": round(time.monotonic() - case_start, 6),
                "files": {path.name: {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size} for path in sorted(directory.iterdir()) if path.is_file()},
                "expected_rejection_marker": case["marker"],
            }
            records.append(record)
            save_new(directory / "receipt.json", encoded(record))
            self.assertFalse(timed_out)
            self.assertEqual(exit_code, case["expected_exit"], stderr.decode("utf-8", "replace"))
            if exit_code == 0:
                result = guard.read_json(output)
                self.assertEqual(result["comparison_result"], "FRAME_CONTRACT_EQUAL")
                self.assertEqual(result["real_result"], "PENDING_REAL_CAPTURE")
                self.assertFalse(result["board_release_allowed"])
                self.assertEqual(result["visual_audio_nondegradation"], "NOT_SIGNED_BY_THIS_SOFTWARE")
            else:
                self.assertIn(case["marker"].lower(), stderr.decode("utf-8", "replace").lower())
                if case["existing_output"]:
                    self.assertEqual(output.read_bytes(), b"DO_NOT_OVERWRITE\n")
                else:
                    self.assertFalse(output.exists(), "rejection must not write a success output")

    for case in cases:
        def directed(self, selected=case):
            self.execute(selected)
        setattr(DirectedCLI, "test_" + case["name"], directed)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DirectedCLI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    after_sources = {path: guard.sha256_file(Path(path)) for path in sources}
    unchanged = sources == after_sources
    report = {
        "schema": "M1_VISUAL_AUDIO_GUARD_SOFTWARE_SELFTEST_V1",
        "started_utc": started_utc,
        "argv": [sys.executable] + sys.argv,
        "cwd": str(Path.cwd()), "python_version": sys.version,
        "test_count": result.testsRun, "accepted_cases": sum(r["expected_exit"] == 0 for r in records),
        "rejection_cases": sum(r["expected_exit"] == 2 for r in records),
        "failures": len(result.failures), "errors": len(result.errors),
        "source_before_sha256": sources, "source_after_sha256": after_sources,
        "source_unchanged": unchanged, "elapsed_seconds": round(time.monotonic() - started, 6),
        "case_receipts": [case["name"] + "/receipt.json" for case in cases],
        "basis_sha256": args.basis_sha256, "input_events_sha256": digest(event_bytes),
        "real_result": "PENDING_REAL_CAPTURE", "board_release_allowed": False,
        "result": "SOFTWARE_SELFTEST_ACCEPTED" if result.wasSuccessful() and unchanged else "SOFTWARE_SELFTEST_FAILED",
    }
    save_new(root / "SELFTEST_SUMMARY.json", encoded(report))
    print(json.dumps({"result": report["result"], "test_count": result.testsRun, "real_result": report["real_result"]}))
    return 0 if result.wasSuccessful() and unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
