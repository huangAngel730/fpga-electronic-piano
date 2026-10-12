"""Focused tests for real-pin readiness and playback-time projection."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from projection_check import ProjectionError, check
from vectors import complete_trace, reset_trace, write_trace


class ProjectionTests(unittest.TestCase):
    @staticmethod
    def find(records, predicate):
        return next(item for item in records if predicate(item))

    def check_records(self, records):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.jsonl"
            write_trace(path, records)
            return check(path)

    def rejects(self, records, diagnostic):
        with self.assertRaisesRegex(ProjectionError, diagnostic):
            self.check_records(records)

    def test_directed_trace_has_explicit_ready_layers(self):
        records = complete_trace()
        result = self.check_records(records)
        wrong_id = self.find(records, lambda item: item.get("result_id") == 99)
        self.assertEqual((wrong_id["raw_result_credit"],
                          wrong_id["qualified_result_ready"],
                          wrong_id["true_result_handshake"]), (1, 0, 0))
        self.assertEqual(result["result_handshakes"], 3)
        self.assertEqual(result["commits"], 3)

    def test_pending_is_visible_after_commit_before_frame(self):
        records = complete_trace()
        commit_b = self.find(records, lambda item: item.get("commit_pulse") == 1
                             and item.get("committed_left") == 333)
        self.assertEqual((commit_b["pre_play_left"], commit_b["pre_play_right"]),
                         (111, -222))
        self.assertEqual((commit_b["post_play_left"], commit_b["post_play_right"]),
                         (333, -444))
        self.assertEqual(commit_b["post_pending_valid"], 1)
        self.check_records(records)

    def test_frame_samples_pre_nba_play_and_transfers_pending(self):
        records = complete_trace()
        frame = self.find(records, lambda item: item.get("frame_tick") == 1
                          and item.get("pre_play_left") == 333)
        self.assertEqual((frame["frame_tx_left"], frame["frame_tx_right"]),
                         (333, -444))
        self.assertEqual(frame["post_pending_valid"], 0)
        self.assertEqual((frame["post_play_left"], frame["post_play_right"]),
                         (333, -444))
        self.check_records(records)

    def test_frame_rejects_old_result_even_if_dispatched(self):
        records = complete_trace()
        frame = self.find(records, lambda item: item.get("frame_tick") == 1
                          and item.get("result_valid") == 1)
        self.assertEqual(frame["result_valid"], 1)
        self.assertEqual(frame["qualified_result_ready"], 0)
        self.assertEqual(frame["true_result_handshake"], 0)
        self.check_records(records)

    def test_reset_clears_transport_state(self):
        result = self.check_records(reset_trace())
        self.assertEqual(result, {"tag": "END", "cycles": 7,
                                  "result_handshakes": 0, "commits": 0,
                                  "frames": 0})

    def test_wrong_id_ready_is_rejected(self):
        records = complete_trace()
        edge = self.find(records, lambda item: item.get("result_id") == 99)
        edge["qualified_result_ready"] = 1
        edge["true_result_handshake"] = 1
        self.rejects(records, "QUALIFIED_READY_ID")

    def test_early_pending_play_is_rejected(self):
        records = complete_trace()
        edge = self.find(records, lambda item: item.get("commit_pulse") == 1
                         and item.get("committed_left") == 333)
        edge["pre_play_left"] = 333
        edge["pre_play_right"] = -444
        self.rejects(records, "PLAY_PRE_EDGE")

    def test_late_pending_play_is_rejected(self):
        records = complete_trace()
        edge = self.find(records, lambda item: item.get("commit_pulse") == 1
                         and item.get("committed_left") == 333)
        edge["post_play_left"] = 111
        edge["post_play_right"] = -222
        self.rejects(records, "PLAY_POST_EDGE")

    def test_frame_old_held_projection_is_rejected(self):
        records = complete_trace()
        edge = self.find(records, lambda item: item.get("frame_tick") == 1
                         and item.get("pre_play_left") == 333)
        edge["frame_tx_left"] = 111
        edge["frame_tx_right"] = -222
        self.rejects(records, "FRAME_TX_PRE_PLAY")

    def test_software_only_field_is_rejected(self):
        records = complete_trace()
        self.find(records, lambda item: item.get("result_id") == 99)["result_epoch"] = 0
        self.rejects(records, "EDGE_FIELDS_EXACT")

    def test_duplicate_json_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.jsonl"
            records = complete_trace()
            raw = [json.dumps(records[0]),
                   '{"tag":"EDGE","tag":"EDGE"}',
                   json.dumps(records[-1])]
            path.write_text("\n".join(raw) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ProjectionError, "JSON_DUPLICATE_KEY"):
                check(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
