"""N32-C v4 inputs and independent frame-level numerical ledger.

The old v3 assets remain unchanged. Expected audio is derived from input
events plus frozen Router/Envelope/DDS/ROM; no observed value is consulted.
The clocked checker independently validates exact transient/calendar behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_plan import build_operations
from n32c_common import CONTROL_EVENT_SPECS, pack_event, records_sha256, write_jsonl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "code/software/polyphony_scaling_candidate"))
sys.path.insert(0, str(ROOT / "code/software/audio_math_acceptance_candidate"))
from inventory import FROZEN  # noqa: E402
from b2c_router_model import Router  # noqa: E402
from dds_model import PianoDDS, pitch_mod, signed  # noqa: E402
from envelope_model import Envelope, voice_pcm  # noqa: E402

ROM_NAMES = ("velocity_gain_rom.mem", "piano_band_4x256_8191.mem",
             "oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem")


def build_v4_operations():
    operations = []
    for op in build_operations():
        if op["case_id"] == "C06_READ_HOLD_RECOVERY" and op["op"] == "tick":
            continue
        if op["case_id"] == "C06_READ_HOLD_RECOVERY" and op["op"] == "read":
            if op["slot"] == 0:
                operations += [dict(case_id=op["case_id"], op="read_stall", slot=0, cycles=5),
                               dict(case_id=op["case_id"], op="set_result_ready", value=1),
                               dict(case_id=op["case_id"], op="wait_idle")]
        if op["case_id"] == "C06_READ_HOLD_RECOVERY" and op["op"] == "set_result_ready" and op["value"] == 1:
            continue
        operations.append(op)
        if op["op"] == "sample" and op["result_id"] == 0x1301:
            operations.append(dict(case_id="C07_CANCEL_RESET", op="cancel"))
        if op["op"] == "sample" and op["result_id"] == 0x1004:
            # Release is exactly 4800 audio ticks, never forced/reset to idle.
            for index in range(4800):
                operations += [dict(case_id="C04_CC64_MULTI_RECYCLE", op="sample",
                                    result_id=0x400000 + index, disposition="PUBLISH"),
                               dict(case_id="C04_CC64_MULTI_RECYCLE", op="wait_idle")]
    # Independent integer search: at tick119 the 32 signed voice samples are
    # 30*(-1025), -985, -1033. Their exact sum is -32768: PCM24 minimum
    # without saturation, so a fullscale-amplitude proxy for clip is wrong.
    operations.append(dict(case_id="C09_EXACT_FULLSCALE_NOT_CLIPPED", op="reset"))
    for lane in range(32):
        operations.append(dict(case_id="C09_EXACT_FULLSCALE_NOT_CLIPPED", op="note_on",
                               source=lane//16, channel=lane%16, note=60,
                               velocity=1017 if lane < 30 else 992 if lane == 30 else 1022,
                               expression=900))
    for index in range(119):
        operations += [dict(case_id="C09_EXACT_FULLSCALE_NOT_CLIPPED", op="sample",
                            result_id=0x900000+index, disposition="PUBLISH"),
                       dict(case_id="C09_EXACT_FULLSCALE_NOT_CLIPPED", op="wait_idle")]
    return operations


class FrameOracle:
    """Independent settled-boundary oracle; exact clocks audited separately."""
    def __init__(self):
        self.rom = {name: [int(x, 16) for x in (FROZEN / "rom" / name).read_text(encoding="utf-8").split()]
                    for name in ROM_NAMES}
        self.epoch = 0
        self.serial = 0
        self.event_serial = 0
        self.read_serial = 0
        self.result_ready = True
        self.retirements = 0
        self.reset()

    def reset(self):
        self.router = Router(32)
        self.env = [Envelope(self.rom[ROM_NAMES[0]]) for _ in range(32)]
        self.dds = [PianoDDS() for _ in range(32)]
        self.lfo = [0] * 32
        self.controls = {}
        self.bank = [0] * 32
        self.pending_bank = None

    def edge(self, *, event=None, tick=False, fcws=None, owner=True):
        r = self.router
        on, off = r.on, r.off
        done = sum(int(s["occupied"] and s["releasing"] and e.state == 0 and not on & (1 << i)) << i
                   for i, (s, e) in enumerate(zip(r.slots, self.env)))
        for i, (s, env, osc) in enumerate(zip(r.slots, self.env, self.dds)):
            env.edge(tick=tick, on=bool(on & (1 << i)), off=bool(off & (1 << i)), velocity=s["velocity"])
            osc.edge(fcws[i] if tick else s["fcw"], s["velocity"], tick=tick, note_on=bool(on & (1 << i)))
            if on & (1 << i):
                self.lfo[i] = 0
        r.edge(event=event, release_done=done, owner=owner)

    def settle(self, owner=True):
        for _ in range(150):
            before = [e.registers() for e in self.env]
            self.edge(owner=owner)
            if not self.router.busy() and not (self.router.on | self.router.off) and before == [e.registers() for e in self.env]:
                return
        raise ValueError("INDEPENDENT_SETTLE_BOUND")

    def apply(self, index, op):
        name = op["op"]
        if name == "reset":
            self.retirements += self.router.counts["retirements"]
            self.reset()
            self.epoch += 1
        elif name in ("note_on", "note_off", "cc64", "control_event"):
            event_type, control_id = (0, 0)
            if name == "note_off":
                event_type = 1
            elif name == "cc64":
                event_type, control_id = 4, 6
            elif name == "control_event":
                event_type, control_id = CONTROL_EVENT_SPECS[op["control"]]
            value = op.get("value", 4095 if op.get("down") else 0)
            word = pack_event(event_type=event_type, source=op["source"], channel=op["channel"],
                              note=op.get("note", 0), velocity=op.get("velocity", 0),
                              expression=op.get("expression", 0), control_id=control_id, control_value=value)
            self.settle()
            self.edge(event=word)
            if name == "control_event":
                key = op["source"], op["channel"]
                ctl = list(self.controls.get(key, (0, 0, 2)))
                ctl[("pitch_bend", "modulation", "pitch_range").index(op["control"])] = value
                self.controls[key] = tuple(ctl)
            self.settle()
            record = dict(record="EVENT", plan_index=index, event_serial=self.event_serial,
                          reset_lifetime=self.epoch, event_word=word,
                          slots_after=[dict(s) for s in self.router.slots])
            self.event_serial += 1
            return record
        elif name == "sample":
            slots = [dict(s) for s in self.router.slots]
            record = dict(record="TXN", plan_index=index, accept_serial=self.serial,
                          reset_lifetime=self.epoch, result_id=op["result_id"], disposition=op["disposition"],
                          slots_snapshot=slots,
                          controls_snapshot=[list(self.controls.get((s["source"], s["channel"]), (0, 0, 2)))
                                             if s["occupied"] else [0, 0, 2] for s in slots])
            self.serial += 1
            if op["disposition"] == "CANCEL":
                record.update(advance=False, left_pcm=None, right_pcm=None, clipped=None)
                return record
            self.settle()
            fcws = []
            for i, s in enumerate(slots):
                ctl = self.controls.get((s["source"], s["channel"]), (0, 0, 2)) if s["occupied"] else (0, 0, 2)
                fcws.append(pitch_mod(s["fcw"], signed(ctl[0], 12), ctl[1], ctl[2], self.lfo[i],
                                      self.rom[ROM_NAMES[2]], self.rom[ROM_NAMES[3]], self.rom[ROM_NAMES[4]])
                            if s["occupied"] else s["fcw"])
                if s["occupied"]:
                    self.lfo[i] = (self.lfo[i] + 447392) & 0xffffffff
            self.edge(tick=True, fcws=fcws, owner=False)
            self.settle(owner=False)
            # Configuration updates the currently readable descriptor bank
            # before launch. A real retirement changes identity and aborts the
            # in-flight token after ADVANCE; oscillator/envelope state remains.
            descriptors = [(s["note"] << 42) | (s["velocity"] << 32) | s["fcw"] for s in slots]
            self.bank = descriptors
            voices = []
            for s, env, osc in zip(slots, self.env, self.dds):
                wave = signed(self.rom[ROM_NAMES[1]][(osc.active_table << 8) | (osc.phase >> 24)], 16)
                voices.append(voice_pcm(wave, env.snapshot()["envelope"]) if s["occupied"] else 0)
            total = sum(voices)
            pcm = max(-(1 << 23), min((1 << 23)-1, total))
            self.pending_bank = [((v & 0xffffff) << 50) | (s["note"] << 42) | (s["velocity"] << 32) | s["fcw"]
                                 for s, v in zip(slots, voices)]
            identity_changed = any(a["occupied"] != b["occupied"] for a, b in zip(slots, self.router.slots))
            if identity_changed:
                self.pending_bank = None
                record.update(disposition="IDENTITY_CANCEL", advance=True, left_pcm=None,
                              right_pcm=None, clipped=None, abort_reason=2)
                return record
            if self.result_ready:
                self.bank, self.pending_bank = self.pending_bank, None
                self.settle()
            record.update(advance=True, left_pcm=pcm, right_pcm=pcm, clipped=int(pcm != total),
                          slot_pcm=voices, source="INPUT_ROUTER_ENVELOPE_DDS_ROM")
            return record
        elif name == "set_result_ready":
            self.result_ready = bool(op["value"])
            if self.result_ready and self.pending_bank is not None:
                self.bank, self.pending_bank = self.pending_bank, None
                self.settle()
        elif name == "read":
            record = dict(record="READ", plan_index=index, read_serial=self.read_serial,
                          reset_lifetime=self.epoch, slot=op["slot"], context=self.bank[op["slot"]])
            self.read_serial += 1
            return record
        elif name == "await_release_done":
            self.settle()
            if self.router.slots[op["slot"]]["occupied"]:
                raise ValueError("INDEPENDENT_RETIREMENT_MISSING")
        elif name in ("wait_idle", "tick"):
            self.settle(owner=self.pending_bank is None)
        elif name in ("cancel", "read_stall"):
            pass
        else:
            raise ValueError("UNKNOWN_V4_OPERATION")
        return None


def generate():
    operations = build_v4_operations()
    body = [dict(record="PLAN", index=i, **op) for i, op in enumerate(operations)]
    meta = dict(record="META", schema="t061-n32c-plan-v4", n=32, response=1, clock_hz=40000000,
                b_review_key="T061-N32-B-RESULT-20261014-R01",
                b_snapshot_sha256="d475ed2acdd65037893cfc778ca7c99aa9c8d6c37c209a9217ce05e1174d3421")
    plan = [meta, *body, dict(record="END", operations=len(body), body_sha256=records_sha256([meta, *body]))]
    oracle = FrameOracle()
    timeline = []
    for i, op in enumerate(operations):
        rec = oracle.apply(i, op)
        if rec is not None:
            timeline.append(rec)
    expmeta = dict(record="META", schema="t061-n32c-expected-v4", plan_sha256=records_sha256(plan),
                   source="INPUT_ONLY_FROZEN_MATH", rom_sha256={n: hashlib.sha256((FROZEN / "rom" / n).read_bytes()).hexdigest() for n in ROM_NAMES})
    expected = [expmeta, *timeline, dict(record="END", events=oracle.event_serial,
                transactions=oracle.serial, reads=oracle.read_serial, retirements=oracle.retirements + oracle.router.counts["retirements"],
                body_sha256=records_sha256([expmeta, *timeline]))]
    return plan, expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan, expected = generate()
    write_jsonl(args.output / "plan_v4.jsonl", plan)
    write_jsonl(args.output / "expected_v4.jsonl", expected)
    print(json.dumps(dict(status="V4_INDEPENDENT_PLAN_MATH_GENERATED", plan_records=len(plan), expected_records=len(expected))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
