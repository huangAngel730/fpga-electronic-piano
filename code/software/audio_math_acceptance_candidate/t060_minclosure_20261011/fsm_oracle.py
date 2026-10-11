"""Independent pre-NBA H calendar, limited to the two minclosure fixtures.

Only reset/event/frame/consumer-enable inputs enter this model. DUT phase,
identity, envelope, FCW and PCM are comparisons, never scheduling inputs.
Existing integer math/router definitions are reused unchanged, not extended.
"""
from copy import deepcopy

from dds_model import PianoDDS, pitch_mod, signed
from envelope_model import Envelope, mix_pcm, voice_pcm
from router_model import Router, fields, packed


PHASE = dict(IDLE=0, WAIT_DISPATCH=1, SETTLE=2, CAPTURE=3,
             WAIT_CONTROL=4, ADVANCE=5, SNAPSHOT=6, HOLD=7, DRAIN=8)
ROUTER_STATE = dict(IDLE=0, ALLOC_SEND=1, ALLOC_APPLY=2, CTRL_ON=3,
                    CTRL_OFF=4, PEDAL=5, PANIC=6, SCAN=7, RELEASE_SEND=8,
                    RELEASE_APPLY=9, ACK=10, RETIRE=11, IGNORE=12)


def require(ok, diagnostic):
    if not ok:
        raise ValueError(diagnostic)


def event_word(kind, velocity=0, control=0, value=0):
    """One fixed source1/channel0/A4 identity; no new public event encoding."""
    return ((kind << 61) | (1 << 57) | (69 << 46) | (velocity << 36)
            | (control << 18) | (value << 6))


class Oracle:
    def __init__(self, roms):
        self.roms = roms
        self.cycle = self.epoch = 0
        self.was_reset = False
        self.reset()

    def reset(self):
        self.router = Router()
        self.env = [Envelope(self.roms['velocity_gain_rom.mem']) for _ in range(4)]
        self.dds = [PianoDDS() for _ in range(4)]
        self.wave = [signed(self.roms['piano_band_4x256_8191.mem'][768], 16)] * 4
        self.lfo = [0] * 4
        self.phase, self.delay, self.pending_id = 'IDLE', 0, 0
        self.resume = False
        self.ctrl_left = 0
        self.ctrl_valid = False
        self.math_left = 0
        self.math_valid = self.math_cancelled = False
        self.frozen = None
        self.computed = [0] * 4
        self.math_fcw = [0] * 4
        self.bank_valid, self.bank_id = False, 0
        self.bank_wave = [0] * 4
        self.bank_env = [0] * 4
        self.bank_mask = 0
        self.req, self.req_id = False, 0
        self.window = self.request_active = False
        self.pcm_valid = self.pending_valid = False
        self.pcm_id = self.pcm = self.pending_pcm = self.held_pcm = 0

    def edge(self, *, rst_n=1, event_valid=0, event=0, frame=0, consumer=1):
        for name, value in dict(rst_n=rst_n, event_valid=event_valid,
                                frame=frame, consumer=consumer).items():
            require(type(value) is int and value in (0, 1), 'INPUT_FLAG:' + name)
        require(type(event) is int and 0 <= event < 1 << 64, 'INPUT_EVENT')
        self.cycle += 1
        if not rst_n:
            if not self.was_reset:
                self.epoch += 1
            self.was_reset = True
            self.reset()
            return None
        self.was_reset = False
        r, phase = self.router, self.phase
        slots = deepcopy(r.slots)
        on, off, busy = r.on, r.off, r.busy()
        owner = phase == 'IDLE' and not self.req and not frame and not self.bank_valid
        event_ready = (r.state == 'IDLE' and not r.pending and r.retire_lane() is None
                       and owner and self.ctrl_left == 0)
        if event_valid:
            e = fields(event)
            require(e['source'] == 1 and e['channel'] == 0 and e['note'] == 69
                    and ((e['type'] in (0, 1, 5) and e['control'] == e['value'] == 0)
                         or (e['type'] == 4 and e['control'] == 6)),
                    'MINCLOSURE_UNSUPPORTED_EVENT')
            require(event_ready, 'MINCLOSURE_EVENT_NOT_ACCEPTED')
        live = self.frozen is not None and all(
            a[k] == b[k] for a, b in zip(slots, self.frozen)
            for k in ('occupied', 'source', 'channel', 'generation'))
        tick = phase == 'ADVANCE' and live and not frame
        ctrl_snap_ready = not frame and ((phase == 'WAIT_CONTROL' and self.math_left == 0
                                         and (not self.math_valid or phase == 'WAIT_CONTROL'))
                                        or phase == 'DRAIN')
        math_ready = not frame and phase in ('WAIT_CONTROL', 'DRAIN')
        math_req_ready = not frame and self.math_left == 0 and (not self.math_valid or math_ready)
        ctrl_req_ready = self.ctrl_left == 0 and (not self.ctrl_valid or ctrl_snap_ready)
        ctrl_accept = not frame and phase == 'CAPTURE' and math_req_ready and ctrl_req_ready
        math_accept = not frame and phase == 'WAIT_CONTROL' and self.ctrl_valid and math_req_ready
        math_take = self.math_valid and math_ready
        bank_ready = (self.window and not frame and not self.pcm_valid
                      and self.bank_id == self.req_id and bool(consumer))
        bank_take = self.bank_valid and bank_ready
        pcm_ready = (self.request_active and not frame and not self.pending_valid
                     and self.pcm_id == self.req_id)
        commit = self.pcm_valid and pcm_ready
        done = sum((1 << i) for i, (s, env) in enumerate(zip(slots, self.env))
                   if s['occupied'] and s['releasing'] and env.state == 0 and not on & (1 << i))
        row = dict(tag='EDGE', cycle=self.cycle, epoch=self.epoch,
                   event_valid=event_valid, event=event, event_ready=int(event_ready),
                   frame=frame, consumer=consumer, sample_req=int(self.req), request_id=self.req_id,
                   phase=PHASE[phase], router_state=ROUTER_STATE[r.state],
                   tick=int(tick), on=on, off=off, occupied=packed([int(s['occupied']) for s in slots], 1),
                   releasing=packed([int(s['releasing']) for s in slots], 1),
                   keys=packed([int(s['key']) for s in slots], 1),
                   deferred=packed([int(s['deferred']) for s in slots], 1),
                   pedal=int((1, 0) in r.pedals),
                   sources=packed([s['source'] for s in slots], 4),
                   channels=packed([s['channel'] for s in slots], 4),
                   notes=packed([s['note'] for s in slots], 8),
                   generations=packed([s['generation'] for s in slots], 32),
                   velocity=packed([s['velocity'] for s in slots], 10),
                   release_done=done, ctrl_accept=int(ctrl_accept), math_accept=int(math_accept),
                   bank_valid=int(self.bank_valid), bank_ready=int(bank_ready), bank_id=self.bank_id,
                   bank_waves=packed([w & 65535 for w in self.bank_wave], 16),
                   bank_envelopes=packed(self.bank_env, 16), bank_occupied=self.bank_mask,
                   pcm_valid=int(self.pcm_valid), pcm_ready=int(pcm_ready), pcm_id=self.pcm_id,
                   pcm_left=self.pcm, pcm_right=self.pcm, commit=int(commit),
                   pending_valid=int(self.pending_valid),
                   play_left=self.pending_pcm if self.pending_valid else self.held_pcm,
                   play_right=self.pending_pcm if self.pending_valid else self.held_pcm,
                   dds_phase=packed([d.phase for d in self.dds], 32),
                   lfo_phase=packed(self.lfo, 32), env_state=packed([e.state for e in self.env], 4),
                   env_level=packed([e.level for e in self.env], 32))
        # All state transitions below use the above pre-edge values.
        next_wave = [signed(self.roms['piano_band_4x256_8191.mem'][(d.active_table << 8)
                                                                       | (d.phase >> 24)], 16)
                     for d in self.dds]
        snap_env = [e.level >> 16 for e in self.env]
        for i, (s, env, dds) in enumerate(zip(slots, self.env, self.dds)):
            fcw = s['fcw'] if phase in ('IDLE', 'WAIT_DISPATCH', 'SETTLE', 'CAPTURE') else self.computed[i]
            env.edge(bool(tick), bool(on & (1 << i)), bool(off & (1 << i)), s['velocity'])
            dds.edge(fcw, s['velocity'], bool(tick), bool(on & (1 << i)))
            if on & (1 << i):
                self.lfo[i] = 0
        r.edge(event if event_valid else None, done, bool(owner))
        if frame:
            self.phase, self.bank_valid, self.resume = 'DRAIN', False, False
        elif phase == 'IDLE' and self.req:
            self.pending_id, self.phase = self.req_id, 'WAIT_DISPATCH'
        elif phase == 'WAIT_DISPATCH' and not busy and not on and not off:
            self.delay, self.phase = 6, 'SETTLE'
        elif phase == 'SETTLE':
            if self.delay == 0:
                self.phase = 'CAPTURE'
            else:
                self.delay -= 1
        elif ctrl_accept:
            self.frozen, self.phase = slots, 'WAIT_CONTROL'
        elif phase == 'WAIT_CONTROL' and math_take:
            require(live, 'MINCLOSURE_LIVE_IDENTITY_CHANGED')
            self.computed, self.phase = self.math_fcw[:], 'ADVANCE'
        elif phase == 'ADVANCE':
            self.delay, self.phase = (4, 'SNAPSHOT') if live else (0, 'DRAIN')
        elif phase == 'SNAPSHOT':
            if self.delay == 0:
                self.bank_id, self.bank_env, self.bank_wave = self.pending_id, snap_env, self.wave[:]
                self.bank_mask = packed([int(s['occupied']) for s in self.frozen], 1)
                self.bank_valid, self.phase = True, 'HOLD'
            else:
                self.delay -= 1
        elif phase == 'HOLD' and bank_take:
            self.bank_valid, self.phase = False, 'IDLE'
        elif phase == 'DRAIN':
            resume = self.resume or self.req
            if self.req:
                self.pending_id, self.resume = self.req_id, True
            if ctrl_req_ready and not self.ctrl_valid and math_req_ready and not self.math_valid:
                self.phase, self.resume = ('WAIT_DISPATCH' if resume else 'IDLE'), False
        if self.ctrl_valid and ctrl_snap_ready:
            self.ctrl_valid = False
        if ctrl_accept:
            self.ctrl_left, self.ctrl_valid = 4, False
        elif self.ctrl_left:
            self.ctrl_left -= 1
            if self.ctrl_left == 0:
                self.ctrl_valid = True
        if math_take or frame:
            self.math_valid = False
        if frame and self.math_left:
            self.math_cancelled = True
        if math_accept:
            self.math_left, self.math_cancelled = 7, False
            self.math_fcw = []
            for i, s in enumerate(self.frozen):
                phase_now = 0 if on & (1 << i) else self.lfo[i]
                self.math_fcw.append(pitch_mod(s['fcw'], 0, 0, 2, phase_now,
                                             self.roms['oct_ratio_q16.mem'],
                                             self.roms['sub_ratio_q16.mem'],
                                             self.roms['lfo_sine_q15.mem']) if s['occupied'] else s['fcw'])
                if s['occupied']:
                    self.lfo[i] = (phase_now + 447392) & 0xffffffff
        elif self.math_left:
            self.math_left -= 1
            if not self.math_left and not self.math_cancelled and not frame:
                self.math_valid = True
        if frame:
            self.window, self.pcm_valid = True, False
        elif commit:
            self.pcm_valid = False
        elif bank_take:
            self.window, self.pcm_valid, self.pcm_id = False, True, row['bank_id']
            voices = [voice_pcm(signed(row['bank_waves'] >> (16 * i), 16),
                                (row['bank_envelopes'] >> (16 * i)) & 65535)
                      if row['bank_occupied'] & (1 << i) else 0 for i in range(4)]
            self.pcm = mix_pcm(voices)[0]
        self.req = bool(frame)
        if frame:
            self.req_id = (self.req_id + 1) & 0xffffffff
            self.request_active = True
            if self.pending_valid:
                self.held_pcm, self.pending_valid = self.pending_pcm, False
        elif commit:
            self.pending_pcm, self.pending_valid, self.request_active = row['pcm_left'], True, False
        self.wave = next_wave
        return row

    def idle_skip(self, target):
        """Skip only quiescent fixed-point edges; otherwise execute each clock."""
        while self.cycle + 1 < target:
            quiet = (self.phase == 'IDLE' and not self.router.busy() and not self.req
                     and not (self.router.on | self.router.off) and not self.bank_valid
                     and not self.pcm_valid and not self.ctrl_left and not self.ctrl_valid
                     and not self.math_left and not self.math_valid)
            before = [e.registers() for e in self.env]
            self.edge()
            if quiet and before == [e.registers() for e in self.env] and not any(
                    s['occupied'] and s['releasing'] and e.state == 0
                    for s, e in zip(self.router.slots, self.env)):
                skip = target - self.cycle - 1
                self.cycle += skip
                for env in self.env:
                    env.cycle += skip


def observable(row, trace):
    return bool(trace or row['event_valid'] or row['frame'] or row['sample_req']
                or row['tick'] or row['bank_valid'] or row['pcm_valid'] or row['on']
                or row['off'] or row['release_done'] or row['router_state'] == 11)
