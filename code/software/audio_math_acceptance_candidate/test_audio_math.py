"""Asserted A2 synthetic stage/clock/rounding boundaries, not hardware proof."""
import unittest

from envelope_model import Envelope, mix_pcm, voice_pcm
from dds_model import signed, note_fcw
import test_candidates as fixtures
from timeline import pack, replay


def audio_roms():
    return [[int(x, 16) for x in (fixtures.FROZEN / "rom" / name).read_text(encoding="utf-8").split()]
            for name in ("velocity_gain_rom.mem", "piano_band_4x256_8191.mem")]


def audio_fixture(note):
    """Build SYNTHETIC expected using closed-form first attack step, not ADSR model."""
    j, f = fixtures.timeline_fixture(note)
    gain, wave = audio_roms()
    peak = gain[256] << 16 if note else 0
    step = (peak * 17895697) >> 32
    sustain = ((gain[256] * 13108) >> 15) << 16 if note else 0
    for row in j["rows"]:
        if row["tag"] == "STATE" and note and row["tick"] and row["lane"] == 0:
            row.update(raw_state=3, public_state=1, peak_q16=f"{peak:08x}",
                       sustain_q16=f"{sustain:08x}", step_q16_twos33=f"{step:09x}")
    value = signed(wave[note_fcw(60) >> 24], 16) if note else signed(wave[768], 16)
    env = step >> 16 if note else 0
    # The scalar formula is deliberately separate from voice_pcm/mix_pcm.
    pcm = ((value * env) // 32768) * 256
    for row in f["rows"]:
        if row["tag"] == "H" and note:
            row["values"][2:4] = [pack([value, wave[768], wave[768], wave[768]], 16), env]
        elif row["tag"] == "M":
            row["values"][1:3] = [pcm & 0xffffff] * 2
        elif row["tag"] == "END":
            row["values"][1] = int(pcm != 0)
    for row in j["rows"]:
        if row["tag"] == "COMMIT":
            row["pcm_left"] = row["pcm_right"] = pcm
    return j, f


class EnvelopeTests(unittest.TestCase):
    def model(self):
        return Envelope([0] + [32767] * 1023)

    def settled_attack(self):
        model = self.model()
        model.quiet_until(5)
        self.assertEqual(model.edge(on=True, velocity=1)["raw_state"], 0)
        model.quiet_until(10)
        self.assertEqual((model.state, model.peak, model.elapsed, model.level), (3, 32767 << 16, 0, 0))
        self.assertEqual(model.step, ((32767 << 16) * 17895697) >> 32)
        return model

    def test_rom_and_two_stage_product_before_attack_apply(self):
        model = self.model()
        model.edge(on=True, velocity=1)
        states = []
        for _ in range(4):
            states.append(model.edge()["raw_state"])
        self.assertEqual(states, [1, 2, 7, 8])
        self.assertEqual((model.state, model.peak, model.level), (3, 32767 << 16, 0))
        self.assertEqual(model.step, ((32767 << 16) * 17895697) >> 32)

    def test_attack_decay_boundaries_and_sustain_pipeline(self):
        model = self.settled_attack()
        for index in range(240):
            model.quiet_until(20 + 20 * index)
            model.edge(tick=True)
        self.assertEqual((model.state, model.level, model.elapsed), (4, model.peak, 0))
        self.assertEqual(model.step, ((model.sustain - model.peak) * 894785) >> 32)
        for index in range(4801):
            model.quiet_until(5000 + 20 * index)
            model.edge(tick=True)
        self.assertEqual((model.state, model.level, model.elapsed), (5, model.sustain, 0))
        level = model.level
        model.quiet_until(model.cycle + 20)
        model.edge(tick=True)
        self.assertEqual(model.level, level - ((level & 0x7fffffff) * 13422 >> 32))

    def test_pending_tick_retrigger_release_and_terminal_zero(self):
        model = self.model()
        model.edge(tick=True, on=True, velocity=1)
        model.quiet_until(20)
        self.assertEqual((model.elapsed, model.level), (1, model.step))
        level = model.level
        before = model.edge(on=True, velocity=2)
        self.assertEqual(before["level_q16"], level)
        model.quiet_until(40)
        self.assertEqual((model.start, model.level, model.elapsed), (level, level, 0))
        model.edge(tick=True, off=True)
        model.quiet_until(60)
        release_step = (-level * 894785) >> 32
        self.assertEqual((model.state, model.step, model.elapsed, model.level),
                         (6, release_step, 1, max(0, level + release_step)))
        for _ in range(4799):
            model.quiet_until(model.cycle + 20)
            model.edge(tick=True)
        self.assertEqual((model.state, model.level, model.elapsed), (0, 0, 0))

    def test_sparse_clocks_equal_literal_quiet_clocks(self):
        fast, slow = self.model(), self.model()
        for cycle, on, off, tick in ((30, True, False, False), (100, False, False, True),
                                     (125, False, True, True), (300, False, False, True),
                                     (400, True, False, True)):
            fast.quiet_until(cycle)
            while slow.cycle < cycle - 1:
                slow.edge()
            self.assertEqual(fast.registers(), slow.registers())
            fast.edge(tick, on, off, 1023)
            slow.edge(tick, on, off, 1023)
        self.assertEqual(fast.registers(), slow.registers())

    def test_pending_tick_assertion_and_event_priority(self):
        model = self.model()
        model.edge(tick=True, on=True, off=True, velocity=1)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PENDING_TICK"):
            model.edge(tick=True)
        self.assertEqual(model.state, 1)
        model.edge(tick=True, on=True, velocity=2)
        self.assertEqual((model.state, model.addr), (1, 2))

    def test_sustain_threshold_and_input_validation(self):
        model = self.model()
        model.state, model.level = 5, 65535
        model.edge(tick=True)
        self.assertEqual((model.state, model.level), (0, 0))
        with self.assertRaisesRegex(ValueError, "GAIN_ROM"):
            Envelope([0])

    def test_gain_negative_floor_and_signed_limits(self):
        self.assertEqual(voice_pcm(-1, 1), -256)
        self.assertEqual(voice_pcm(1, 1), 0)
        self.assertEqual(voice_pcm(-32768, 32767), -8388352)
        self.assertEqual(voice_pcm(32767, 32767), 8388096)
        self.assertEqual(voice_pcm(-32768, 0), 0)
        for values, expected in (([8388607, 1, 0, 0], (8388607, True)),
                                 ([-8388608, -1, 0, 0], (-8388608, True)),
                                 ([8388607, 0, 0, 0], (8388607, False)),
                                 ([-8388608, 0, 0, 0], (-8388608, False)),
                                 ([5, -5, 0, 0], (0, False))):
            self.assertEqual(mix_pcm(values), expected)


class AudioReplayTests(fixtures.Checks):
    def check(self, j, f, roms=None):
        return replay(j, f, fixtures.TimelineTests.roms(), roms or audio_roms())

    def test_silent_and_note_stage_positive(self):
        for note in (False, True):
            result = self.check(*audio_fixture(note))
            self.assertEqual(result["comparisons"]["pcm_channel_comparisons"], 2)
            self.assertTrue(result["audio_math_replayed"])
            self.assertFalse(result["complete_audio_golden"])

    def test_envelope_register_and_terminal_lane_mutations(self):
        for name in ("level_q16", "start_q16", "peak_q16", "sustain_q16", "step_q16_twos33", "elapsed", "envelope"):
            j, f = audio_fixture(True)
            row = next(r for r in j["rows"] if r["tag"] == "STATE" and r["tick"] and r["lane"] == 0)
            row[name] = f"{int(row[name], 16) + 1:0{len(row[name])}x}" if isinstance(row[name], str) else row[name] + 1
            self.rejected(lambda: self.check(j, f), "ENVELOPE_" + name)

    def test_wave_rom_one_word_and_coherent_pcm_chain(self):
        j, f = audio_fixture(True)
        roms = audio_roms()
        roms[1][note_fcw(60) >> 24] ^= 1
        self.rejected(lambda: self.check(j, f, roms), "H_WAVETABLE")
        j, f = audio_fixture(True)
        next(r for r in f["rows"] if r["tag"] == "H")["values"][2] ^= 1
        self.rejected(lambda: self.check(j, f), "H_WAVETABLE")
        j, f = audio_fixture(True)
        next(r for r in f["rows"] if r["tag"] == "H")["values"][3] ^= 1
        self.rejected(lambda: self.check(j, f), "H_ENVELOPE")
        j, f = audio_fixture(True)
        m = next(r for r in f["rows"] if r["tag"] == "M")
        m["values"][1] += 1
        next(r for r in j["rows"] if r["tag"] == "COMMIT")["pcm_left"] += 1
        self.rejected(lambda: self.check(j, f), "M_PCM_MATH")

    def test_gain_rom_mutation_and_coherent_wrong_envelope_chain(self):
        j, f = audio_fixture(True)
        roms = audio_roms()
        roms[0][256] += 1
        self.rejected(lambda: self.check(j, f, roms), "ENVELOPE_peak_q16")
        j, f = audio_fixture(True)
        h = next(r for r in f["rows"] if r["tag"] == "H")
        env = h["values"][3] + 1
        h["values"][3] = env
        wave = signed(h["values"][2] & 65535, 16)
        pcm = ((wave * env) // 32768) * 256
        next(r for r in f["rows"] if r["tag"] == "M")["values"][1:3] = [pcm & 0xffffff] * 2
        commit = next(r for r in j["rows"] if r["tag"] == "COMMIT")
        commit["pcm_left"] = commit["pcm_right"] = pcm
        self.rejected(lambda: self.check(j, f), "H_ENVELOPE")

    def test_missing_wave_rom_is_not_acceptance(self):
        j, f = audio_fixture(False)
        roms = audio_roms()
        roms[1] = []
        self.rejected(lambda: self.check(j, f, roms), "WAVE_ROM_SHAPE")
