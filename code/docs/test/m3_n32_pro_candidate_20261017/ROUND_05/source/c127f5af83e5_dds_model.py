"""Integer DDS/brightness/PitchMod reference, no capture-derived expected values."""
from dataclasses import dataclass

MASK32 = (1 << 32) - 1
SEMITONES = (23409859, 24801882, 26276679, 27839171, 29494575, 31248413,
             33106541, 35075158, 37160835, 39370534, 41711627, 44191930)


def note_fcw(note):
    if type(note) is not int or not 0 <= note <= 127:
        raise ValueError("NOTE_RANGE")
    octave, semitone = divmod(note, 12)
    shift = octave - 5
    base = SEMITONES[semitone]
    return ((base << shift) if shift >= 0 else (base >> -shift)) & MASK32


def signed(value, bits):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def pitch_mod(base, bend, modulation, pitch_range, lfo_phase, oct_rom, sub_rom, sine_rom):
    """Frozen pipeline's widths, arithmetic shifts, table floor and rounding.

    Inputs must be independently recovered accepted control/base snapshots.
    Caller owns LFO clocking: accepted occupied launch advances by447392;
    note_on chooses phase0 even on a simultaneous launch, reset cancels tokens.
    """
    if not (all(type(v) is int for v in (base, bend, modulation, pitch_range, lfo_phase))
            and 0 <= base <= MASK32 and -2048 <= bend <= 2047 and 0 <= modulation <= 4095
            and 0 <= pitch_range <= 24 and 0 <= lfo_phase <= MASK32):
        raise ValueError("PITCH_INPUT_RANGE")
    if (len(oct_rom), len(sub_rom), len(sine_rom)) != (50, 1024, 1024):
        raise ValueError("PITCH_ROM_SHAPE")
    semi = signed(bend * pitch_range, 17) >> 1
    depth = ((modulation * 512 + 2048) & ((1 << 22) - 1)) >> 12
    vibrato = signed(signed(sine_rom[lfo_phase >> 22], 16) * depth, 26) >> 15
    total = signed(semi + signed(vibrato, 17), 18)
    oct_index = 49 if (total >> 10) > 24 else 0 if (total >> 10) < -25 else (total >> 10) + 25
    ratio = (oct_rom[oct_index] * sub_rom[total & 1023]) & ((1 << 40) - 1)
    factor = (ratio >> 16) & ((1 << 24) - 1)
    raw = (((base * factor + 32768) & ((1 << 57) - 1)) >> 16) & ((1 << 33) - 1)
    return min(raw, 0x80000000)


@dataclass
class PianoDDS:
    phase: int = 0
    attack_left: int = 0
    active_table: int = 3
    pending_table: int = 3
    change_pending: bool = False

    def reset(self):
        self.phase, self.attack_left = 0, 0
        self.active_table = self.pending_table = 3
        self.change_pending = False

    def edge(self, fcw, velocity=0, tick=False, note_on=False):
        """Return pre-NBA state, then advance exactly one active edge.

        note_on changes table/count but never resets DDS phase; simultaneous
        tick still advances phase but does not shorten the new attack window.
        """
        if type(fcw) is not int or not 0 <= fcw <= MASK32 or type(velocity) is not int or not 0 <= velocity <= 1023:
            raise ValueError("DDS_INPUT_RANGE")
        before = {"phase_acc": self.phase, "table": self.active_table,
                  "rom_addr": (self.active_table << 8) | (self.phase >> 24)}
        body, attack = ((1, 0) if fcw <= 134217728 else (2, 1) if fcw <= 268435456
                        else (3, 2) if fcw <= 536870912 else (3, 3))
        next_phase = (self.phase + fcw) & MASK32
        wrap = next_phase < self.phase
        if note_on:
            self.attack_left = 1440 if velocity >= 768 else 960 if velocity >= 512 else 480 if velocity >= 256 else 0
            self.active_table = attack if self.attack_left else body
            self.change_pending = False
        elif tick:
            if self.change_pending and wrap:
                self.active_table = self.pending_table
                self.change_pending = False
            elif self.attack_left:
                self.attack_left -= 1
                if self.attack_left == 0:
                    if wrap:
                        self.active_table = body
                    else:
                        self.pending_table = body
                        self.change_pending = True
        if tick:
            self.phase = next_phase
        return before


def replay_states(rows, independent_fcw):
    """Check every STATE including final rows; no default observed-FCW oracle.

    independent_fcw(row) must derive fcw from accepted control/event history,
    not row.dds_fcw or F/D observed result. Not yet wired to realcapture2.
    """
    lanes = [PianoDDS() for _ in range(4)]
    compared = 0
    for row in rows:
        if row["tag"] == "RESET":
            for lane in lanes:
                lane.reset()
        elif row["tag"] == "STATE":
            fcw = independent_fcw(row)
            if int(row["dds_fcw"], 16) != fcw:
                raise ValueError(f"DDS_FCW:{row['epoch']}:{row['cycle']}:{row['lane']}")
            expected = lanes[row["lane"]].edge(fcw, row["velocity"], bool(row["tick"]), bool(row["note_on"]))
            for field, actual in (("phase_acc", int(row["phase_acc"], 16)), ("table", row["table"])):
                if actual != expected[field]:
                    raise ValueError(f"DDS_{field}:{row['epoch']}:{row['cycle']}:{row['lane']}")
            compared += 1
    return {"status": "PARTIAL_DDS_ONLY", "state_rows_compared": compared, "complete_audio_golden": False}
