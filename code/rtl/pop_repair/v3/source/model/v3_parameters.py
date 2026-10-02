"""V3 conservative research candidate. Values are design choices, not measured piano data."""
from functools import lru_cache
import math
import numpy as np
FS = 48_000
BASE_FCW = (23409859, 24801882, 26276679, 27839171, 29494575, 31248413,
            33106541, 35075158, 37160835, 39370534, 41711627, 44191930)
BASS_INITIAL = (1, 1.1, .9, .7, .6, .45, .34, .25, .18, .13, .09, .06)
BASS_FLOOR = (1, 1.05, .85, .66, .50, .38, .28, .20, .14, .09, .06, .04)
# Q16 shift-subtract time constants: 2**shift / 48000 seconds.
DECAY_SHIFTS = (0, 18, 17, 16, 15, 15, 14, 14, 13, 13, 12, 12)
BASS_LIMIT = round(220 * 2**32 / FS)

def note_fcw(note):
    octave = (note - 60 - note % 12) // 12
    value = BASE_FCW[note % 12]
    return value << octave if octave >= 0 else value >> -octave

@lru_cache(maxsize=1)
def phase_rom_values():
    # Exact integer boundaries of EVERY possible ROM address change for all
    # twelve harmonic lookups. Between these boundaries the waveform is fixed.
    edges = []
    for k in range(1, 13):
        j = np.arange(1024*k, dtype=np.int64)
        edges.append((j*2**32+1024*k-1)//(1024*k))
    phases = np.unique(np.concatenate(edges))
    sine = np.array([round(32767*math.sin(2*math.pi*n/1024)) for n in range(1024)],dtype=np.int64)
    return np.array([sine[(((phases*k)&0xffffffff)>>22)] for k in range(1,13)])

def coefficient_box_bound(initial, floor):
    """Exact ROM-domain bound for ANY independent amplitude in floor..initial."""
    s = phase_rom_values()
    a, b = np.array(initial)[:,None], np.array(floor)[:,None]
    upper = np.sum(s*np.where(s>=0,a,b),axis=0)
    lower = np.sum(s*np.where(s>=0,b,a),axis=0)
    return int((lower.min()+16384)>>15), int((upper.max()+16384)>>15)

@lru_cache(maxsize=1)
def bass_coefficients():
    # Peak normalization across the entire independently decaying coefficient
    # box. Does NOT use a low L1 gain to make beating quieter. This is still
    # not equal loudness, so WAV listening also uses explicit RMS matching.
    lo, hi = 0., 8191.
    result = None
    for _ in range(24):
        scale = (lo+hi)/2
        a = [round(x*scale) for x in BASS_INITIAL]
        b = [round(x*scale) for x in BASS_FLOOR]
        minimum, maximum = coefficient_box_bound(a,b)
        if minimum>=-8192 and maximum<=8191:
            result = (a,b)
            lo=scale
        else:
            hi=scale
    assert result is not None
    return result
