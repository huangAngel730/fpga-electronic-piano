"""Pure software policy/ledger/supervisor tests, never call ModelSim/RTL."""
from copy import deepcopy
from pathlib import Path
import json
import os
import tempfile
import time
import unittest
import sys

from common import DOCS, Refusal, json_load, json_bytes, PASS_MARKER, write_new
from input_binding import inspect_archive
from public_ledger import analyze
from receipt_check import check_step
from supervised_process import invoke


GOOD = (
    b"# END REAL_M1 accepted=6 active=4 commits=200 nonzero=190 frames=201 serial=1000 max_cycles=155\n"
    + ("# " + PASS_MARKER + "\n").encode()
)


def ledger_fixture():
    records = [{"kind": "HEADER", "schema": "M3_R05_PUBLIC_PRE_NBA_V1", "clock_hz": 40000000, "first_valid_observable": False}]
    clip = 0
    for cycle in range(1, 2601):
        r = {
            "kind": "TICK", "cycle": cycle, "epoch": 0, "rst_n": 1,
            "frame_tick": int(cycle in (1, 834, 1667, 2501)),
            "request_accept": int(cycle in (2, 835, 1668)), "request_id": 0 if cycle < 834 else 1 if cycle < 1667 else 2,
            "commit": int(cycle in (10, 850)), "committed_id": 0 if cycle < 834 else 1,
            "left": -1000, "right": 1000, "clipped": int(cycle == 10),
            "pending": 0, "play_left": 0, "play_right": 0, "clip_count": clip,
            "underflow": 0, "bclk": 0, "ws": 0, "din": 0, "first_valid": None,
        }
        records.append(r)
        if cycle == 10:
            clip += 1
    records.append({"kind": "END", "cycle": 2600, "epoch": 0})
    return records


def encoded(records):
    return b"".join((json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8") for r in records)


class PolicyTests(unittest.TestCase):
    def refusal(self, expected, callback):
        with self.assertRaises(Refusal) as error:
            callback()
        self.assertEqual(error.exception.code, expected)

    def test_synthetic_positive_policy_not_real_signoff(self):
        result = check_step("vsim", GOOD, b"", 0, False, synthetic=True)
        self.assertEqual(result["evidence_kind"], "SYNTHETIC_SOFTWARE_TEST")
        self.assertFalse(result["board_release_allowed"])

    def test_all_error_diagnostics_both_streams_and_positions(self):
        for diag in (b"Error: synthetic", b"Errors: 1", b"Errors: 01", b"Errors: 0001", b"** Failure: synthetic", b"FATAL: synthetic", b"assertion failed: synthetic"):
            for before in (True, False):
                for side in (0, 1):
                    with self.subTest(diag=diag, before=before, side=side):
                        out, err = GOOD, b""
                        if side == 0:
                            out = diag + b"\n" + out if before else out + diag + b"\n"
                        else:
                            err = diag + b"\n"
                        self.refusal("TOOL_DIAGNOSTIC", lambda: check_step("vsim", out, err, 0, False, synthetic=True))

    def test_zero_errors_with_leading_zero_accepted(self):
        for line in (b"Errors: 0", b"Errors: 00", b"Errors: 000"):
            self.assertEqual(check_step("vsim", GOOD, line, 0, False, synthetic=True)["status"], "STEP_LOG_POLICY_PASS")

    def test_nonzero_and_strict_types(self):
        for code in (1, -1, False, "0", None):
            self.refusal("NONZERO_OR_INVALID_EXIT", lambda: check_step("vsim", GOOD, b"", code, False, synthetic=True))

    def test_timeout_flags(self):
        for flag in (True, 0, "false", None):
            self.refusal("TIMEOUT_OR_INVALID_FLAG", lambda: check_step("vsim", GOOD, b"", 0, flag, synthetic=True))

    def test_fake_pass_substring_and_cross_stream(self):
        for replacement in ("NOT " + PASS_MARKER, PASS_MARKER + " garbage", "garbage " + PASS_MARKER):
            out = GOOD.replace(PASS_MARKER.encode(), replacement.encode())
            self.refusal("EXACT_PASS_MISSING_OR_DUPLICATE", lambda: check_step("vsim", out, b"", 0, False, synthetic=True))
        out, err = GOOD.split(("# " + PASS_MARKER).encode())
        self.refusal("EXACT_PASS_MISSING_OR_DUPLICATE", lambda: check_step("vsim", out, PASS_MARKER.encode() + err, 0, False, synthetic=True))

    def test_missing_duplicate_pass(self):
        for out in (GOOD.replace(PASS_MARKER.encode(), b"none"), GOOD + (PASS_MARKER + "\n").encode()):
            self.refusal("EXACT_PASS_MISSING_OR_DUPLICATE", lambda: check_step("vsim", out, b"", 0, False, synthetic=True))

    def test_x_summary_and_834_rejected(self):
        self.refusal("SUMMARY_MISSING_OR_X", lambda: check_step("vsim", GOOD.replace(b"active=4", b"active=x"), b"", 0, False, synthetic=True))
        self.refusal("R05_SUMMARY_PREDICATE", lambda: check_step("vsim", GOOD.replace(b"max_cycles=155", b"max_cycles=834"), b"", 0, False, synthetic=True))
        self.assertEqual(check_step("vsim", GOOD.replace(b"max_cycles=155", b"max_cycles=833"), b"", 0, False, synthetic=True)["status"], "STEP_LOG_POLICY_PASS")

    def test_synthetic_cannot_be_real_log(self):
        self.refusal("SYNTHETIC_RECEIPT", lambda: check_step("vsim", GOOD + b"SYNTHETIC\n", b"", 0, False))

    def test_duplicate_json(self):
        self.refusal("DUPLICATE_KEY", lambda: json_load(b'{"x":1,"x":2}'))

    def test_duplicate_consumption_rejected(self):
        DOCS.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="SYNTHETIC_CONSUME_", dir=DOCS))
        marker = folder / "SYNTHETIC_ONLY_CONSUMED.json"
        write_new(marker, {"synthetic": True})
        with self.assertRaises(FileExistsError):
            write_new(marker, {"synthetic": True})

    def test_exact_r05_binding(self):
        _, result = inspect_archive()
        self.assertEqual(result["declared_members"], 91)
        self.assertEqual(len(result["compile_units"]), 69)
        self.assertEqual(len(result["rom_members"]), 9)
        self.assertEqual(result["same_version_counts"]["ROM_PATH_RELOCATION_ONLY_REVERSED_TO_PHYSICAL_SHA"], 15)

    def test_ledger_positive_precise_frame_distribution(self):
        result = analyze(encoded(ledger_fixture()))
        self.assertEqual(result["accepted"], 3)
        self.assertEqual(result["committed"], 2)
        self.assertEqual(result["cancelled"], 1)
        self.assertEqual(result["frame_intervals"], [833, 833, 834])
        self.assertEqual(result["commits_with_observed_next_frame_deadline"], 2)

    def test_ledger_missing_repeated_rows(self):
        records = ledger_fixture()
        for altered in (records[:100] + records[101:], records[:100] + [records[99]] + records[100:]):
            self.refusal("CAPTURE_ORDER", lambda: analyze(encoded(altered)))

    def test_ledger_x_and_strict_bits(self):
        for value in ("x", None, False):
            records = ledger_fixture()
            records[10]["clipped"] = value
            self.refusal("CAPTURE_X_OR_TYPE", lambda: analyze(encoded(records)))

    def test_ledger_stale_commit_underflow_clip(self):
        for field, value, expected in (
            ("committed_id", 99, "STALE_OR_DUPLICATE_COMMIT"),
            ("underflow", 1, "UNDERFLOW"), ("clip_count", 9, "CLIP_COUNT_ALIGNMENT"),
        ):
            records = ledger_fixture()
            records[10][field] = value
            self.refusal(expected, lambda: analyze(encoded(records)))

    def test_ledger_frame_clock_and_end(self):
        records = ledger_fixture()
        records[834]["frame_tick"] = 0
        self.refusal("FRAME_INTERVAL", lambda: analyze(encoded(records)))
        records = ledger_fixture()
        records[0]["clock_hz"] = 50000000
        self.refusal("CAPTURE_HEADER", lambda: analyze(encoded(records)))
        self.refusal("CAPTURE_END", lambda: analyze(encoded(ledger_fixture()[:-1])))


@unittest.skipUnless(os.name == "nt", "Windows Job implementation")
class SupervisorTests(unittest.TestCase):
    def folder(self):
        DOCS.mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mkdtemp(prefix="SYNTHETIC_JOB_", dir=DOCS))

    def test_fake_python_normal_and_nonzero(self):
        for code in (0, 7):
            folder = self.folder()
            result = invoke([sys.executable, "-B", "-c", f"print('SYNTHETIC');raise SystemExit({code})"], folder, folder, "fake", time.monotonic() + 3, step_budget=2)
            write_new(folder / "RECEIPT.json", result)
            self.assertEqual(result["exit_code"], code)
            self.assertTrue(result["process_created"])
            self.assertFalse(result["timeout"])

    def test_fake_python_timeout_tree(self):
        folder = self.folder()
        child = "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);time.sleep(10)"
        result = invoke([sys.executable, "-B", "-c", child], folder, folder, "fake_tree", time.monotonic() + 2, step_budget=0.2)
        write_new(folder / "RECEIPT.json", result)
        self.assertTrue(result["timeout"])
        self.assertLess(result["elapsed_s"], 2)

    def test_fake_python_log_limit(self):
        folder = self.folder()
        code = "import sys,time;sys.stdout.write('a'*500000);sys.stdout.flush();time.sleep(5)"
        result = invoke([sys.executable, "-B", "-c", code], folder, folder, "fake_flood", time.monotonic() + 3, step_budget=2, log_limit=1024)
        write_new(folder / "RECEIPT.json", result)
        self.assertTrue(result["log_limit_exceeded"])
        self.assertLessEqual(result["stdout"]["bytes"] + result["stderr"]["bytes"], 1024)


if __name__ == "__main__":
    unittest.main(verbosity=2)
