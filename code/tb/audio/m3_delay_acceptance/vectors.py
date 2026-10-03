"""Independent integer delay recurrence and cycle-level, reset-aware vectors.

No import or reuse of M1 DelayEffectFixed/vector generators.
"""
from dataclasses import dataclass, field
import random

MIN_PCM, MAX_PCM = -(1 << 23), (1 << 23) - 1


def saturate(value):
    return max(MIN_PCM, min(MAX_PCM, value))


@dataclass
class Recurrence:
    depth: int
    memory: list = field(init=False)
    pointer: int = 0
    output: int = 0
    pending: tuple | None = None
    statistics: dict = field(default_factory=lambda: {
        "positive_output_saturation": 0, "negative_output_saturation": 0,
        "positive_feedback_saturation": 0, "negative_feedback_saturation": 0})

    def __post_init__(self):
        self.memory = [0] * self.depth

    def cycle(self, index, reset, enable, pcm, delay, dry, wet, feedback):
        if not reset:
            self.memory = [0] * self.depth
            self.pointer = 0
            self.output = 0
            self.pending = None
            return 0, 0
        valid = 0
        if self.pending and self.pending[0] == index:
            _, self.output, stored = self.pending
            self.memory[self.pointer] = stored
            self.pointer = (self.pointer + 1) % self.depth
            self.pending = None
            valid = 1
        if enable:
            if self.pending:
                raise ValueError("overlapping request violates fixture contract")
            delayed = self.memory[(self.pointer - delay) % self.depth]
            # Each signed product floors independently, THEN growth-bit addition.
            raw_output = ((pcm * dry) >> 15) + ((delayed * wet) >> 15)
            raw_stored = pcm + ((delayed * feedback) >> 15)
            for name, raw in (("output", raw_output), ("feedback", raw_stored)):
                self.statistics[f"positive_{name}_saturation"] += int(raw > MAX_PCM)
                self.statistics[f"negative_{name}_saturation"] += int(raw < MIN_PCM)
            output = saturate(raw_output)
            stored = saturate(raw_stored)
            self.pending = (index + 2, output, stored)
        return valid, self.output


def generate(depth, zero_policy="pending"):
    rng = random.Random(20261003)
    oracle = Recurrence(depth)
    rows, counters = [], {"launched": 0, "valid": 0, "random_parameters": 0,
                          "reset_scenarios": 0, "zero_delay_samples": 0}

    def row(reset=1, enable=0, params=None):
        if params is None:
            # Deliberately hostile live changes on EVERY non-sampling clock.
            params = (rng.randint(MIN_PCM, MAX_PCM), rng.randrange(depth),
                      rng.randrange(32768), rng.randrange(32768), rng.randrange(32768))
        pcm, delay, dry, wet, feedback = params
        valid, output = oracle.cycle(len(rows), reset, enable, *params)
        rows.append((reset, enable, pcm, delay, dry, wet, feedback, valid, output))
        counters["launched"] += int(bool(enable and reset))
        counters["valid"] += valid

    def reset():
        row(reset=0); row(reset=0); row(reset=0)
        row()
        counters["reset_scenarios"] += 1

    def sample(pcm, delay, dry, wet, feedback, spacing=4):
        row(enable=1, params=(pcm, delay, dry, wet, feedback))
        for _ in range(spacing - 1):
            row()

    reset()
    for pcm in (MAX_PCM, MAX_PCM, MAX_PCM, MIN_PCM, MIN_PCM, MIN_PCM):
        sample(pcm, 1, 32767, 32767, 32767)
    for n in range(64):
        sample([MIN_PCM, MAX_PCM, 0, -1, 1, 1234567, -7654321, 2][n % 8],
               1, [0, 32767, 16384, 1][n % 4], 32767, 32767)
    # A continuous segment exceeds THREE complete wraps without resetting.
    for n in range(4 * depth + 64):
        sample(MAX_PCM if n % 7 == 0 else (MIN_PCM if n % 11 == 0 else 2000000),
               depth-1, 32767, 32767, 32767)
    counters["uninterrupted_wraps"] = (4 * depth + 128) // depth
    for _ in range(2048):
        sample(rng.randint(MIN_PCM, MAX_PCM), rng.choice((1, depth-1, rng.randrange(1, depth))),
               rng.randrange(32768), rng.randrange(32768), rng.randrange(32768), rng.randrange(4, 9))
        counters["random_parameters"] += 1
    if zero_policy == "modulo_depth_old":
        reset()
        for n in range(4*depth+3):
            sample(2000 if n == 0 else 0, 0, 0, 16384, 0)
            counters["zero_delay_samples"] += 1
    elif zero_policy != "pending":
        raise ValueError("unsupported confirmed zero policy")
    # Populate nonzero history before reset at each pipeline boundary, and tail.
    for age in (0, 1, 2, 7):
        for n in range(32):
            sample(1000000 + n, 1, 32767, 32767, 32767)
        row(enable=1, params=(MIN_PCM, depth-1, 32767, 32767, 32767))
        for _ in range(age):
            row()
        reset()  # asserted between launch and E+1/E+2/E+3 or after nonzero tail
        for _ in range(depth + 3):
            sample(0, depth-1, 0, 32767, 32767)
    for _ in range(16):
        row()
    assert counters["random_parameters"] >= 2048 and counters["uninterrupted_wraps"] > 3
    assert all(oracle.statistics.values()), "positive/negative output and feedback saturation required"
    counters.update(oracle.statistics)
    return rows, counters


def write_vectors(path, rows):
    if not rows:
        raise ValueError("empty vectors")
    path.write_text(str(len(rows)) + "\n" + "".join(" ".join(map(str, row)) + "\n" for row in rows),
                    encoding="utf-8", newline="\n")


def read_vectors(path, depth):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or int(lines[0]) <= 0:
        raise ValueError("empty vector count")
    if len(lines)-1 != int(lines[0]):
        raise ValueError("vector count mismatch")
    rows = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) != 9:
            raise ValueError("malformed vector record")
        r = tuple(map(int, fields))
        if not (r[0] in (0, 1) and r[1] in (0, 1) and MIN_PCM <= r[2] <= MAX_PCM
                and 0 <= r[3] < depth and all(0 <= x < 32768 for x in r[4:7])
                and r[7] in (0, 1) and MIN_PCM <= r[8] <= MAX_PCM):
            raise ValueError("out-of-range vector")
        rows.append(r)
    return rows


def check_capture(path, rows):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or len(lines) != len(rows):
        raise ValueError("empty capture/count mismatch")
    for index, (line, row) in enumerate(zip(lines, rows)):
        fields = line.split()
        if len(fields) != 3 or any(c in fields[2].lower() for c in "xz"):
            raise ValueError("malformed/unknown capture")
        cycle, valid, pcm = int(fields[0]), int(fields[1]), int(fields[2], 16)
        pcm = pcm - (1 << 24) if pcm & (1 << 23) else pcm
        if cycle != index or (valid, pcm) != row[7:9]:
            raise AssertionError(f"delay capture cycle {index}: {(valid, pcm)} != {row[7:9]}")
