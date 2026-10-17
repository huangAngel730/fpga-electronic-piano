"""Independent fixture plan/ledger and pin decoder; never signs Pro DUT."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


FIELDS = set("kind cycle epoch rst_n clock_stable pa_en frame_tick request request_id commit pcm_epoch pcm_id "
             "left right pending play_epoch play_id play_left play_right bclk ws din".split())
BITS = "rst_n clock_stable pa_en frame_tick request commit pending bclk ws din".split()


class Refusal(ValueError):
    def __init__(self, code, cycle=0, expected=None, actual=None):
        self.detail = {"code": code, "cycle": cycle, "expected": expected, "actual": actual}
        super().__init__(json.dumps(self.detail))


def need(condition, code, cycle=0, expected=None, actual=None):
    if not condition:
        raise Refusal(code, cycle, expected, actual)


def load_json(raw):
    def unique(pairs):
        result = {}
        for k, v in pairs:
            need(k not in result, "DUPLICATE_JSON_KEY")
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=unique)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Decoder:
    def __init__(self):
        self.halves = []; self.stereo = []; self.reset()

    def reset(self):
        self.prev = None; self.toggle = None; self.rise = None
        self.start = None; self.last_fall_frame = False
        self.sync = False; self.ws = 0; self.bits = []; self.right = None
        self.sample = {"epoch": 0, "frame": 0, "id": 0, "dac_left": 0, "dac_right": 0}
        self.word_sample = None

    def observe(self, r):
        c = r["cycle"]
        if not r["rst_n"]:
            self.reset(); self.sample["epoch"] = r["epoch"]; return
        if self.start is None:
            self.start = c
        p = self.prev
        if p is not None:
            changed = p["bclk"] != r["bclk"]
            fall = changed and not r["bclk"]
            rise = changed and r["bclk"]
            need(not p["frame_tick"] or fall, "FRAME_BCLK_PHASE", c)
            if changed:
                if self.toggle is not None:
                    need(c - self.toggle in (6, 7), "BCLK_HALF_PERIOD", c)
                self.toggle = c
            need(c - (self.toggle if self.toggle is not None else self.start) <= 7, "BCLK_STALLED", c)
            need((p["ws"] == r["ws"] and p["din"] == r["din"]) or fall, "PIN_CHANGE_NOT_FALLING", c)
            if fall:
                boundary = p["ws"] == 1 and r["ws"] == 0
                need(boundary == self.last_fall_frame, "WS_FRAME_BOUNDARY", c)
                self.last_fall_frame = bool(p["frame_tick"])
            if rise:
                if self.rise is not None:
                    need(c - self.rise in (13, 14), "BCLK_FULL_PERIOD", c)
                self.rise = c
                if r["ws"] != self.ws:
                    if self.sync:
                        need(len(self.bits) == 32, "WS_SLOT_COUNT", c, 32, len(self.bits))
                        need(not any(bit for _, bit in self.bits[:16]), "LSBJ_PADDING_NONZERO", c)
                        word = 0
                        for _, bit in self.bits[16:]:
                            word = (word << 1) | bit
                        value = word - 65536 if word & 32768 else word
                        ch = "left" if self.ws else "right"
                        expected = self.word_sample["dac_" + ch]
                        need(value == expected, "SERIAL_SAMPLE", c,
                             {"channel": ch, "pcm16": expected}, {"channel": ch, "pcm16": value})
                        half = {**self.word_sample, "channel": ch, "value": value,
                                "first_rise": self.bits[0][0], "last_rise": self.bits[-1][0], "boundary": c}
                        self.halves.append(half)
                        if ch == "right":
                            self.right = half
                        elif self.right:
                            need((self.right["epoch"], self.right["frame"], self.right["id"]) ==
                                 (half["epoch"], half["frame"], half["id"]), "STEREO_ID_MIX", c)
                            self.stereo.append({"epoch": half["epoch"], "frame": half["frame"], "id": half["id"],
                                                "left": value, "right": self.right["value"], "last_rise": half["last_rise"]})
                            self.right = None
                    self.sync = True; self.bits = []; self.ws = r["ws"]
                    self.word_sample = dict(self.sample)
                if self.sync:
                    self.bits.append((c, r["din"]))
                    need(len(self.bits) <= 32, "WS_SLOT_COUNT", c, 32, len(self.bits))
        self.prev = r


def check(capture, plan_path):
    plan = load_json(Path(plan_path).read_text(encoding="utf-8"))
    need(plan["origin"] == "ISOLATED_PYTHON_FIXTURE_NOT_PRO_DUT" and plan["board_release_allowed"] is False,
         "PLAN_SCOPE")
    for v in plan["vectors"]:
        for ch in ("left", "right"):
            value = v[ch]
            need(type(value) is int and -(1 << 23) <= value < (1 << 23), "VECTOR_PCM24_RANGE")
            # Independently check explicit hand table using integer division.
            expected = min(32767, max(-32768, (value + 128) // 256))
            need(v["dac_" + ch] == expected, "HAND_BOUNDARY_VECTOR", expected=expected, actual=v["dac_" + ch])
    frames = {x["cycle"]: x for x in plan["frames"]}
    requests = {x["request_cycle"]: x for x in plan["frames"] if x["request_cycle"] <= plan["epochs"][x["epoch"]]["end"]}
    d = Decoder(); outstanding = None; pending = None; held = (0, 0, 0, 0)
    stable_count = 0; epoch_index = 0; last_epoch = 0; cycle = 0; end = False
    ledger = {}; frame_cycles = {}; pa_open_cycles = {}; seen_vectors = set()
    raw_sha = sha(capture)
    with Path(capture).open(encoding="utf-8") as stream:
        need(load_json(stream.readline()) == {"kind": "HEADER", "schema": "D_PT8211_FIXTURE_V1",
             "origin": plan["origin"], "clock_hz": 40000000}, "HEADER_SCOPE")
        for line in stream:
            need(not end, "AFTER_END")
            r = load_json(line)
            if r.get("kind") == "END":
                need(r == {"kind": "END", "cycle": plan["cycles"], "epoch": plan["epochs"][-1]["epoch"]}
                     and cycle == plan["cycles"], "END_COUNT")
                end = True; continue
            need(set(r) == FIELDS and r["kind"] == "TICK", "TICK_FIELDS")
            need(all(type(r[k]) is int for k in FIELDS - {"kind"}), "UNKNOWN_OR_NONINTEGER", cycle + 1)
            need(r["cycle"] == cycle + 1, "TICK_ORDER", cycle + 1)
            cycle += 1
            need(all(r[k] in (0, 1) for k in BITS), "BIT_RANGE", cycle)
            need(all(-(1 << 23) <= r[k] < (1 << 23) for k in ("left", "right", "play_left", "play_right")), "PCM24_RANGE", cycle)
            if cycle > plan["epochs"][epoch_index]["end"]:
                epoch_index += 1
            e = plan["epochs"][epoch_index]
            reset = cycle < e["active_start"]
            stable = cycle >= e["stable_start"]
            need(r["epoch"] == e["epoch"] and r["rst_n"] == int(not reset)
                 and r["clock_stable"] == int(stable), "RESET_EPOCH_STIMULUS", cycle)
            stable_count = stable_count + 1 if not reset and stable else 0
            if reset:
                need(r["pa_en"] == 0, "PA_EN_DURING_RESET", cycle, 0, r["pa_en"])
            elif stable_count < plan["fixture_stable_wait_cycles"]:
                need(r["pa_en"] == 0, "PA_EN_BEFORE_STABLE", cycle, 0, r["pa_en"])
            else:
                need(r["pa_en"] == 1, "PA_EN_ACTIVE_HIGH", cycle, 1, r["pa_en"])
                pa_open_cycles.setdefault(str(e["epoch"]), cycle)
            if reset:
                if outstanding:
                    ledger[outstanding].update(status="CANCELLED_RESET", cancel_cycle=cycle)
                outstanding = None; pending = None; held = (0, 0, e["epoch"], 0)
                need(not any(r[k] for k in ("frame_tick", "request", "commit", "pending", "play_id", "play_left", "play_right", "bclk", "ws", "din")),
                     "RESET_NOT_SILENT", cycle)
                d.observe(r); last_epoch = e["epoch"]; continue
            need(r["pending"] == int(pending is not None), "PENDING_IDENTITY", cycle)
            play = pending if pending else held
            need((r["play_left"], r["play_right"], r["play_epoch"], r["play_id"]) == play, "PLAY_IDENTITY", cycle)
            f = frames.get(cycle)
            need(r["frame_tick"] == int(f is not None), "FRAME_CALENDAR", cycle, int(f is not None), r["frame_tick"])
            expected_request = requests.get(cycle)
            need(r["request"] == int(expected_request is not None), "REQUEST_CALENDAR", cycle)
            d.observe(r)
            if f:
                need(outstanding is None, "REQUEST_DEADLINE_MISSED", cycle, "COMMIT_BEFORE_FRAME", outstanding)
                need(not r["commit"] and not r["request"], "FRAME_FENCE_TRANSACTION", cycle)
                frame_cycles.setdefault(str(e["epoch"]), []).append(cycle)
                sample = {"epoch": e["epoch"], "frame": f["frame"], "id": play[3], "dac_left": 0, "dac_right": 0}
                if play[3]:
                    vector = plan["vectors"][(play[3] - 1) % len(plan["vectors"])]
                    sample.update(dac_left=vector["dac_left"], dac_right=vector["dac_right"])
                    ledger[(e["epoch"], play[3])].update(sample_cycle=cycle, next_frame_deadline="PROVEN")
                d.sample = sample
                if pending:
                    held = pending; pending = None
            if expected_request:
                key = (e["epoch"], expected_request["request_id"])
                need(r["request_id"] == key[1] and outstanding is None and key not in ledger, "REQUEST_IDENTITY", cycle)
                outstanding = key
                ledger[key] = {"epoch": key[0], "id": key[1], "request_cycle": cycle, "status": "IN_FLIGHT", "next_frame_deadline": "UNKNOWN_TAIL"}
            if r["commit"]:
                need(r["pcm_epoch"] == e["epoch"], "OLD_EPOCH_PCM", cycle, e["epoch"], r["pcm_epoch"])
                key = (r["pcm_epoch"], r["pcm_id"])
                need(outstanding == key and pending is None, "STALE_OR_DUPLICATE_COMMIT", cycle)
                vector_index = (key[1] - 1) % len(plan["vectors"])
                vector = plan["vectors"][vector_index]
                need((r["left"], r["right"]) == (vector["left"], vector["right"]), "PCM_INPUT_VECTOR", cycle)
                need(cycle > ledger[key]["request_cycle"], "COMMIT_NOT_AFTER_REQUEST", cycle)
                pending = (r["left"], r["right"], key[0], key[1]); outstanding = None
                ledger[key].update(status="COMMITTED", commit_cycle=cycle)
                seen_vectors.add(vector_index)
            last_epoch = e["epoch"]
    need(end, "END_MISSING")
    gaps = {}
    for epoch, times in frame_cycles.items():
        intervals = [b - a for a, b in zip(times, times[1:])]
        need(set(intervals) == {833, 834}, "FRAME_833_834", expected=[833, 834], actual=sorted(set(intervals)))
        need(all(sum(intervals[i:i + 3]) == 2500 for i in range(len(intervals) - 2)), "FRAME_48K_MEAN")
        gaps[epoch] = dict(Counter(intervals))
    need(set(gaps) == {"0", "1"} and len(seen_vectors) == len(plan["vectors"]), "RESET_AND_VECTOR_COVERAGE")
    for frame in d.stereo:
        key = (frame["epoch"], frame["id"])
        if frame["id"]:
            entry = ledger[key]
            entry["serial_last_rise"] = frame["last_rise"]
            entry["request_to_serial_cycles"] = frame["last_rise"] - entry["request_cycle"]
            need(entry["request_to_serial_cycles"] <= 400000, "DIGITAL_OVER_10MS", frame["last_rise"])
    need(any(r["left"] != r["right"] for r in d.stereo) and any(r["left"] < 0 or r["right"] < 0 for r in d.stereo), "SIGNED_UNEQUAL_STEREO_COVERAGE")
    need(sha(capture) == raw_sha, "CAPTURE_CHANGED")
    return {"passed": True, "scope": plan["origin"], "level": "L1_SOFTWARE_FIXTURE_ONLY",
            "cycles": cycle, "request_ledger": list(ledger.values()), "serial_frames": d.stereo,
            "serial_half_frames": d.halves, "frame_intervals": gaps, "pa_first_open_cycles": pa_open_cycles,
            "hand_vectors_covered": len(seen_vectors), "capture_sha256": raw_sha, "plan_sha256": sha(plan_path),
            "Pro_DUT_actual_deadline_sampling_PA": "UNKNOWN", "analog_10ms": "UNKNOWN_NOT_MEASURED", "board_release_allowed": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", required=True, type=Path)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    try:
        result = check(args.capture, args.plan); code = 0
    except (Refusal, ValueError, KeyError, TypeError, OSError) as exc:
        result = {"passed": False, "first_difference": exc.detail if isinstance(exc, Refusal) else {"code": str(exc)},
                  "board_release_allowed": False}; code = 1
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2); stream.write("\n")
    print(json.dumps({"passed": result["passed"], "first_difference": result.get("first_difference")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
