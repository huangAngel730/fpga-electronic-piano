"""Sample-level integer V3 oscillator model, plus current formal ADSR reference.

Oscillator step matches post-tick phase and amplitude used by RTL scheduler.
ADSR is copied formal FLOAT reference: not a bit-exact ADSR or full-top model.
No router/CC64/HDMI/STAT is modeled here. Never present WAV as board evidence.
"""
from pathlib import Path
import sys
import numpy as np
from v3_parameters import FS, BASS_LIMIT, DECAY_SHIFTS, note_fcw, bass_coefficients

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / "baseline"))
from adsr_piano import PianoADSREnvelope

def mem(path):
    return np.array([int(s, 16) if int(s, 16)<32768 else int(s,16)-65536
                     for s in path.read_text(encoding="ascii").split()], dtype=np.int64)

def approach(current, target):
    return current + ((target-current+63)>>6) if target>=current else current-((current-target+63)>>6)

class BassOscillator:
    """12 exact integer harmonics; same phase state across retriggers; no detuning."""
    def __init__(self, fcw):
        self.fcw = fcw
        self.phase = 0
        self.initial, self.floor = bass_coefficients()
        self.target = [a<<16 for a in self.floor]
        self.amplitude = self.target.copy()
        self.rom = mem(SOURCE / "rom" / "sine_v3_1024_32767.mem")

    def note_on(self, velocity):
        for k, (a, b) in enumerate(zip(self.initial, self.floor)):
            extra = a-b
            extra = extra//2 if velocity<256 else (extra*3)//4 if velocity<768 else extra
            self.target[k] = (b+extra)<<16
        # Do NOT reload amplitude or phase: retrigger has no immediate jump.

    def step(self):
        self.phase = (self.phase+self.fcw) & 0xffffffff
        total = 0
        for k in range(12):
            self.amplitude[k] = approach(self.amplitude[k], self.target[k])
            gap = self.target[k]-(self.floor[k]<<16)
            if gap>0 and DECAY_SHIFTS[k]:
                self.target[k] -= (gap+(1<<DECAY_SHIFTS[k])-1)>>DECAY_SHIFTS[k]
            if self.fcw*(k+1) <= (20000*2**32)//FS:
                address = (((self.phase*(k+1)) & 0xffffffff)>>22)
                total += int(self.rom[address])*(self.amplitude[k]>>16)
        # Single final rounding, then defensive clamp (bound normally tighter).
        return min(8191, max(-8192, (total+16384)>>15))

class LegacyOscillator:
    """Current formal V1 or V2 algorithm transplant, not old whole bitstream."""
    def __init__(self, fcw, version="v1", lane=0):
        self.fcw, self.phase, self.version = fcw, 0, version
        self.remaining = 0
        self.active = 3
        self.pending = None
        if version=="v1":
            self.rom = mem(SOURCE / "baseline" / "piano_band_4x256_8191.mem")
        else:
            from generate_wavetable_v2 import build_table, TABLE_MAGNITUDES, LANE_SIGNS
            self.rom = np.array([x for a in TABLE_MAGNITUDES for x in build_table(a, LANE_SIGNS[lane])])
        f = fcw*FS/2**32
        if version=="v1":
            self.body, self.attack = (1,0) if f<=1500 else (2,1) if f<=3000 else (3,2) if f<=6000 else (3,3)
        else:
            self.body, self.attack = (1,0) if f<=1500 else (2,1) if f<=3000 else (2,2) if f<=4400 else (3,3)
        self.lane = lane

    def note_on(self, velocity):
        self.remaining = 1440 if velocity>=768 else 960 if velocity>=512 else 480 if velocity>=256 else 0
        if self.version=="v2" and self.remaining:
            self.remaining = max(0, self.remaining-self.lane*48)
        self.active = self.attack if self.remaining else self.body
        self.pending = None

    def step(self):
        old_phase = self.phase
        self.phase = (old_phase+self.fcw)&0xffffffff
        wrapped = self.phase<old_phase
        if self.pending is not None and wrapped:
            self.active = self.pending
            self.pending = None
        elif self.remaining:
            self.remaining -= 1
            if not self.remaining:
                if wrapped:
                    self.active = self.body
                else:
                    self.pending = self.body
        return int(self.rom[self.active*256+(self.phase>>24)])

def render(notes, version="v3", velocity=900, duration=3., release_at=2.5):
    """Independent static lanes, not allocator simulation; 1/4 mix headroom.

    This generates diagnostic PCM16 directly from Q15 waves and envelope.
    Not bit-exact formal PCM24 mixer/quantizer: M2 must compare actual RTL.
    """
    count = round(FS*duration)
    mix = np.zeros(count, dtype=np.int64)
    for lane, note in enumerate(notes):
        fcw = note_fcw(note)
        osc = BassOscillator(fcw) if version=="v3" and fcw<=BASS_LIMIT else LegacyOscillator(fcw, "v1" if version=="v3" else version, lane)
        env = PianoADSREnvelope()
        osc.note_on(velocity)
        env.note_on(velocity)
        for i in range(count):
            if i==round(release_at*FS):
                env.note_off()
            mix[i] += (osc.step()*env.step())>>15
    return np.clip(mix//4, -32768, 32767).astype("<i2")
