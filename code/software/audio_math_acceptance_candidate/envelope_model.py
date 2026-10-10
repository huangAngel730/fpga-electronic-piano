"""Frozen capture2 integer ADSR: pre-NBA registers and clocked ROM/products.

No capture values enter this model. Quiet intervals are skipped only after the
entire register tuple reaches a fixed point, not by assuming sample-only math.
"""
from dds_model import MASK32, signed

PUBLIC = (0, 1, 1, 1, 2, 3, 4, 1, 1, 4, 4)


class Envelope:
    def __init__(self, gain_rom):
        if len(gain_rom) != 1024 or any(not 0 <= x <= 32767 for x in gain_rom):
            raise ValueError("GAIN_ROM_SHAPE_OR_RANGE")
        self.rom = tuple(gain_rom)
        self.reset()

    def reset(self, cycle=0):
        self.cycle = cycle
        self.state = self.level = self.start = self.peak = self.sustain = 0
        self.step = self.elapsed = self.pending = self.release_start = self.addr = 0
        self.delta_q = self.product_q = self.sustain_product = 0
        self.recip_q = 894785
        # ROM and sustain products are unreset RTL registers; the first useful
        # observation is after quiet reset clocks. These values are settled then.
        self.rom_dout = self.rom[0]

    def registers(self):
        return tuple(getattr(self, name) for name in (
            "state", "level", "start", "peak", "sustain", "step", "elapsed",
            "pending", "release_start", "addr", "delta_q", "product_q",
            "sustain_product", "recip_q", "rom_dout"))

    def snapshot(self):
        return {"raw_state": self.state, "public_state": PUBLIC[self.state],
                "level_q16": self.level, "start_q16": self.start,
                "peak_q16": self.peak, "sustain_q16": self.sustain,
                "step_q16_twos33": self.step & ((1 << 33) - 1),
                "elapsed": self.elapsed, "envelope": self.level >> 16}

    def quiet_until(self, cycle):
        """Advance all edges strictly before cycle; cycle is the next input edge."""
        if cycle <= self.cycle:
            raise ValueError("ENVELOPE_EDGE_ORDER")
        remaining = cycle - self.cycle - 1
        for _ in range(min(remaining, 12)):
            before = self.registers()
            self.edge()
            remaining -= 1
            if self.registers() == before:
                self.cycle += remaining
                return
        if remaining:
            raise ValueError("ENVELOPE_QUIET_NOT_FIXED")

    def edge(self, tick=False, on=False, off=False, velocity=0):
        before = self.snapshot()
        state, level = self.state, self.level
        quotient = signed(self.product_q >> 32, 33)
        delta, recip = 0, 894785
        if off and state != 0:
            delta = -level
        elif state == 2:
            delta, recip = (self.rom_dout << 16) - self.start, 17895697
        elif state == 3:
            delta = self.sustain - self.peak
        next_level = signed(level + self.step, 33)
        first_level = signed(self.start + quotient, 33)
        new_product = signed(self.delta_q * self.recip_q, 59)
        new_rom = self.rom[self.addr]
        new_sustain_product = (level & 0x7fffffff) * 13422
        if tick and self.pending and state in (1, 2, 7, 8, 9, 10) and not on and not off:
            raise ValueError("ENVELOPE_DUPLICATE_PENDING_TICK")
        if on:
            if type(velocity) is not int or not 0 <= velocity <= 1023:
                raise ValueError("ENVELOPE_VELOCITY_RANGE")
            self.addr, self.start, self.elapsed = velocity, level, 0
            self.pending, self.state = int(tick), 1
        elif off and state != 0:
            self.release_start, self.pending, self.elapsed, self.state = level, int(tick), 0, 9
        elif state == 9:
            self.pending |= int(tick)
            self.state = 10
        elif state == 10:
            self.step = quotient
            self.elapsed = int(bool(self.pending or tick))
            if self.pending or tick:
                self.level = max(0, signed(self.release_start + quotient, 33)) & MASK32
            self.pending, self.state = 0, 6
        elif state == 1:
            self.pending |= int(tick)
            self.state = 2
        elif state == 2:
            self.peak = self.rom_dout << 16
            self.sustain = (((self.rom_dout * 13108) & MASK32) >> 15) << 16 & MASK32
            self.pending |= int(tick)
            self.state = 7
        elif state == 7:
            self.pending |= int(tick)
            self.state = 8
        elif state == 8:
            self.step = quotient
            self.level = (first_level if self.pending or tick else self.start) & MASK32
            self.elapsed = int(bool(self.pending or tick))
            self.pending, self.state = 0, 3
        elif tick:
            if state == 3 and self.elapsed == 239:
                self.level, self.step, self.elapsed, self.state = self.peak, quotient, 0, 4
            elif state == 4 and self.elapsed == 4800:
                self.level, self.elapsed, self.state = self.sustain, 0, 5
            elif state in (3, 4):
                self.level, self.elapsed = next_level & MASK32, (self.elapsed + 1) & 8191
            elif state == 5:
                if level < 65536:
                    self.level, self.state = 0, 0
                else:
                    self.level = (level - (self.sustain_product >> 32)) & MASK32
            elif state == 6:
                if self.elapsed == 4799:
                    self.level, self.elapsed, self.state = 0, 0, 0
                else:
                    self.level, self.elapsed = max(next_level, 0) & MASK32, (self.elapsed + 1) & 8191
            else:
                self.level = 0
        self.delta_q, self.recip_q, self.product_q = signed(delta, 33), recip, new_product
        self.rom_dout, self.sustain_product = new_rom, new_sustain_product
        self.cycle += 1
        return before


def voice_pcm(wave, envelope):
    if not -32768 <= wave <= 32767 or not 0 <= envelope <= 32767:
        raise ValueError("VOICE_GAIN_INPUT_RANGE")
    sample = signed((wave * envelope) >> 15, 16)
    return sample << 8


def mix_pcm(voices):
    if len(voices) != 4 or any(not -(1 << 23) <= x < (1 << 23) for x in voices):
        raise ValueError("MIX_INPUT_RANGE")
    total = sum(voices)
    pcm = max(-(1 << 23), min((1 << 23) - 1, total))
    return pcm, pcm != total
