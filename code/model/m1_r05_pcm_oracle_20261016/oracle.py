"""N=4 R06 arithmetic reference for an independently supplied settled calendar.

This is neither a board scheduler nor a capture parser. Event application,
every DSP advance and every effect acceptance are explicit independent inputs.
The old signed models are imported byte-for-byte; their test mains are not run.
"""
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
PCM_MIN, PCM_MAX = -8388608, 8388607


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('RANGE:' + name)
    return value


def verify_dependencies(directory=HERE):
    manifest = json.loads((directory / 'DEPENDENCIES.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        path = directory / row['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('FROZEN_DEPENDENCY_MISSING_OR_CHANGED:' + row['path'])
    return manifest


DEPENDENCIES = verify_dependencies()


def load_frozen(name):
    path = HERE / 'frozen' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dds = load_frozen('dds_model')
adsr = load_frozen('envelope_model')
allocator = load_frozen('allocator_oracle')
delay = load_frozen('delay_effect_fixed')


def rom(name, signed=False):
    # Verilog readmemh accepts // comments; retain the original ROM bytes and
    # ignore only their lexical comments when decoding the words.
    text = (HERE / 'frozen/rom' / name).read_text(encoding='ascii')
    words = ' '.join(line.split('//', 1)[0] for line in text.splitlines()).split()
    values = [int(word, 16) for word in words]
    if len(values) != 1024 or any(not 0 <= value <= 65535 for value in values):
        raise ValueError('ROM_SHAPE_OR_RANGE:' + name)
    return [dds.signed(value, 16) for value in values] if signed else values


PIANO = rom('piano_band_4x256_8191.mem', True)
TRIANGLE = rom('triangle_wavetable.hex', True)
VELOCITY = rom('velocity_gain_rom.mem')


def mixed(voices):
    if len(voices) != 4 or any(type(x) is not int for x in voices):
        raise ValueError('FOUR_INTEGER_VOICES_REQUIRED')
    return adsr.mix_pcm(voices)


@dataclass
class Lane:
    envelope: object
    piano: object
    fcw: int = 0
    velocity: int = 0
    timbre: int = 0
    generation: int = 0


class Reference:
    """Settled-event profile: no CC64, panic, PB/mod or frontend timing guess.

    Calls are ordered by cycle; no event/config during advance..advance+5.
    A sample advances every lane, including empty slots. An accepted effect
    input updates history even when that request is subsequently unpublished.
    """
    def __init__(self):
        self.epoch = -1
        self.reset(0)

    def reset(self, cycle):
        integer(cycle, 0, 2**63 - 1, 'reset_cycle')
        self.epoch += 1
        self.last_action = cycle
        self.last_advance = cycle
        self.event_count = 0
        self.requests = set()
        self.programs = {}
        self.slots = allocator.Oracle()
        self.lanes = [Lane(adsr.Envelope(VELOCITY), dds.PianoDDS()) for _ in range(4)]
        for lane in self.lanes:
            lane.envelope.reset(cycle)
        self.effects = [delay.DelayEffectFixed(1024), delay.DelayEffectFixed(1024)]
        self.config = (False, 1, 32767, 0, 0)

    def order(self, cycle):
        integer(cycle, self.last_action + 1, 2**63 - 1, 'ordered_cycle')

    def config_accept(self, cycle, enable, length, dry, wet, feedback):
        self.order(cycle)
        if type(enable) is not bool:
            raise ValueError('CONFIG_ENABLE_BOOL')
        integer(length, 0, 1023, 'delay_length')
        for name, gain in [('dry', dry), ('wet', wet), ('feedback', feedback)]:
            integer(gain, 0, 32767, name)
        if (enable, length) != self.config[:2]:
            for effect in self.effects:
                effect.reset()
        self.config = enable, length, dry, wet, feedback
        self.last_action = cycle

    def retire_finished(self, cycle):
        done = 0
        for index, lane in enumerate(self.lanes):
            if cycle >= lane.envelope.cycle:
                lane.envelope.quiet_until(cycle + 1)
            slot = self.slots.slots[index]
            if slot and slot[3] == 'release' and lane.envelope.snapshot()['public_state'] == 0:
                done |= 1 << index
        if done:
            self.slots.step(1, 0, 0, 0, 0, 0, done)
        return done

    def event(self, cycle, kind, source=1, channel=0, note=60, velocity=0, program=0):
        self.order(cycle)
        integer(source, 0, 15, 'source')
        integer(channel, 0, 15, 'channel')
        self.retire_finished(cycle - 1)
        if kind == 'program':
            integer(program, 0, 4095, 'program')
            if program <= 1:
                self.programs[source, channel] = program
            decision = dict(decision='program' if program <= 1 else 'ignored_program')
        elif kind in ('note_on', 'note_off'):
            integer(note, 0, 127, 'note')
            integer(velocity, 0, 1023, 'velocity')
            on = kind == 'note_on' and velocity != 0
            off = not on
            on_valid, slot_on, off_valid, slot_off, label = self.slots.step(
                1, on, off, source, channel, note, 0)
            target = slot_on if on_valid else slot_off if off_valid else None
            if target is not None:
                lane = self.lanes[target]
                lane.envelope.quiet_until(cycle)
                lane.envelope.edge(on=bool(on_valid), off=bool(off_valid), velocity=velocity)
                if on_valid:
                    lane.fcw = dds.note_fcw(note)
                    lane.velocity = velocity
                    lane.timbre = self.programs.get((source, channel), 0)
                    lane.generation = (lane.generation + 1) & 0xffffffff
                    lane.piano.edge(lane.fcw, velocity=velocity, note_on=True)
            decision = dict(decision=label if on_valid else 'release' if off_valid else 'ignored_off',
                            lane=target, generation=self.lanes[target].generation if target is not None else None)
        else:
            raise ValueError('UNSUPPORTED_EVENT:' + kind)
        self.event_count += 1
        self.last_action = cycle
        return dict(epoch=self.epoch, apply_cycle=cycle, kind=kind, source=source,
                    channel=channel, note=note, velocity10=velocity, program=program, **decision)

    def sample(self, advance_cycle, request_id, effect_accepted=True, publish=True,
               postprocess_accept_cycle=None):
        self.order(advance_cycle)
        integer(request_id, 0, 0xffffffff, 'request_id')
        if request_id in self.requests:
            raise ValueError('DUPLICATE_REQUEST_IN_EPOCH')
        if type(effect_accepted) is not bool or type(publish) is not bool:
            raise ValueError('SAMPLE_FLAGS_BOOL')
        if publish and not effect_accepted:
            raise ValueError('PUBLISH_WITHOUT_EFFECT_ACCEPT')
        # The settled profile deliberately excludes same-edge event/tick and
        # unresolved frontend/ADSR setup. It does not promise a board deadline.
        if advance_cycle - self.last_action < 8:
            raise ValueError('SETTLED_PROFILE_REQUIRES_8_QUIET_CLOCKS')
        post = advance_cycle + 7 if postprocess_accept_cycle is None else postprocess_accept_cycle
        integer(post, advance_cycle + 7, 2**63 - 1, 'postprocess_accept_cycle')
        retired = self.retire_finished(advance_cycle - 1)
        lanes, voices = [], []
        for index, lane in enumerate(self.lanes):
            env = lane.envelope
            env.quiet_until(advance_cycle)
            env.edge(tick=True)
            phase_before = lane.piano.phase
            lane.piano.edge(lane.fcw, velocity=lane.velocity, tick=True)
            # E+5 bank samples pre-NBA. After quiet_until(E+5), the envelope
            # contains all updates through E+4, exactly the value being read.
            env.quiet_until(advance_cycle + 5)
            state = env.snapshot()
            address = phase_before >> 22 if lane.timbre else (lane.piano.active_table << 8) | (lane.piano.phase >> 24)
            wave = TRIANGLE[address] if lane.timbre else PIANO[address]
            identity = self.slots.slots[index]
            voice = adsr.voice_pcm(wave, state['envelope']) if identity else 0
            voices.append(voice)
            lanes.append(dict(lane=index, identity=list(identity) if identity else None,
                              generation=lane.generation, timbre=lane.timbre,
                              velocity10=lane.velocity, fcw=lane.fcw,
                              frequency_hz=lane.fcw * 48000 / 2**32,
                              phase_before=phase_before, phase_after=lane.piano.phase,
                              piano_table=lane.piano.active_table, rom_address=address,
                              wave16=wave, level_q16=state['level_q16'], env_q15=state['envelope'],
                              adsr_state=state['public_state'], voice_pcm24=voice))
        value, upstream_clip = mixed(voices)
        result, output_flags, feedback_flags = [], [], []
        enabled, length, dry, wet, feedback = self.config
        for effect in self.effects:
            if effect_accepted and enabled:
                delayed = effect.buffer[(effect.wr_ptr - length) % effect.depth]
                raw = (value * dry >> 15) + (delayed * wet >> 15)
                fbraw = value + (delayed * feedback >> 15)
                result.append(effect.process(value, length, dry, wet, feedback))
                output_flags.append(not PCM_MIN <= raw <= PCM_MAX)
                feedback_flags.append(not PCM_MIN <= fbraw <= PCM_MAX)
            else:
                result.append(value if effect_accepted else None)
                output_flags.append(False if effect_accepted else None)
                feedback_flags.append(False if effect_accepted else None)
        self.requests.add(request_id)
        self.last_action = post if effect_accepted else advance_cycle + 5
        self.last_advance = advance_cycle
        return dict(epoch=self.epoch, request_id=request_id, advance_cycle=advance_cycle,
                    snapshot_cycle=advance_cycle + 5,
                    postprocess_accept_cycle=post if effect_accepted else None,
                    calendar_kind='SYNTHETIC_SETTLED_EVENT', retired_mask=retired,
                    lanes=lanes, mixed_left=value, mixed_right=value, upstream_clip=upstream_clip,
                    effect_accepted=effect_accepted, expected_publish=publish,
                    left=result[0], right=result[1], effect_clip=output_flags,
                    feedback_clip=feedback_flags,
                    clipped=[upstream_clip or x if x is not None else None for x in output_flags])
