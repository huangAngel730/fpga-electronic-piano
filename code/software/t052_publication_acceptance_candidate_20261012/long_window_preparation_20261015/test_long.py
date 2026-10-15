"""Independent handwritten prefix fixture and explicit failure expectations."""
import io
import json
import unittest

from check_capture import Incomplete, check_streams, equal, read_json
from plan import COUNT, RESETS, VERSION, Calendar, controls, pack, unpack

# Handwritten directly from M1's prefix table, not Calendar.step output.
PUBLISH = {7: (1, 1, 0xFFFFFFFE), 11: (1, 2, 0xFFFFFFFF),
           15: (1, 3, 0), 24: (1, 4, 0), 49: (1, 10, 5),
           53: (1, 11, 6), 57: (1, 12, 7), 61: (1, 13, 8),
           135: (2, 1, 0xA5A5A5A5)}
ACCEPT = {4: (1, 1, 0xFFFFFFFE), 8: (1, 2, 0xFFFFFFFF),
          12: (1, 3, 0), 16: (1, 4, 0), 25: (1, 5, 0),
          27: (1, 6, 1), 30: (1, 7, 2), 34: (1, 8, 3),
          42: (1, 9, 4), 46: (1, 10, 5), 50: (1, 11, 6),
          54: (1, 12, 7), 58: (1, 13, 8), 124: (1, 14, 0xA5A5A5A5),
          132: (2, 1, 0xA5A5A5A5)}
CANCEL = {26: ((1, 5, 0), "cancel"), 29: ((1, 6, 1), "frame"),
          33: ((1, 7, 2), "cancel"), 41: ((1, 8, 3), "frame"),
          43: ((1, 9, 4), "frame+cancel"),
          128: ((1, 14, 0xA5A5A5A5), "reset")}


def fixture():
    rows, events = [], []
    held_id = 0
    for cycle in range(256):
        busy = any(start < cycle <= end for start, end in (
            (4, 7), (8, 11), (12, 15), (16, 24), (25, 26), (27, 29),
            (30, 33), (34, 41), (42, 43), (46, 49), (50, 53),
            (54, 57), (58, 61), (124, 127), (132, 135)))
        valid = cycle in {7, 11, 15, 33, 49, 53, 57, 61, 127, 135} or (
            19 <= cycle <= 24 or 37 <= cycle <= 41)
        # Public ID is installed when valid first appears, retained after consume.
        if cycle in {7, 11, 15, 19, 33, 37, 49, 53, 57, 61, 127, 135}:
            preceding = max(c for c in ACCEPT if c < cycle)
            held_id = ACCEPT[preceding][2]
        if cycle in {0, 27, 30, 34, 42, 44, 45, 46, 128}:
            held_id = 0
        value = (((cycle << 64 | (10 + 20 * cycle)) << 170 | pack(controls(cycle))) << 34
                 | int(not busy) << 33 | int(valid) << 32 | held_id)
        rows.append(f"{value:075x}\n")
        if cycle in ACCEPT:
            events.append(dict(event="ACCEPT", cycle=cycle,
                               time_ns=10+20*cycle, key=list(ACCEPT[cycle])))
        if cycle in PUBLISH:
            events.append(dict(event="PUBLISH", cycle=cycle,
                               time_ns=10+20*cycle, key=list(PUBLISH[cycle])))
        if cycle in CANCEL:
            key, why = CANCEL[cycle]
            events.append(dict(event="CANCEL", cycle=cycle,
                               time_ns=20*cycle if why == "reset" else 10+20*cycle,
                               key=list(key), reason=why))
    rows.append("END 256\n")
    events.append(dict(type="END", rows=256, accepted=15, published=9,
                       cancelled=6, open=0))
    resets = [dict(time_ns=t, cycle=c, rst_n=r) for t, c, r in RESETS]
    return rows, events, resets


def check(rows, events, resets):
    return check_streams(io.StringIO("".join(rows)),
                         io.StringIO("".join(json.dumps(e)+"\n" for e in events)),
                         io.StringIO("".join(json.dumps(e)+"\n" for e in resets)), 256)


class LongTests(unittest.TestCase):
    def test_handwritten_prefix(self):
        result = check(*fixture())
        self.assertEqual((result["accepted"], result["published"],
                          result["cancelled"], result["open"]), (15, 9, 6, 0))
        self.assertFalse(result["PCM_math_verified"])

    def test_missing_edge(self):
        rows, ev, rst = fixture()
        del rows[4]
        with self.assertRaisesRegex(ValueError, "INPUT_CYCLE_OR_TIME_MISMATCH:4"):
            check(rows, ev, rst)

    def test_ready_silent_loss(self):
        rows, ev, rst = fixture()
        # DUT ready falsely low: cannot redefine the accepted set to get a pass.
        rows[4] = f"{int(rows[4], 16) ^ (1 << 33):075x}\n"
        with self.assertRaisesRegex(ValueError, "READY_VALID_ID_MISMATCH:4"):
            check(rows, ev, rst)

    def test_publish_on_cancel(self):
        rows, ev, rst = fixture()
        index = next(i for i, e in enumerate(ev) if e.get("cycle") == 33)
        ev[index] = dict(event="PUBLISH", cycle=33, time_ns=670, key=[1, 7, 2])
        with self.assertRaisesRegex(ValueError, "TRANSACTION_EVENT_MISMATCH:33"):
            check(rows, ev, rst)

    def test_wrong_serial_repeated_id(self):
        rows, ev, rst = fixture()
        next(e for e in ev if e.get("cycle") == 24)["key"][1] = 3
        with self.assertRaisesRegex(ValueError, "TRANSACTION_EVENT_MISMATCH:24"):
            check(rows, ev, rst)

    def test_false_counts(self):
        rows, ev, rst = fixture()
        ev[-1]["published"] = 9.0
        with self.assertRaisesRegex(ValueError, "EVENT_END_MISMATCH"):
            check(rows, ev, rst)

    def test_missing_end(self):
        rows, ev, rst = fixture()
        with self.assertRaisesRegex(Incomplete, "OBS_END"):
            check(rows[:-1], ev, rst)

    def test_async_reset_missing(self):
        rows, ev, rst = fixture()
        with self.assertRaisesRegex(Incomplete, "RESET_TRAJECTORY"):
            check(rows, ev, rst[:2])

    def test_post_nba_one_edge_early(self):
        rows, ev, rst = fixture()
        rows[6] = f"{int(rows[6], 16) | (1 << 32):075x}\n"
        with self.assertRaisesRegex(ValueError, "READY_VALID_ID_MISMATCH:6"):
            check(rows, ev, rst)

    def test_extra_after_end(self):
        rows, ev, rst = fixture()
        rows.append(rows[0])
        with self.assertRaisesRegex(ValueError, "OBS_AFTER_END"):
            check(rows, ev, rst)

    def test_wrong_reset_epoch(self):
        rows, ev, rst = fixture()
        next(e for e in ev if e.get("cycle") == 132)["key"][0] = 1
        with self.assertRaisesRegex(ValueError, "TRANSACTION_EVENT_MISMATCH:132"):
            check(rows, ev, rst)

    def test_json_strict_types(self):
        self.assertFalse(equal(True, 1))
        self.assertFalse(equal(3.0, 3))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            read_json('{"a":1,"a":2}')

    def test_actual_time_mismatch(self):
        rows, ev, rst = fixture()
        rows[100] = f"{int(rows[100], 16) ^ (1 << 204):075x}\n"
        with self.assertRaisesRegex(ValueError, "INPUT_CYCLE_OR_TIME_MISMATCH:100"):
            check(rows, ev, rst)

    def test_wrong_async_time(self):
        rows, ev, rst = fixture()
        rst[2]["time_ns"] += 10
        with self.assertRaisesRegex(ValueError, "RESET_TRAJECTORY_MISMATCH"):
            check(rows, ev, rst)

    def test_crlf_and_extra_reset(self):
        rows, ev, rst = fixture()
        self.assertEqual(check([r.replace("\n", "\r\n") for r in rows], ev, rst)["accepted"], 15)
        rst.append(dict(time_ns=3000, cycle=150, rst_n=0))
        with self.assertRaisesRegex(ValueError, "RESET_TRAJECTORY_MISMATCH"):
            check(rows, ev, rst)

    def test_plan_boundaries(self):
        for j, mask in ((0, 1), (1023, 1), (1024, 2), (2048, 4),
                        (3072, 8), (4095, 8), (4096, 15), (8191, 15)):
            f = 256+1042*j
            self.assertEqual(controls(f)["mask"], mask)
            self.assertEqual(controls(f)["frame"], 1)
            self.assertEqual(controls(f+1)["req"], 1)
            self.assertEqual(controls(f+1)["ready"], int(j % 64 != 0))
        self.assertEqual(controls(256+1042*32)["id"], 0)
        self.assertEqual(controls(COUNT-1)["id"], 0xFEF)
        self.assertEqual(COUNT, 8536336)

    def test_pack_roundtrip(self):
        for cycle in (0, 4, 16, 26, 43, 46, 128, 132, 256, COUNT-1):
            row = controls(cycle)
            self.assertEqual(unpack(pack(row)), row)
        with self.assertRaisesRegex(ValueError, "CONTROL_TYPE"):
            pack(dict(controls(4), req=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
