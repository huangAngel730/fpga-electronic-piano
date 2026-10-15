"""Independent synthetic ACK/READ transaction contract tests."""
from __future__ import annotations

import copy
import json
import struct
import unittest

from session_audit import audit_transcript, unique
from session_fixtures import (
    RECORDS_A, RECORDS_B, attempt, begin, build_recovery, build_success,
    checksum, frame, response,
)


class SessionAuditTests(unittest.TestCase):
    def reject(self, doc):
        with self.assertRaises(ValueError):
            audit_transcript(doc)

    def test_success_independent_exact_report(self):
        report = audit_transcript(build_success())
        self.assertEqual(report["status"], "OFFLINE_SESSION_AUDIT_PASS")
        self.assertEqual(report["commits"], 1)
        self.assertEqual(report["final_unique_reads"], 2)
        self.assertEqual(report["final_score_id"], 101)
        self.assertFalse(report["hardware_pass_claim"])
        self.assertFalse(report["trace_authenticity_verified"])

    def test_ack_loss_cache_replay_abort_badcrc_recovery(self):
        report = audit_transcript(build_recovery())
        self.assertEqual(report["commits"], 2)
        self.assertEqual(report["retry_attempts"], 1)
        self.assertEqual(report["cached_ack_replays"], 1)
        self.assertEqual(report["aborts"], 2)
        self.assertEqual(report["nack_codes"], {"9": 1})
        self.assertEqual(report["final_score_id"], 202)
        self.assertEqual(report["final_unique_reads"], 2)

    def test_recorded_kind_is_not_authenticity_proof(self):
        doc = build_success()
        doc["evidence_kind"] = "recorded_frames"
        self.assertFalse(audit_transcript(doc)["trace_authenticity_verified"])

    def test_wrong_echo_identity(self):
        for field in ("command", "session", "seq", "offset"):
            doc = build_success()
            raw = bytes.fromhex(doc["attempts"][0]["response_hex"])
            _, cmd, session, seq, offset, _ = struct.unpack("<BBHHHH", raw[2:12])
            payload = raw[12:-2]
            if field == "command":
                payload = bytes([2]) + payload[1:]
            elif field == "session":
                session += 1
            elif field == "seq":
                seq += 1
            else:
                offset += 1
            doc["attempts"][0]["response_hex"] = frame(cmd, session, seq, offset, payload).hex()
            with self.subTest(field=field):
                self.reject(doc)

    def test_wrong_response_crc_version_and_ackcode(self):
        for kind in ("crc", "version", "ackcode"):
            doc = build_success()
            raw = bytes.fromhex(doc["attempts"][0]["response_hex"])
            if kind == "crc":
                raw = raw[:-1] + bytes([raw[-1] ^ 1])
            else:
                raw = frame(0x81 if kind == "ackcode" else 0x80,
                            1, 0, payload=raw[12:-2],
                            version=2 if kind == "version" else 1)
            doc["attempts"][0]["response_hex"] = raw.hex()
            self.reject(doc)

    def test_wrong_metadata_each_field(self):
        for position in range(2, 12):
            doc = build_success()
            raw = bytes.fromhex(doc["attempts"][0]["response_hex"])
            payload = bytearray(raw[12:-2])
            payload[position] ^= 1
            doc["attempts"][0]["response_hex"] = frame(0x80, 1, 0, payload=payload).hex()
            with self.subTest(position=position):
                self.reject(doc)

    def test_read_event_mismatch_with_valid_crc(self):
        doc = build_success()
        raw = bytes.fromhex(doc["attempts"][-1]["response_hex"])
        payload = bytearray(raw[12:-2])
        payload[-1] ^= 1
        doc["attempts"][-1]["response_hex"] = frame(0x80, 1, 1, 1, payload).hex()
        self.reject(doc)

    def test_missing_read_and_duplicates_cannot_fill_gap(self):
        for duplicate in (False, True):
            doc = build_success()
            doc["attempts"].pop()
            if duplicate:
                doc["attempts"].append(copy.deepcopy(doc["attempts"][-1]))
            self.reject(doc)

    def test_redundant_read_different_seq_legal_but_unique_count_unchanged(self):
        doc = build_success()
        req = frame(6, 1, 87, 0)
        doc["attempts"].append(attempt(req, response(
            req, bank=(101, RECORDS_A), received=16, event=RECORDS_A[:8])))
        report = audit_transcript(doc)
        self.assertEqual(report["final_unique_reads"], 2)
        self.assertEqual(report["redundant_reads"], 1)

    def test_each_generation_must_be_read_before_next_commit(self):
        doc = build_recovery()
        # Remove all first-bank READs, including those observed during staging.
        doc["attempts"] = [a for a in doc["attempts"]
                           if not (bytes.fromhex(a["request_hex"])[3] == 6
                                   and bytes.fromhex(a["request_hex"])[4] < 4)]
        self.reject(doc)

    def test_timeout_tail_and_early_timeout(self):
        doc = build_success()
        req = frame(5, 1, 55)
        doc["attempts"].append(attempt(req, None, 500000))
        self.reject(doc)
        doc["attempts"][-1]["elapsed_us"] = 499999
        self.reject(doc)
        doc["attempts"][-1]["elapsed_us"] = 500001
        self.reject(doc)

    def test_two_retries_permitted_three_retries_rejected(self):
        for count in (2, 3):
            doc = build_success()
            first = doc["attempts"][0]
            missing = {**first, "response_hex": None, "elapsed_us": 500000}
            doc["attempts"][0:0] = [copy.deepcopy(missing) for _ in range(count)]
            if count == 2:
                self.assertEqual(audit_transcript(doc)["retry_attempts"], 2)
            else:
                self.reject(doc)

    def test_retry_must_preserve_request_bytes(self):
        doc = build_success()
        first = doc["attempts"][0]
        doc["attempts"].insert(0, {**first, "response_hex": None, "elapsed_us": 500000})
        doc["attempts"][1]["request_hex"] = begin(101, RECORDS_A, 2).hex()
        self.reject(doc)

    def test_response_deadline_total_budget_and_typed_times(self):
        for elapsed in (-1, True, 500001, 30000001):
            doc = build_success()
            doc["attempts"][0]["elapsed_us"] = elapsed
            self.reject(doc)
        doc = build_success()
        doc["total_timeout_us"] = 500000
        for a in doc["attempts"]:
            a["elapsed_us"] = 100000
        self.reject(doc)

    def test_invalid_transcript_schema_expected_scores_and_hex(self):
        changes = [("schema", True), ("schema", 2), ("initial_committed", {}),
                   ("evidence_kind", "hardware_pass"), ("attempts", []),
                   ("expected_scores", []), ("max_retries", 3),
                   ("ack_timeout_us", 0), ("ack_timeout_us", 500001)]
        for key, value in changes:
            doc = build_success()
            doc[key] = value
            self.reject(doc)
        doc = build_success()
        doc["expected_scores"].append(copy.deepcopy(doc["expected_scores"][0]))
        self.reject(doc)
        for text in ("zz", "f", "A5", "a5 " , "00" * 143):
            doc = build_success()
            doc["attempts"][0]["request_hex"] = text
            self.reject(doc)

    def test_extra_missing_and_duplicate_json_fields(self):
        doc = build_success()
        doc["extra"] = 1
        self.reject(doc)
        doc = build_success()
        del doc["attempts"][0]["elapsed_us"]
        self.reject(doc)
        with self.assertRaises(ValueError):
            json.loads('{"schema":1,"schema":1}', object_pairs_hook=unique)

    def test_expected_content_and_unpublished_targets(self):
        doc = build_success()
        doc["expected_scores"][0]["records_hex"] = RECORDS_B.hex()
        self.reject(doc)
        doc = build_success()
        doc["expected_scores"].append({"score_id": 202, "records_hex": RECORDS_B.hex()})
        self.reject(doc)

    def test_open_staging_session_rejected_even_after_full_read(self):
        doc = build_success()
        req = begin(202, RECORDS_B, 2)
        doc["attempts"].append(attempt(req, response(req, bank=(101, RECORDS_A), active=True)))
        self.reject(doc)

    def test_bad_record_nack10_preserves_old_bank_and_abort_recovers(self):
        doc = build_success()
        old = (101, RECORDS_A)
        bad = bytearray(RECORDS_B)
        bad[4] = 2
        # Both record legality and whole CRC are wrong: frozen VERIFY_USE
        # rejects the record first, before checking the final score CRC.
        req = begin(202, bad, 2, checksum(bad) ^ 1)
        doc["attempts"].append(attempt(req, response(req, bank=old, active=True)))
        req = frame(2, 2, 1, payload=bad)
        doc["attempts"].append(attempt(req, response(req, bank=old, active=True, received=16)))
        req = frame(3, 2, 2)
        doc["attempts"].append(attempt(req, response(req, error=10, bank=old, received=16)))
        req = frame(4, 2, 17)
        doc["attempts"].append(attempt(req, response(req, bank=old)))
        self.assertEqual(audit_transcript(doc)["nack_codes"], {"10": 1})

    def test_early_commit_nack8_keeps_active_then_abort(self):
        doc = build_success()
        old = (101, RECORDS_A)
        req = begin(202, RECORDS_B, 2)
        doc["attempts"].append(attempt(req, response(req, bank=old, active=True)))
        req = frame(3, 2, 1)
        doc["attempts"].append(attempt(req, response(req, error=8, bank=old, active=True)))
        req = frame(4, 2, 99)
        doc["attempts"].append(attempt(req, response(req, bank=old)))
        self.assertEqual(audit_transcript(doc)["nack_codes"], {"8": 1})

    def test_command_nack_priorities_preserve_stage_and_old_bank(self):
        doc = build_success()
        old = (101, RECORDS_A)
        inactive_cases = [
            (frame(99, 1, 1), 3),
            (frame(5, 1, 1, payload=b"x"), 4),
            (frame(6, 1, 1, 2), 13),
            (frame(5, 1, 2, version=2), 2),
        ]
        damaged = bytearray(frame(5, 1, 3))
        damaged[-1] ^= 1
        inactive_cases.append((bytes(damaged), 1))
        for req, error in inactive_cases:
            doc["attempts"].append(attempt(req, response(
                req, error=error, bank=old, received=16)))
        req = begin(202, RECORDS_B, 2)
        doc["attempts"].append(attempt(req, response(req, bank=old, active=True)))
        active_cases = [
            (frame(2, 3, 1, payload=RECORDS_B), 5),
            (frame(2, 2, 2, payload=RECORDS_B), 6),
            (frame(2, 2, 1, 1, RECORDS_B), 7),
            (frame(2, 2, 1), 4),
            (frame(3, 2, 1, payload=b"x"), 4),
            (frame(3, 3, 1), 5),
            (frame(3, 2, 2), 6),
            (frame(3, 2, 1), 8),
        ]
        for req, error in active_cases:
            doc["attempts"].append(attempt(req, response(
                req, error=error, bank=old, active=True)))
        req = frame(4, 0, 0)
        doc["attempts"].append(attempt(req, response(req, bank=old)))
        report = audit_transcript(doc)
        self.assertEqual(report["commits"], 1)
        self.assertEqual(report["nacks"], 13)
        self.assertEqual(report["nack_codes"]["8"], 1)

    def test_cached_ack_must_be_byteidentical(self):
        doc = build_recovery()
        replay = doc["attempts"][5]
        raw = bytes.fromhex(replay["response_hex"])
        payload = bytearray(raw[12:-2])
        payload[2] ^= 1
        replay["response_hex"] = frame(0x80, 1, 3, payload=payload).hex()
        self.reject(doc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
