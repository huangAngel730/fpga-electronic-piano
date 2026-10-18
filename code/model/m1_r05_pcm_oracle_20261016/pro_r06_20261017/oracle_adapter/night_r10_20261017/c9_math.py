"""C9 clocked arithmetic adapter, using unchanged signed M1 primitives.

Public rows supply *when* an action happened. Independent input-plan values
supply *what* it means. No observed wave, envelope, phase or PCM is a model input.
This is a bounded Piano/Triangle + ordinary NoteOff + stereo-delay profile.
"""
from collections import Counter
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
REFERENCE_ROOT = HERE.parents[2]
PROFILE = 'C9_PIANO_TRIANGLE_NOTES_DELAY_CLOCKED_V1'
MAX_ID = (1 << 32) - 1
PCM_MIN, PCM_MAX = -(1 << 23), (1 << 23) - 1


class MathIssue(ValueError):
    def __init__(self, code, where='', status='CONTRACT_REJECTED', expected=None, actual=None):
        super().__init__(code + (':' + where if where else ''))
        self.code, self.where, self.status = code, where, status
        self.expected, self.actual = expected, actual


def reject(code, where='', status='CONTRACT_REJECTED'):
    raise MathIssue(code, where, status)


def integer(value, lo, hi, where):
    if type(value) is not int or not lo <= value <= hi:
        reject('INTEGER_RANGE', where)
    return value


def known(row, key, bits=1, signed=False):
    value = row[key]
    if type(value) is str and len(value) <= bits and value and set(value) <= {'0', '1'}:
        value = int(value, 2)
        if signed and value & (1 << (bits - 1)):
            value -= 1 << bits
    if value is None or type(value) is str:
        reject('UNKNOWN_REQUIRED_FIELD', key, 'PENDING_INPUT')
    return integer(value, -(1 << (bits-1)) if signed else 0,
                   (1 << (bits-1))-1 if signed else (1 << bits)-1, key)


def decode_event(word):
    integer(word, 0, (1 << 64)-1, 'event_data')
    return dict(type=word >> 61, source=(word >> 57) & 15,
                channel=(word >> 53) & 15, note=(word >> 46) & 127,
                velocity=(word >> 36) & 1023, expression=(word >> 26) & 1023,
                control=(word >> 18) & 255, value=(word >> 6) & 4095,
                reserved=word & 63)


def load_reference():
    # Identity checks in c9_inputs.verify_bindings run before this import.
    name = '_m1_r10_unchanged_reference'
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REFERENCE_ROOT/'oracle.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class Lane:
    envelope: object
    piano: object
    source: int = 0
    channel: int = 0
    note: int = 0
    generation: int = 0
    velocity: int = 0
    fcw: int = 0
    timbre: int = 0
    on_allocation_cycle: int = -1
    note_consumed: bool = True
    release_cycle: int = -1


class ClockedMath:
    """Process all public posedges; slot observations only check model state."""
    def __init__(self, plan, *, diagnostic_limit=64):
        self.ref = load_reference()
        self.plan = plan
        self.limit = diagnostic_limit
        self.counts = Counter()
        self.compared = []
        self.actions = []
        self.epoch_receipts = []
        self.first_difference = None
        self.cycle, self.epoch = -1, -1
        self.reset(-1, 0)

    def reset(self, cycle, epoch):
        self.epoch = epoch
        self.slots = self.ref.allocator.Oracle()
        self.lanes = [Lane(self.ref.adsr.Envelope(self.ref.VELOCITY),
                           self.ref.dds.PianoDDS()) for _ in range(4)]
        for lane in self.lanes:
            lane.envelope.reset(cycle)
        self.programs = {}
        self.accepted = {}
        self.router_next = 0
        self.event_cursor = 0
        self.config_cursor = 0
        self.pending_off = {}
        self.tokens = {}
        self.next_off_mask = 0
        self.next_off_cycle = -1
        self.done_seen = {}
        self.effects = [self.ref.delay.DelayEffectFixed(1024) for _ in range(2)]
        self.config = (False, 1, 32767, 0, 0)
        self.effect_busy_until = -1
        self.effect_last_id = None
        self.events = [e for e in self.plan['events'] if e.get('epoch', 0) == epoch]
        self.config_events = [e for e in self.plan.get('config_events', []) if e.get('epoch', 0) == epoch]

    def check(self, field, expected, actual, row, layer, event=None):
        if expected != actual:
            difference = dict(cycle=row['cycle'], epoch=row['epoch'], layer=layer,
                              field=field, expected=expected, actual=actual,
                              event=event, request_id=row.get('advance_frame_req_id'))
            self.first_difference = difference
            raise MathIssue('MATH_OR_IDENTITY_MISMATCH', field, 'FAIL', expected, actual)

    def state_check(self, row):
        occupied = sum(1 << i for i, s in enumerate(self.slots.slots) if s is not None)
        releasing = sum(1 << i for i, s in enumerate(self.slots.slots) if s is not None and s[3] == 'release')
        self.check('occupied_mask', occupied, known(row, 'occupied_mask', 4), row, 'lane_identity')
        self.check('releasing_mask', releasing, known(row, 'releasing_mask', 4), row, 'lane_identity')
        for name, attr, bits in [('slot_sources','source',4), ('slot_channels','channel',4),
                                 ('slot_notes','note',8), ('slot_generations','generation',32)]:
            expected = sum(getattr(lane,attr) << (i*bits) for i,lane in enumerate(self.lanes))
            self.check(name, expected, known(row, name, bits*4), row, 'lane_identity')
        for i,lane in enumerate(self.lanes):
            slot=self.slots.slots[i]
            if slot is not None and slot[3]=='release' and lane.envelope.snapshot()['public_state']==0:
                self.done_seen.setdefault(i,row['cycle'])

    def accept_event(self, row):
        if not (known(row,'event_valid') and known(row,'event_ready')):
            return
        if self.event_cursor >= len(self.events):
            reject('UNPLANNED_EVENT_ACCEPT', str(row['cycle']))
        event = self.events[self.event_cursor]
        word = int(event['expected_event_hex'], 16)
        window = event['arrival_window']
        if not window['min_cycle'] <= row['cycle'] <= window['max_cycle']:
            reject('EVENT_OUTSIDE_INDEPENDENT_WINDOW', str(event['event_seq']))
        self.check('event_data', word, known(row,'event_data',64), row, 'independent_event', event['event_seq'])
        parsed = decode_event(word)
        if parsed['reserved']:
            reject('RESERVED_EVENT_BITS', str(event['event_seq']))
        if parsed['type'] not in (0,1) and not (parsed['type']==4 and parsed['control']==5 and parsed['value']<=1):
            reject('UNSUPPORTED_CONTROL_PROFILE', str(parsed), 'UNSUPPORTED_PROFILE')
        if self.router_next > MAX_ID:
            reject('ROUTER_SEQUENCE_WRAP_UNSUPPORTED', status='UNSUPPORTED_PROFILE')
        self.accepted[self.router_next] = dict(word=word, event=parsed,
            plan_seq=event['event_seq'], accepted_cycle=row['cycle'], stages=set())
        self.router_next += 1
        self.event_cursor += 1
        self.counts['accepted_events'] += 1

    def application(self, row):
        valid = known(row,'apply_valid')
        kind = known(row,'apply_kind',4)
        on, off = known(row,'note_on_mask',4), known(row,'note_off_mask',4)
        retire = known(row,'retire_mask',4)
        if not valid:
            self.check('kind_without_apply', 0, kind, row,'apply')
            self.check('orphan_note_pulses', 0, on|off|retire, row,'apply')
            return 0, 0, None
        if kind not in range(1,9):
            reject('UNKNOWN_APPLY_KIND', str(kind), 'UNSUPPORTED_PROFILE')
        mask = known(row,'apply_mask',4)
        seq_valid = known(row,'router_apply_seq_valid')
        seq = known(row,'router_apply_seq',32)
        word = known(row,'apply_data',64)
        event = None
        if kind in (3,4,8):
            if (seq_valid,seq,word)!=(0,0,0):
                reject('INVALID_CAUSE_SENTINEL_REQUIRED', str(row['cycle']))
        else:
            if seq_valid != 1 or seq not in self.accepted:
                reject('MISSING_TRUSTED_APPLY_CAUSE', str(row['cycle']), 'PENDING_INPUT')
            event = self.accepted[seq]
            self.check('apply_data', event['word'], word, row,'apply',event['plan_seq'])
            if kind in event['stages']:
                reject('DUPLICATE_APPLY_STAGE', f'{seq}:{kind}')
            if event['accepted_cycle'] >= row['cycle']:
                reject('APPLY_BEFORE_ACCEPT', str(row['cycle']))
            event['stages'].add(kind)
        self.counts['apply_kind_'+str(kind)] += 1
        self.actions.append(dict(cycle=row['cycle'], epoch=row['epoch'], kind=kind,
                                 plan_seq=event['plan_seq'] if event else None,
                                 router_seq=seq if seq_valid else None, mask=mask))
        if kind in (1,2,3,4,8) and (mask == 0 or mask & (mask-1)):
            reject('ONE_LANE_ACTION_REQUIRED', str(mask))
        lane_id = mask.bit_length()-1
        if kind == 1:
            ev = event['event']
            if ev['type'] != 0 or ev['velocity'] == 0:
                reject('ALLOCATION_NOT_NOTE_ON')
            _, lane, _, _, allocation = self.slots.step(1,1,0,ev['source'],ev['channel'],ev['note'],0)
            self.check('allocation_mask', 1<<lane, mask, row,'allocator',event['plan_seq'])
            l = self.lanes[lane]
            l.source,l.channel,l.note = ev['source'],ev['channel'],ev['note']
            l.velocity,l.fcw = ev['velocity'],self.ref.dds.note_fcw(ev['note'])
            l.timbre = self.programs.get((ev['source'],ev['channel']),0)
            l.generation = (l.generation+1)&MAX_ID
            l.on_allocation_cycle,l.note_consumed = row['cycle'],False
            event['lane'],event['generation'],event['allocation'] = lane,l.generation,allocation
            self.pending_off.pop(lane,None)
            self.done_seen.pop(lane,None)
        elif kind == 2:
            if 1 not in event['stages'] or event.get('lane') != lane_id:
                reject('NOTE_ON_WITHOUT_ALLOCATION')
            l = self.lanes[lane_id]
            if l.note_consumed or row['cycle'] < l.on_allocation_cycle+2 or l.generation!=event['generation']:
                reject('NOTE_ON_CONSUME_TIMING_OR_GENERATION')
            l.note_consumed = True
            self.check('note_on_mask',mask,on,row,'note_on',event['plan_seq'])
        elif kind == 3:
            if lane_id not in self.pending_off or self.slots.slots[lane_id] is None:
                reject('RELEASE_WITHOUT_INDEPENDENT_NOTE_OFF')
            pending = self.pending_off[lane_id]
            if pending['generation'] != self.lanes[lane_id].generation:
                reject('STALE_RELEASE_GENERATION')
            slot = self.slots.slots[lane_id]
            self.slots.step(1,0,1,*slot[:3],0)
            self.lanes[lane_id].release_cycle = row['cycle']
            self.next_off_mask,self.next_off_cycle = mask,row['cycle']+1
            self.check('note_off_not_yet_consumed',0,off,row,'note_off')
        elif kind == 4:
            if row['cycle'] != self.next_off_cycle or mask != self.next_off_mask:
                reject('NOTE_OFF_CONSUME_TIMING')
            self.check('note_off_mask',mask,off,row,'note_off')
            self.pending_off.pop(lane_id,None)
            self.next_off_mask,self.next_off_cycle = 0,-1
        elif kind == 5:
            ev = event['event']
            if (ev['type'],ev['control'])!=(4,5) or ev['value']>1 or mask:
                reject('PROGRAM_ACTION_MISMATCH')
            self.programs[ev['source'],ev['channel']] = ev['value']
        elif kind == 6:
            ev = event['event']
            if ev['type'] not in (0,1) or (ev['type']==0 and ev['velocity']!=0):
                reject('UNSUPPORTED_CONTROL_ACTION', status='UNSUPPORTED_PROFILE')
            matching = [i for i,s in enumerate(self.slots.slots) if s is not None and s[:3]==(ev['source'],ev['channel'],ev['note'])]
            if not matching:
                reject('OFF_CONTROL_WITHOUT_SLOT')
            self.check('off_control_mask',1<<matching[0],mask,row,'note_off',event['plan_seq'])
            if self.slots.slots[matching[0]][3] == 'active':
                self.pending_off[matching[0]] = dict(generation=self.lanes[matching[0]].generation,
                    plan_seq=event['plan_seq'])
        elif kind == 7:
            ev = event['event']
            matching = any(s is not None and s[:3]==(ev['source'],ev['channel'],ev['note']) for s in self.slots.slots)
            if ev['type'] not in (0,1) or (ev['type']==0 and ev['velocity']) or matching or mask:
                reject('UNEXPECTED_IGNORED_EVENT')
        elif kind == 8:
            slot = self.slots.slots[lane_id]
            if slot is None or slot[3]!='release' or self.lanes[lane_id].envelope.snapshot()['public_state']!=0:
                reject('RETIRE_BEFORE_ENVELOPE_DONE')
            if row['cycle'] < self.done_seen.get(lane_id,row['cycle'])+2:
                reject('RETIRE_BEFORE_ROUTER_PENDING')
            self.check('retire_mask',mask,retire,row,'retire')
            self.slots.step(1,0,0,0,0,0,mask)
            self.done_seen.pop(lane_id,None)
        if kind != 2:
            self.check('unexpected_note_on',0,on,row,'apply')
        if kind != 4:
            self.check('unexpected_note_off',0,off,row,'apply')
        if kind != 8:
            self.check('unexpected_retire',0,retire,row,'apply')
        return on,off,event

    def configuration(self, row):
        take = known(row,'config_take')
        self.check('config_take', known(row,'config_valid') & known(row,'config_ready'), take, row,'config')
        if not take:
            return
        if self.config_cursor >= len(self.config_events):
            reject('UNPLANNED_CONFIG')
        expected = self.config_events[self.config_cursor]
        payload = integer(expected['payload'],0,(1<<62)-1,'plan.config.payload')
        w = expected['arrival_window']
        if not w['min_cycle'] <= row['cycle'] <= w['max_cycle']:
            reject('CONFIG_OUTSIDE_INDEPENDENT_WINDOW')
        self.check('config_payload',payload,known(row,'config_payload',62),row,'config')
        config = (bool(payload>>61), (payload>>45)&65535,
                  (payload>>30)&32767, (payload>>15)&32767, payload&32767)
        if config[1] >= 1024:
            reject('DELAY_LENGTH_UNSUPPORTED',status='UNSUPPORTED_PROFILE')
        if self.effect_locked(row['cycle']):
            reject('CONFIG_DURING_EFFECT_TRANSACTION')
        if config[:2] != self.config[:2]:
            for effect in self.effects:
                effect.reset()
        self.config = config
        self.config_cursor += 1
        self.counts['config_accepts'] += 1

    def take_snapshot(self, row):
        for token in self.tokens.values():
            if token.get('snapshot_cycle') != row['cycle'] or token.get('snapshot') or token.get('cancelled'):
                continue
            voices,lanes = [],[]
            for i,lane in enumerate(self.lanes):
                state = lane.envelope.snapshot()
                value = self.ref.adsr.voice_pcm(token['waves'][i],state['envelope']) if token['occupied']&(1<<i) else 0
                voices.append(value)
                lanes.append(dict(lane=i,wave16=token['waves'][i],envelope=state['envelope'],
                                  level_q16=state['level_q16'],voice_pcm24=value,
                                  generation=lane.generation,note=lane.note))
            pcm,clip = self.ref.adsr.mix_pcm(voices)
            token['snapshot'] = dict(left=pcm,right=pcm,clip_mask=3 if clip else 0,lanes=lanes)
            self.counts['snapshots'] += 1

    def input_effect(self, row):
        if not (known(row,'effect_input_valid') and known(row,'effect_input_ready')):
            return
        req = known(row,'effect_input_id',32)
        token = self.tokens.get(req)
        if token is None or 'snapshot' not in token or token.get('cancelled') or 'effect' in token:
            reject('EFFECT_ACCEPT_WITHOUT_LIVE_SNAPSHOT',str(req))
        if row['cycle'] < token['snapshot_cycle']+2 or self.effect_locked(row['cycle']):
            reject('EFFECT_ACCEPT_PIPELINE_ORDER',str(req))
        if known(row,'frame_tick') or known(row,'config_take'):
            reject('EFFECT_ACCEPT_CONFLICT')
        s = token['snapshot']
        for side in ('left','right'):
            self.check('effect_input_'+side,s[side],known(row,'effect_input_'+side,24,True),row,'mix')
        self.check('effect_input_clip_mask',s['clip_mask'],known(row,'effect_input_clip_mask',2),row,'mix')
        if req == self.effect_last_id:
            reject('DUPLICATE_EFFECT_ID')
        enabled,length,dry,wet,feedback = self.config
        output, effect_mask, feedback_mask = [],0,0
        for i,side in enumerate(('left','right')):
            value = s[side]
            effect = self.effects[i]
            if enabled:
                delayed = effect.buffer[(effect.wr_ptr-length)%1024]
                raw = (value*dry>>15)+(delayed*wet>>15)
                fb = value+(delayed*feedback>>15)
                effect_mask |= int(not PCM_MIN <= raw <= PCM_MAX)<<i
                feedback_mask |= int(not PCM_MIN <= fb <= PCM_MAX)<<i
                output.append(effect.process(value,length,dry,wet,feedback))
            else:
                output.append(value)
        token['effect'] = dict(cycle=row['cycle'], earliest_result=row['cycle']+4,
            left=output[0],right=output[1],upstream_mask=s['clip_mask'],
            effect_mask=effect_mask,feedback_mask=feedback_mask,
            clip_mask=s['clip_mask']|effect_mask,enabled=enabled)
        self.effect_busy_until,self.effect_last_id = row['cycle']+3,req
        self.counts['effect_accepts'] += 1

    def effect_locked(self, cycle):
        if cycle<=self.effect_busy_until:
            return True
        return any('effect' in t and not t.get('cancelled') and
                   (t.get('result_accepted') is None or t['result_accepted']>=cycle)
                   for t in self.tokens.values())

    def outputs(self, row):
        if known(row,'result_valid'):
            req = known(row,'result_id',32)
            token = self.tokens.get(req)
            if token is None or 'effect' not in token or token.get('cancelled'):
                reject('RESULT_WITHOUT_ACCEPTED_EFFECT',str(req))
            exp = token['effect']
            if row['cycle'] < exp['earliest_result']:
                reject('RESULT_TOO_EARLY',str(req))
            for side in ('left','right'):
                self.check('result_'+side,exp[side],known(row,'result_'+side,24,True),row,'effect')
            for field,key in [('result_clip_mask','clip_mask'),('upstream_clip_mask','upstream_mask'),
                              ('effect_clip_mask','effect_mask'),('feedback_clip_mask','feedback_mask')]:
                self.check(field,exp[key],known(row,field,2),row,'clip')
            token['result_seen'] = True
            if known(row,'result_ready'):
                if token.get('result_accepted') is not None:
                    reject('DUPLICATE_RESULT_ACCEPT',str(req))
                token['result_accepted'] = row['cycle']
                self.counts['result_accepts'] += 1
                if len(self.compared)<self.limit:
                    self.compared.append(dict(epoch=self.epoch,cycle=row['cycle'],request_id=req,
                        left=exp['left'],right=exp['right'],clip_mask=exp['clip_mask'],
                        snapshot=token['snapshot']))
        if known(row,'commit'):
            req = known(row,'commit_id',32)
            token = self.tokens.get(req)
            if token is None or token.get('result_accepted') is None or token.get('cancelled') or token.get('committed'):
                reject('COMMIT_WITHOUT_UNIQUE_RESULT_ACCEPT',str(req))
            if row['cycle'] <= token['result_accepted']:
                reject('COMMIT_PRE_NBA_ORDER',str(req))
            exp = token['effect']
            for side in ('left','right'):
                self.check('commit_'+side,exp[side],known(row,'commit_'+side,24,True),row,'commit')
            self.check('commit_clip',int(bool(exp['clip_mask'])),known(row,'commit_clip'),row,'commit')
            token['committed'] = True
            self.counts['commits'] += 1

    def row(self, row):
        cycle,epoch = known(row,'cycle',64),known(row,'epoch',32)
        if cycle != self.cycle+1:
            reject('PUBLIC_POSEDGE_COVERAGE_GAP',f'{self.cycle}->{cycle}','UNSUPPORTED_PROFILE')
        self.cycle = cycle
        if known(row,'rst_n') == 0:
            # Explicit low reset rows are required by the initial supported
            # clock/reset profile. Subcycle resets without such rows reject in IO.
            if epoch < self.epoch or epoch > self.epoch+1:
                reject('RESET_EPOCH_DISCONTINUITY')
            if epoch!=self.epoch:
                self.close_epoch(reset_abort=True)
            self.reset(cycle,epoch)
            self.counts['reset_rows'] += 1
            return
        if epoch != self.epoch:
            reject('EPOCH_WITHOUT_RESET')
        self.state_check(row)
        self.take_snapshot(row)
        if known(row,'frame_tick'):
            if known(row,'result_valid') or known(row,'commit') or (known(row,'req_valid') and known(row,'req_ready')):
                reject('TRANSACTION_ON_FRAME_CANCEL_EDGE')
        self.outputs(row)
        frame = known(row,'frame_tick')
        if frame:
            for token in self.tokens.values():
                if not token.get('committed'):
                    token['cancelled'] = True
            self.counts['frames'] += 1
        if known(row,'cancel'):
            self.counts['cancel_observations'] += 1
        if frame and (known(row,'advance_mask',4) or known(row,'effect_input_ready')):
            reject('FRAME_CONFLICT_WITH_MATH')
        # Preserve simultaneous input consumption. A new accepted event must not
        # overwrite the cause of an earlier kind2 pulse at the same pre-NBA edge.
        pre_fcw = [lane.fcw for lane in self.lanes]
        pre_velocity = [lane.velocity for lane in self.lanes]
        pre_timbre = [lane.timbre for lane in self.lanes]
        on,off,event = self.application(row)
        self.accept_event(row)
        self.configuration(row)
        if known(row,'req_valid') and known(row,'req_ready'):
            req = known(row,'req_id',32)
            if req in self.tokens:
                reject('DUPLICATE_REQUEST_ID_IN_EPOCH',str(req))
            self.tokens[req] = dict(accepted_cycle=cycle)
            self.counts['requests'] += 1
        advance = known(row,'advance_mask',4)
        if advance not in (0,15):
            reject('PARTIAL_ADVANCE_MASK',str(advance),'UNSUPPORTED_PROFILE')
        token = None
        if advance:
            req = known(row,'advance_frame_req_id',32)
            token = self.tokens.get(req)
            if token is None or token.get('cancelled') or 'advance_cycle' in token:
                reject('ADVANCE_WITHOUT_LIVE_REQUEST',str(req))
            token.update(advance_cycle=cycle,snapshot_cycle=cycle+5,
                         occupied=known(row,'occupied_mask',4),waves=[])
            self.counts['all_lane_advances'] += 1
        for i,lane in enumerate(self.lanes):
            # At allocation the new registers only become visible after this
            # edge. Note consumption and tick use the pre-NBA FCW/velocity.
            before_phase = lane.piano.phase
            lane.envelope.edge(tick=bool(advance),on=bool(on&(1<<i)),
                               off=bool(off&(1<<i)),velocity=pre_velocity[i])
            lane.piano.edge(pre_fcw[i],velocity=pre_velocity[i],tick=bool(advance),note_on=bool(on&(1<<i)))
            if token is not None:
                addr = before_phase>>22 if pre_timbre[i] else (lane.piano.active_table<<8)|(lane.piano.phase>>24)
                token['waves'].append(self.ref.TRIANGLE[addr] if pre_timbre[i] else self.ref.PIANO[addr])
        self.input_effect(row)
        self.counts['active_rows'] += 1

    def close_epoch(self,reset_abort=False):
        if self.event_cursor != len(self.events) or self.config_cursor != len(self.config_events):
            reject('UNCONSUMED_INDEPENDENT_INPUT_PLAN')
        unfinished=[]
        for event in self.accepted.values():
            e=event['event']
            needed={1,2} if e['type']==0 and e['velocity'] else {5} if e['type']==4 else None
            complete=needed<=event['stages'] if needed is not None else bool(event['stages']&{6,7})
            if not complete:
                unfinished.append(event['plan_seq'])
        if unfinished and not reset_abort:
            reject('ACCEPTED_EVENT_WITHOUT_REQUIRED_APPLY',str(unfinished))
        self.epoch_receipts.append(dict(epoch=self.epoch,reset_aborted_events=unfinished))

    def finish(self):
        self.close_epoch()
        if self.pending_off or any(not l.note_consumed for l in self.lanes):
            reject('UNFINISHED_EVENT_APPLICATION')
        pending = [req for req,t in self.tokens.items() if not t.get('committed') and not t.get('cancelled')]
        if pending:
            reject('UNFINISHED_REQUESTS',str(pending))
        return dict(profile=PROFILE,counts=dict(self.counts),comparisons=self.compared,
                    actions=self.actions,first_difference=self.first_difference,
                    epoch_receipts=self.epoch_receipts,
                    tolerances=dict(pcm_lsb=0,id_exact=True,clip_exact=True),
                    unsupported=['CC64','panic','pitch/mod controls','subcycle reset without a sampled low row'],
                    expected_values_from_observed_pcm=False)
