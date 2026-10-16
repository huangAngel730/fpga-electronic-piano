"""Focused software tests for the chat8 provenance verifier helpers."""

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from provenance_audit import AuditError, scan_jsonl, strict_json, verify_archive


WRITE_SET_ROOT = Path(__file__).resolve().parent


def require_test_path_in_write_set(path):
    """Resolve a test path and reject writes outside this task's software directory."""
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(WRITE_SET_ROOT)
    except ValueError as exc:
        raise AuditError(f"TEST_PATH_OUTSIDE_WRITE_SET:{resolved}") from exc
    return resolved


TEST_PARENT = require_test_path_in_write_set(WRITE_SET_ROOT / "_test_tmp")
TEST_PARENT.mkdir(parents=True, exist_ok=True)


class ProvenanceHelperTests(unittest.TestCase):
    def test_strict_json_rejects_duplicate_key(self):
        with tempfile.TemporaryDirectory(dir=TEST_PARENT) as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"ok": true, "ok": false}\n', encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "DUPLICATE_JSON_KEY"):
                strict_json(path)

    def test_strict_json_rejects_nonfinite_number(self):
        with tempfile.TemporaryDirectory(dir=TEST_PARENT) as directory:
            path = Path(directory) / "nonfinite.json"
            path.write_text('{"value": NaN}\n', encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "NONFINITE_JSON"):
                strict_json(path)

    def test_jsonl_counts_consecutive_ticks(self):
        with tempfile.TemporaryDirectory(dir=TEST_PARENT) as directory:
            path = Path(directory) / "capture.jsonl"
            rows = [
                {"kind": "HEADER", "schema": "TEST"},
                {"kind": "TICK", "cycle": 1},
                {"kind": "TICK", "cycle": 2},
                {"kind": "END", "cycle": 2},
            ]
            path.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
            result = scan_jsonl(path, "TEST")
            self.assertEqual(result["ticks"], 2)
            self.assertEqual(result["last_cycle"], 2)

    def test_jsonl_rejects_missing_tick(self):
        with tempfile.TemporaryDirectory(dir=TEST_PARENT) as directory:
            path = Path(directory) / "capture.jsonl"
            rows = [
                {"kind": "HEADER", "schema": "TEST"},
                {"kind": "TICK", "cycle": 1},
                {"kind": "TICK", "cycle": 3},
                {"kind": "END", "cycle": 3},
            ]
            path.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
            with self.assertRaisesRegex(AuditError, "JSONL_TICK_ORDER"):
                scan_jsonl(path, "TEST")

    def test_archive_verifies_member_hashes(self):
        with tempfile.TemporaryDirectory(dir=TEST_PARENT) as directory:
            root = Path(directory)
            archive = root / "evidence.zip"
            payload = b"evidence\n"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("payload.txt", payload)
            import hashlib

            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "payload.txt": {
                            "bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest(),
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            result = verify_archive(archive, manifest)
            self.assertEqual(result, {"manifest_members": 1, "zip_members": 1})

    def test_archive_rejects_wrong_member_hash(self):
        with tempfile.TemporaryDirectory(dir=TEST_PARENT) as directory:
            root = Path(directory)
            archive = root / "evidence.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("payload.txt", b"evidence\n")
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({"payload.txt": {"bytes": 9, "sha256": "0" * 64}}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(AuditError, "ARCHIVE_SHA"):
                verify_archive(archive, manifest)


if __name__ == "__main__":
    unittest.main()
