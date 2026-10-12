"""Independent proposed single-clock frame transport, NOT an RTL math model."""
from copy import deepcopy

U32 = (1 << 32) - 1
FLAGS = ('rst_n', 'frame_tick', 'backend_ready', 'result_valid', 'clipped',
         'result_sink_ready', 'pcm_sink_ready')
INPUT_FIELDS = set(FLAGS) | {'result_epoch', 'result_id', 'left', 'right'}
INITIAL_FIELDS = {'current_id', 'clip_count'}


def require(ok, diagnostic):
    if not ok:
        raise ValueError(diagnostic)


def integer(value, low, high, diagnostic):
    require(type(value) is int and low <= value <= high, diagnostic)


def validate_input(inp):
    require(type(inp) is dict and set(inp) == INPUT_FIELDS, 'INPUT_FIELDS')
    for name in FLAGS:
        integer(inp[name], 0, 1, 'INPUT_FLAG:' + name)
    integer(inp['result_epoch'], 0, U32, 'INPUT_EPOCH')
    integer(inp['result_id'], 0, U32, 'INPUT_ID')
    for name in ('left', 'right'):
        integer(inp[name], -(1 << 23), (1 << 23) - 1, 'INPUT_PCM24:' + name)


def default_input(**updates):
    result = dict(rst_n=1, frame_tick=0, backend_ready=1, result_valid=0,
                  result_epoch=0, result_id=0, left=0, right=0, clipped=0,
                  result_sink_ready=1, pcm_sink_ready=1)
    result.update(updates)
    validate_input(result)
    return result


class FrameReference:
    def __init__(self, initial):
        require(type(initial) is dict and set(initial) == INITIAL_FIELDS, 'INITIAL_FIELDS')
        for name in INITIAL_FIELDS:
            integer(initial[name], 0, U32, 'INITIAL_U32:' + name)
        self.epoch, self.was_reset, self.blocked_result = 0, False, None
        self.clear()
        # Software entry-state fixtures ONLY; reset always clears these seeds.
        self.current_id, self.clip_count = initial['current_id'], initial['clip_count']

    def clear(self):
        self.current_id = self.clip_count = 0
        self.pending_request = self.dispatched = self.received = False
        self.pcm_record = self.committed_pending = self.held = None
        self.dispatch_count = self.result_count = self.commit_count = self.discard_count = 0
        self.blocked_result = None

    def state(self):
        return deepcopy(dict(epoch=self.epoch, current_id=self.current_id,
            pending_request=int(self.pending_request), dispatched=int(self.dispatched),
            received=int(self.received), pcm_record=self.pcm_record,
            committed_pending=self.committed_pending, held=self.held,
            clip_count=self.clip_count, dispatch_count=self.dispatch_count,
            result_count=self.result_count, commit_count=self.commit_count,
            discard_count=self.discard_count))

    def edge(self, inp):
        validate_input(inp)
        live_edge = inp['rst_n'] == 1 and inp['frame_tick'] == 0
        payload = dict(epoch=inp['result_epoch'], id=inp['result_id'],
                       left=inp['left'], right=inp['right'], clipped=inp['clipped'])
        current_result = (payload['epoch'], payload['id']) == (self.epoch, self.current_id)
        result_ready = live_edge and self.dispatched and not self.received and inp['result_sink_ready'] == 1
        result_accept = bool(result_ready and inp['result_valid'] and current_result)
        dispatch_valid = bool(live_edge and self.pending_request)
        dispatch_accept = bool(dispatch_valid and inp['backend_ready'])
        commit = bool(live_edge and self.pcm_record is not None and inp['pcm_sink_ready'])
        if self.pcm_record is not None:
            require((self.pcm_record['epoch'], self.pcm_record['id']) == (self.epoch, self.current_id), 'MODEL_STALE_PCM')
        # HOLD guarantee applies to a live unaccepted offer, not an already
        # invalid/duplicate identity. Frame/reset explicitly cancel the offer.
        if live_edge and self.blocked_result is not None:
            require(inp['result_valid'] == 1 and payload == self.blocked_result,
                    'RESULT_HOLD_STABILITY')
        self.blocked_result = (deepcopy(payload) if live_edge and inp['result_valid']
            and current_result and not self.received and not result_accept else None)
        discarded = bool(inp['rst_n'] and inp['result_valid'] and
                         (inp['frame_tick'] or not current_result or self.received))
        pre = dict(epoch=self.epoch, current_id=self.current_id,
            dispatch_valid=int(dispatch_valid), dispatch_accept=int(dispatch_accept),
            result_ready=int(bool(result_ready)), result_accept=int(result_accept),
            result_payload=payload if inp['result_valid'] else None,
            commit=int(commit), commit_payload=deepcopy(self.pcm_record) if commit else None,
            discard_result=int(discarded), cancelled_request=int(bool(inp['rst_n'] and inp['frame_tick'] and self.pending_request)),
            cancelled_pcm=int(bool(inp['rst_n'] and inp['frame_tick'] and self.pcm_record)),
            play_left=self.held['left'] if self.held else 0,
            play_right=self.held['right'] if self.held else 0)
        if not inp['rst_n']:
            if not self.was_reset:
                require(self.epoch < U32, 'EPOCH_EXHAUSTED_NO_REUSE')
                self.epoch += 1
            self.was_reset = True
            self.clear()
        else:
            self.was_reset = False
            if inp['frame_tick']:
                # Only a previously successful commit can enter the play hold.
                if self.committed_pending is not None:
                    self.held = self.committed_pending
                self.committed_pending = self.pcm_record = None
                self.current_id = (self.current_id + 1) & U32
                self.pending_request, self.dispatched, self.received = True, False, False
                self.blocked_result = None
            else:
                if dispatch_accept:
                    self.pending_request, self.dispatched = False, True
                    self.dispatch_count += 1
                if commit:
                    self.committed_pending = self.pcm_record
                    self.pcm_record = None
                    self.commit_count += 1
                    if self.committed_pending['clipped']:
                        self.clip_count = min(U32, self.clip_count + 1)
                if result_accept:
                    self.pcm_record = deepcopy(payload)
                    self.received = True
                    self.result_count += 1
            self.discard_count += int(discarded)
        return pre, self.state()
