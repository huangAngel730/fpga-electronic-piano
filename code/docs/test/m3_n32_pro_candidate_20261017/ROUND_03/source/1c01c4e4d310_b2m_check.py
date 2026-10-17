"""Independent PCM replay of the ORIGINAL B2K directed cancellation captures.

Only accepted event/sample inputs, reset and cancel drive the reference. The
old source-clock checker is reused for transport/timing, never PCM expectations.
No new RTL run, no observed phase/FCW/PCM fed back into mathematical state.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from b2k_check import Cancellation, FIELDS, check as timing_check
from b2c_router_model import Router
from inventory import FROZEN
from dds_model import MASK32, PianoDDS, pitch_mod, signed
from envelope_model import Envelope, voice_pcm

STATUS = "B2M_DIRECTED_RECOVERY_PCM_MATCH_T061_PARTIAL"
ROM_NAMES = ("velocity_gain_rom.mem", "piano_band_4x256_8191.mem",
             "oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def parse_verified(raw):
    """Timing/schema must be checked first, including FCW, CASE and full END."""
    for line in raw.decode("ascii").splitlines():
        fields = line.split()
        if fields and fields[0] == "T":
            yield dict(zip(FIELDS, map(int, fields[1:])))


class Mathematics:
    """Persistent DSP state plus discardable render context, PRE-NBA edges.

    Static A4 stimulus is deliberately narrow. LFO is tracked, but modulation
    is zero in this fixture, so its persistence is NOT empirically proved.
    """
    def __init__(self, n, response, roms=None):
        self.n, self.response = n, response
        self.clock = Cancellation(n, response)
        self.rom = roms if roms is not None else {
            name: [int(x, 16) for x in (FROZEN / "rom" / name).read_text(
                encoding="utf-8").split()] for name in ROM_NAMES}
        require([len(self.rom[k]) for k in ROM_NAMES] == [1024, 1024, 50, 1024, 1024],
                "B2M_ROM_SHAPE")
        self.env = [Envelope(self.rom[ROM_NAMES[0]]) for _ in range(n)]
        self.dds = [PianoDDS() for _ in range(n)]
        self.lfo = [0] * n
        self.router = Router(n)
        self.frame = None
        self.expected_output = None
        self.counts = Counter()
        self.outputs = []
        self.cancel_advances = 0

    def reset(self, cycle):
        self.router = Router(self.n)
        self.lfo = [0] * self.n
        self.frame = self.expected_output = None
        for env, osc in zip(self.env, self.dds):
            env.reset(cycle)
            osc.reset()

    def edge(self, row):
        c, stop = row["cycle"], bool(row["cancel"])
        k = self.clock
        if not row["rst"]:
            self.reset(c)
            k.edge(row)
            self.counts["reset_edges"] += 1
            return
        idle = k.mode == "idle" and k.scheduler == "idle" and k.backend == "idle" \
            and c >= max(k.pitch_clear, k.rom_clear)
        launch = k.mode == "frame" and c == k.c and not stop
        advance = k.backend == "run" and c == k.c + 8 and not stop
        valid = k.mode == "frame" and c >= k.f
        on, off = self.router.on, self.router.off
        if valid:
            require(self.expected_output is not None, "B2M_OUTPUT_WITHOUT_ALL_SLOTS")
            pcm = self.expected_output
            self.compare_pcm(row, pcm)
            self.counts["valid_edges_checked"] += 1
            if c == k.f:
                self.counts["first_valid_checked"] += 1
            if row["rr"] and not stop:
                self.counts["published_pcm_checked"] += 1
                self.counts["nonzero_published_pcm"] += pcm != 0
                self.outputs.append(dict(cycle=c, request=k.sid, pcm=pcm,
                                         advance_count=self.cancel_advances))
        if launch:
            require(not (on or off), "B2M_EVENT_LAUNCH_SCOPE")
            slots = [dict(s) for s in self.router.slots]
            fcws = []
            for i, s in enumerate(slots):
                fcws.append(pitch_mod(s["fcw"], 0, 0, 2, self.lfo[i],
                    self.rom[ROM_NAMES[2]], self.rom[ROM_NAMES[3]], self.rom[ROM_NAMES[4]])
                    if s["occupied"] else s["fcw"])
                if s["occupied"]:
                    self.lfo[i] = (self.lfo[i] + 447392) & MASK32
            self.frame = dict(accepted=c, slots=slots, fcw=fcws,
                              envelopes=None, waves={}, lanes={})
            self.expected_output = None
            self.counts["backend_launches"] += 1
        f = self.frame
        if f and k.backend == "run" and not stop:
            offset = c - f["accepted"]
            if offset == 13:
                # SETTLE latches old live_envelopes before this edge's ADSR work.
                f["envelopes"] = [e.snapshot()["envelope"] for e in self.env]
            for i in range(self.n):
                if offset == 14 + i * (self.response + 3):
                    osc = self.dds[i]
                    f["waves"][i] = signed(self.rom[ROM_NAMES[1]][
                        (osc.active_table << 8) | (osc.phase >> 24)], 16)
                if offset == 15 + self.response + i * (self.response + 3):
                    require(f["envelopes"] is not None and i in f["waves"],
                            "B2M_RENDER_CALENDAR")
                    amplitude, wave = f["envelopes"][i], f["waves"][i]
                    pcm = voice_pcm(wave, amplitude) if f["slots"][i]["occupied"] else 0
                    f["lanes"][i] = pcm
                    self.counts["independently_rendered_lanes"] += 1
                    self.counts["nonzero_rendered_lanes"] += pcm != 0
                    self.counts["negative_fractional_gain"] += (
                        f["slots"][i]["occupied"] and wave < 0 and wave * amplitude % 32768 != 0)
                    if len(f["lanes"]) == self.n:
                        total = sum(f["lanes"].values())
                        self.expected_output = max(-(1 << 23), min((1 << 23) - 1, total))
        # Same-edge cancel suppresses only new work. Earlier DSP changes remain.
        for i, (env, osc, s) in enumerate(zip(self.env, self.dds, self.router.slots)):
            require(env.cycle == c - 1, "B2M_ENVELOPE_CONTIGUITY")
            env.edge(tick=advance, on=bool(on & (1 << i)),
                     off=bool(off & (1 << i)), velocity=s["velocity"])
            osc.edge(f["fcw"][i] if advance else s["fcw"], s["velocity"],
                     tick=advance, note_on=bool(on & (1 << i)))
            if on & (1 << i):
                self.lfo[i] = 0
                self.counts["note_on_pulses"] += 1
        if advance:
            self.cancel_advances += 1
            self.counts["persistent_advances"] += 1
        if stop:
            if f and c > f["accepted"] + 8:
                self.counts["cancel_edges_after_advance"] += 1
            self.frame = self.expected_output = None
        event = row["data"] if row["ev"] and row["er"] else None
        self.router.edge(event=event, owner=bool(idle and not row["sv"] and not stop))
        k.edge(row)

    @staticmethod
    def compare_pcm(row, pcm):
        require(row["left"] == pcm and row["right"] == pcm,
                f"B2M_PCM:{row['cycle']}:{row['left']},{row['right']}!={pcm}")


def check(raw):
    timing = timing_check(raw)
    model = Mathematics(timing["N"], timing["response"])
    rows = list(parse_verified(raw))
    fcws = {int(p[1]): int(p[2]) for p in (s.split() for s in raw.decode("ascii").splitlines())
            if p and p[0] == "FCW"}
    for row in rows:
        row["fcw"] = fcws.get(row["cycle"], 0)
        model.edge(row)
    require(model.counts["published_pcm_checked"] == 21 and model.counts["first_valid_checked"] == 21,
            "B2M_REQUIRED_OUTPUT_COVERAGE")
    require(model.counts["note_on_pulses"] == 5 and model.counts["nonzero_published_pcm"] > 0,
            "B2M_REQUIRED_SOUND_COVERAGE")
    return dict(status=STATUS, N=model.n, response=model.response,
                input_sha256=hashlib.sha256(raw).hexdigest(), counts=dict(model.counts),
                published_outputs=model.outputs, timing_reference=timing,
                task_complete=False, new_rtl_simulation=False, physical_STA=None,
                mathematical_scope="Original B2K static A4 / zero modulation / directed cancellation and whole-domain reset",
                observable_fields_checked=["left PCM24", "right PCM24", "valid HOLD PCM"],
                lane_math_fields_observed=False, LFO_nonrollback_proved=False,
                general_event_service_bound=None, production_admitted=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result, code = check(args.input.read_bytes()), 0
    except (ValueError, OSError, UnicodeError) as error:
        result, code = dict(status="B2M_REJECTED", diagnostic=str(error)), 1
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as out:
            json.dump(result, out, indent=2)
            out.write("\n")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
